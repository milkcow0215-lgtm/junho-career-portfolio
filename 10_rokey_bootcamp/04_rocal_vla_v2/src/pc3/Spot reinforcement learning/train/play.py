# Copyright (c) 2022-2026, The Isaac Lab Project Developers (https://github.com/isaac-sim/IsaacLab/blob/main/CONTRIBUTORS.md).
# All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause

"""Script to play a checkpoint if an RL agent from RSL-RL."""

"""Launch Isaac Sim Simulator first."""

# ────────────────────────────────────────────────────────────
# [1] 기본 임포트 및 CLI 인자 파싱
#     - Isaac Sim 앱을 먼저 실행해야 하므로, AppLauncher 관련 인자를
#       여기서 파싱하고 시뮬레이터를 띄운다.
# ────────────────────────────────────────────────────────────
import argparse
import sys

from isaaclab.app import AppLauncher

# local imports
import cli_args  # isort: skip


# add argparse arguments
parser = argparse.ArgumentParser(description="Train an RL agent with RSL-RL.")
parser.add_argument("--video", action="store_true", default=False, help="Record videos during training.")
parser.add_argument("--video_length", type=int, default=200, help="Length of the recorded video (in steps).")
parser.add_argument(
    "--disable_fabric", action="store_true", default=False, help="Disable fabric and use USD I/O operations."
)
parser.add_argument("--num_envs", type=int, default=None, help="Number of environments to simulate.")
parser.add_argument("--task", type=str, default=None, help="Name of the task.")
parser.add_argument(
    "--agent", type=str, default="rsl_rl_cfg_entry_point", help="Name of the RL agent configuration entry point."
)
parser.add_argument("--seed", type=int, default=None, help="Seed used for the environment")
parser.add_argument(
    "--use_pretrained_checkpoint",
    action="store_true",
    help="Use the pre-trained checkpoint from Nucleus.",
)
parser.add_argument("--real-time", action="store_true", default=False, help="Run in real-time, if possible.")
parser.add_argument("--teleop", action="store_true", default=False, help="Enable keyboard teleoperation.")
parser.add_argument("--ros_teleop", action="store_true", default=False, help="Enable ROS2 /cmd_vel teleoperation.")
parser.add_argument("--cmd_vel_topic", type=str, default="/cmd_vel", help="ROS2 Twist topic for teleop.")
# append RSL-RL cli arguments
cli_args.add_rsl_rl_args(parser)
# append AppLauncher cli args
AppLauncher.add_app_launcher_args(parser)
# parse the arguments
args_cli, hydra_args = parser.parse_known_args()
# always enable cameras to record video
if args_cli.video:
    args_cli.enable_cameras = True

# Spot Play 환경처럼 CameraCfg 센서가 포함된 태스크는 --enable_cameras 없이도
# 렌더링 파이프라인이 켜져야 한다. 태스크 이름에 "Spot"이 포함되면 자동 활성화한다.
if args_cli.task and "Spot" in args_cli.task:
    args_cli.enable_cameras = True

# clear out sys.argv for Hydra
sys.argv = [sys.argv[0]] + hydra_args

# ────────────────────────────────────────────────────────────
# [2] Isaac Sim 앱 실행
#     - AppLauncher가 Omniverse 런타임을 초기화한다.
#     - 이후 모든 isaac/torch 임포트는 여기 이후에 해야 한다.
# ────────────────────────────────────────────────────────────
app_launcher = AppLauncher(args_cli)
simulation_app = app_launcher.app

"""Check for installed RSL-RL version."""

# ────────────────────────────────────────────────────────────
# [3] RSL-RL 버전 확인
#     - 설치된 rsl-rl-lib 버전에 따라 API 호출 방식이 달라지므로
#       버전을 미리 읽어 둔다.
# ────────────────────────────────────────────────────────────
import importlib.metadata as metadata

from packaging import version

installed_version = metadata.version("rsl-rl-lib")

"""Rest everything follows."""

# ────────────────────────────────────────────────────────────
# [4] 나머지 임포트
#     - Isaac Sim 앱 실행 후에만 임포트 가능한 모듈들
# ────────────────────────────────────────────────────────────
import os
import threading
import time

import gymnasium as gym
import torch
from rsl_rl.runners import DistillationRunner, OnPolicyRunner

from isaaclab.envs import (
    DirectMARLEnv,
    DirectMARLEnvCfg,
    DirectRLEnvCfg,
    ManagerBasedRLEnvCfg,
    multi_agent_to_single_agent,
)
from isaaclab.utils.assets import retrieve_file_path
from isaaclab.utils.dict import print_dict

from isaaclab_rl.rsl_rl import (
    RslRlBaseRunnerCfg,
    RslRlVecEnvWrapper,
    export_policy_as_jit,
    export_policy_as_onnx,
    handle_deprecated_rsl_rl_cfg,
)
from isaaclab_rl.utils.pretrained_checkpoint import get_published_pretrained_checkpoint

import isaaclab_tasks  # noqa: F401
from isaaclab_tasks.utils import get_checkpoint_path
from isaaclab_tasks.utils.hydra import hydra_task_config


# ────────────────────────────────────────────────────────────
# [5] 키보드 원격 조작 (Teleoperation)
#     - pynput으로 키 이벤트를 백그라운드 스레드에서 수신한다.
#     - get_command()로 매 스텝마다 [vx, vy, wz] 명령을 읽어
#       velocity_term에 직접 주입한다.
#     - W/S: 전진·후진, A/D: 좌·우회전, ↑/↓: 속도 조절
# ────────────────────────────────────────────────────────────
class KeyboardTeleop:
    """WASD 방향 제어 + 상하 화살표 속도 조절 키보드 원격 조작."""

    # 기본 속도 범위 및 증가 단위
    DEFAULT_SPEED = 0.5
    SPEED_STEP = 0.1
    MAX_SPEED = 5.0
    MIN_SPEED = 0.1

    def __init__(self):
        self.speed = self.DEFAULT_SPEED
        self._keys: set = set()
        self._lock = threading.Lock()

        try:
            from pynput import keyboard as kb
            from pynput.keyboard import Key

            self._Key = Key

            _DIR_LABELS = {"w": "전진", "s": "후진", "a": "좌회전", "d": "우회전"}

            def on_press(key):
                with self._lock:
                    try:
                        ch = key.char.lower()
                        if ch not in self._keys and ch in _DIR_LABELS:
                            print(f"[Teleop] {_DIR_LABELS[ch]} ({ch.upper()})", flush=True)
                        self._keys.add(ch)
                    except AttributeError:
                        self._keys.add(key)
                    if key == Key.up:
                        self.speed = min(self.speed + self.SPEED_STEP, self.MAX_SPEED)
                        print(f"[Teleop] 속도 증가 → {self.speed:.1f} m/s", flush=True)
                    elif key == Key.down:
                        self.speed = max(self.speed - self.SPEED_STEP, self.MIN_SPEED)
                        print(f"[Teleop] 속도 감소 → {self.speed:.1f} m/s", flush=True)

            def on_release(key):
                with self._lock:
                    try:
                        self._keys.discard(key.char.lower())
                    except AttributeError:
                        self._keys.discard(key)

            self._listener = kb.Listener(on_press=on_press, on_release=on_release)
            self._listener.daemon = True
            self._listener.start()
            print("\n" + "=" * 60)
            print("[Teleop] 키보드 조작 안내")
            print("  W / S       : 전진 / 후진")
            print("  A / D       : 좌회전 / 우회전")
            print("  ↑ / ↓ 방향키 : 속도 증가 / 감소")
            print(f"  현재 속도    : {self.speed:.1f} m/s  (범위: {self.MIN_SPEED}~{self.MAX_SPEED})")
            print("=" * 60 + "\n")
        except ImportError:
            print("[WARNING] pynput 미설치 — 키보드 조작 비활성화. `pip install pynput` 후 재시도하세요.")
            self._listener = None

    def get_command(self) -> list[float]:
        """현재 키 상태에 따른 [vx, vy, wz] 반환."""
        with self._lock:
            vx, vy, wz = 0.0, 0.0, 0.0
            spd = self.speed
            Key = self._Key if hasattr(self, "_Key") else None

            if "w" in self._keys:
                vx += spd
            if "s" in self._keys:
                vx -= spd
            if "a" in self._keys:
                wz += spd
            if "d" in self._keys:
                wz -= spd

        return [vx, vy, wz]

    def reset(self):
        with self._lock:
            self._keys.clear()

    def close(self):
        if self._listener is not None:
            self._listener.stop()


# ────────────────────────────────────────────────────────────
# [5-b] ROS2 /cmd_vel 원격 조작 (Teleoperation)
#     - Isaac Sim 번들 rclpy(humble, py3.11)를 사용 → 시스템 ROS 버전과 무관.
#     - geometry_msgs/Twist 를 구독하여 [vx, vy, wz] = [lin.x, lin.y, ang.z]
#       를 매 스텝 velocity_term 에 주입한다. (KeyboardTeleop 과 동일 인터페이스)
#     - 외부에서:  ros2 run teleop_twist_keyboard teleop_twist_keyboard
#                  (또는 ros2 topic pub /cmd_vel geometry_msgs/msg/Twist ...)
# ────────────────────────────────────────────────────────────
class ROS2Teleop:
    """ROS2 /cmd_vel(Twist) 구독 기반 원격 조작 (Isaac Sim 번들 rclpy 사용)."""

    def __init__(self, topic: str = "/cmd_vel"):
        self._lock = threading.Lock()
        self._cmd = [0.0, 0.0, 0.0]
        self._ok = False
        try:
            # Isaac Sim ROS2 브리지 확장 활성화 (내부 ROS2 라이브러리 로드)
            from isaacsim.core.utils.extensions import enable_extension

            enable_extension("isaacsim.ros2.bridge")

            # 시스템 ROS rclpy(py3.10)와 충돌 방지: Isaac 번들 rclpy(py3.11)를 sys.path 최우선 삽입
            import os as _os
            import isaacsim as _isim

            _bridge = _os.path.join(_os.path.dirname(_isim.__file__), "exts", "isaacsim.ros2.bridge")
            for _distro in (_os.environ.get("ROS_DISTRO", "humble"), "humble", "jazzy"):
                _cand = _os.path.join(_bridge, _distro)
                if _os.path.isdir(_os.path.join(_cand, "rclpy")):
                    if _cand in sys.path:
                        sys.path.remove(_cand)
                    sys.path.insert(0, _cand)
                    break
            # 이미 로드된 시스템 rclpy 캐시 제거 (있으면)
            for _m in [k for k in list(sys.modules) if k == "rclpy" or k.startswith("rclpy.")]:
                del sys.modules[_m]

            import rclpy
            from geometry_msgs.msg import Twist
            from rclpy.node import Node

            if not rclpy.ok():
                rclpy.init()

            self._rclpy = rclpy
            node = Node("isaac_spot_teleop")

            def _cb(msg: "Twist"):
                with self._lock:
                    self._cmd = [float(msg.linear.x), float(msg.linear.y), float(msg.angular.z)]

            node.create_subscription(Twist, topic, _cb, 10)
            self._node = node

            def _spin():
                while rclpy.ok():
                    rclpy.spin_once(node, timeout_sec=0.1)

            self._thread = threading.Thread(target=_spin, daemon=True)
            self._thread.start()
            self._ok = True
            print("\n" + "=" * 60)
            print("[ROS Teleop] ROS2 /cmd_vel 구독 활성화")
            print(f"  토픽       : {topic}  (geometry_msgs/Twist)")
            print("  매핑       : linear.x→vx, linear.y→vy, angular.z→wz")
            print("  예시       : ros2 run teleop_twist_keyboard teleop_twist_keyboard")
            print("=" * 60 + "\n")
        except Exception as e:
            print(f"[WARNING] ROS2 teleop 초기화 실패: {e}")
            self._ok = False

    def get_command(self) -> list[float]:
        if not self._ok:
            return [0.0, 0.0, 0.0]
        with self._lock:
            return list(self._cmd)

    def reset(self):
        with self._lock:
            self._cmd = [0.0, 0.0, 0.0]

    def close(self):
        try:
            if self._ok:
                self._node.destroy_node()
        except Exception:
            pass


@hydra_task_config(args_cli.task, args_cli.agent)
def main(env_cfg: ManagerBasedRLEnvCfg | DirectRLEnvCfg | DirectMARLEnvCfg, agent_cfg: RslRlBaseRunnerCfg):
    """Play with RSL-RL agent."""

    # ────────────────────────────────────────────────────────
    # [6] 태스크 이름 및 에이전트 설정 초기화
    #     - Play 전용 태스크(예: Foo-Play)에서 학습 태스크 이름을
    #       추출하여 체크포인트 경로 탐색에 사용한다.
    # ────────────────────────────────────────────────────────
    task_name = args_cli.task.split(":")[-1]
    train_task_name = task_name.replace("-Play", "")

    agent_cfg: RslRlBaseRunnerCfg = cli_args.update_rsl_rl_cfg(agent_cfg, args_cli)
    env_cfg.scene.num_envs = args_cli.num_envs if args_cli.num_envs is not None else env_cfg.scene.num_envs

    # rsl-rl 구버전 설정 호환 처리
    agent_cfg = handle_deprecated_rsl_rl_cfg(agent_cfg, installed_version)

    env_cfg.seed = agent_cfg.seed
    env_cfg.sim.device = args_cli.device if args_cli.device is not None else env_cfg.sim.device

    # ────────────────────────────────────────────────────────
    # [7] 체크포인트 경로 결정
    #     우선순위: --use_pretrained_checkpoint > --checkpoint > 자동 탐색
    # ────────────────────────────────────────────────────────
    log_root_path = os.path.join("logs", "rsl_rl", agent_cfg.experiment_name)
    log_root_path = os.path.abspath(log_root_path)
    print(f"[INFO] Loading experiment from directory: {log_root_path}")
    if args_cli.use_pretrained_checkpoint:
        # Nucleus 서버의 공개 사전학습 체크포인트 사용
        resume_path = get_published_pretrained_checkpoint("rsl_rl", train_task_name)
        if not resume_path:
            print("[INFO] Unfortunately a pre-trained checkpoint is currently unavailable for this task.")
            return
    elif args_cli.checkpoint:
        # CLI에서 직접 지정한 체크포인트 파일 경로
        resume_path = retrieve_file_path(args_cli.checkpoint)
    else:
        # 로그 디렉토리에서 가장 최신 체크포인트를 자동으로 탐색
        resume_path = get_checkpoint_path(log_root_path, agent_cfg.load_run, agent_cfg.load_checkpoint)

    log_dir = os.path.dirname(resume_path)
    env_cfg.log_dir = log_dir

    # ────────────────────────────────────────────────────────
    # [8] 환경 생성 및 래핑
    #     - gymnasium.make → DirectMARLEnv 단일 에이전트 변환(필요 시)
    #     - 비디오 녹화 옵션 → RecordVideo 래퍼 추가
    #     - RSL-RL용 벡터 환경 래퍼(RslRlVecEnvWrapper) 적용
    # ────────────────────────────────────────────────────────
    env = gym.make(args_cli.task, cfg=env_cfg, render_mode="rgb_array" if args_cli.video else None)

    # 멀티 에이전트 환경을 단일 에이전트로 변환
    if isinstance(env.unwrapped, DirectMARLEnv):
        env = multi_agent_to_single_agent(env)

    # 첫 스텝에서만 녹화를 시작하고 video_length 스텝 후 종료
    if args_cli.video:
        video_kwargs = {
            "video_folder": os.path.join(log_dir, "videos", "play"),
            "step_trigger": lambda step: step == 0,
            "video_length": args_cli.video_length,
            "disable_logger": True,
        }
        print("[INFO] Recording videos during training.")
        print_dict(video_kwargs, nesting=4)
        env = gym.wrappers.RecordVideo(env, **video_kwargs)

    # RSL-RL 내부 API와 호환되는 벡터 환경 래퍼
    env = RslRlVecEnvWrapper(env, clip_actions=agent_cfg.clip_actions)

    # ────────────────────────────────────────────────────────
    # [9] 모델 로드 및 추론 정책 획득
    #     - agent_cfg.class_name에 따라 OnPolicyRunner 또는
    #       DistillationRunner를 선택하여 체크포인트를 불러온다.
    # ────────────────────────────────────────────────────────
    print(f"[INFO]: Loading model checkpoint from: {resume_path}")
    if agent_cfg.class_name == "OnPolicyRunner":
        runner = OnPolicyRunner(env, agent_cfg.to_dict(), log_dir=None, device=agent_cfg.device)
    elif agent_cfg.class_name == "DistillationRunner":
        runner = DistillationRunner(env, agent_cfg.to_dict(), log_dir=None, device=agent_cfg.device)
    else:
        raise ValueError(f"Unsupported runner class: {agent_cfg.class_name}")
    runner.load(resume_path)

    # 추론 전용 정책 함수 (그래디언트 불필요)
    policy = runner.get_inference_policy(device=env.unwrapped.device)

    # ────────────────────────────────────────────────────────
    # [10] 학습된 정책 내보내기 (JIT / ONNX)
    #      - rsl-rl >= 4.0.0: runner 내장 export API 사용
    #      - 구버전: isaaclab_rl 유틸 함수로 직접 내보내기
    #      - 내보낸 파일은 체크포인트 디렉토리의 exported/ 에 저장
    # ────────────────────────────────────────────────────────
    export_model_dir = os.path.join(os.path.dirname(resume_path), "exported")

    if version.parse(installed_version) >= version.parse("4.0.0"):
        runner.export_policy_to_jit(path=export_model_dir, filename="policy.pt")
        runner.export_policy_to_onnx(path=export_model_dir, filename="policy.onnx")
    else:
        if version.parse(installed_version) >= version.parse("2.3.0"):
            policy_nn = runner.alg.policy
        else:
            policy_nn = runner.alg.actor_critic

        if hasattr(policy_nn, "actor_obs_normalizer"):
            normalizer = policy_nn.actor_obs_normalizer
        elif hasattr(policy_nn, "student_obs_normalizer"):
            normalizer = policy_nn.student_obs_normalizer
        else:
            normalizer = None

        export_policy_as_jit(policy_nn, normalizer=normalizer, path=export_model_dir, filename="policy.pt")
        export_policy_as_onnx(policy_nn, normalizer=normalizer, path=export_model_dir, filename="policy.onnx")

    dt = env.unwrapped.step_dt

    # ────────────────────────────────────────────────────────
    # [11] 속도 명령 고정 (랜덤 리샘플링 비활성화)
    #      - 학습 중 env.step()은 command_manager를 통해 매 에피소드마다
    #        속도 목표를 무작위로 바꾼다.
    #      - 플레이 시에는 _resample / _update_command를 no-op으로
    #        교체하여 명령이 덮어써지지 않도록 막는다.
    # ────────────────────────────────────────────────────────
    obs = env.get_observations()
    timestep = 0

    velocity_term = None
    if hasattr(env.unwrapped, "command_manager"):
        try:
            velocity_term = env.unwrapped.command_manager.get_term("base_velocity")
            velocity_term.command[:] = 0.0
            velocity_term._resample = lambda *args, **kwargs: None
            velocity_term._update_command = lambda: None
            print("[INFO] Random velocity commands disabled.")
        except Exception as e:
            print(f"[INFO] Could not disable random commands: {e}")

    # ────────────────────────────────────────────────────────
    # [12] 키보드 텔레오퍼레이션 초기화
    #      - --teleop 플래그가 있을 때만 활성화
    #      - _inject_command()가 매 스텝 후 velocity_term에 명령을 주입
    # ────────────────────────────────────────────────────────
    keyboard = None
    if args_cli.ros_teleop:
        keyboard = ROS2Teleop(args_cli.cmd_vel_topic)  # KeyboardTeleop과 동일 인터페이스
        keyboard.reset()
    elif args_cli.teleop:
        keyboard = KeyboardTeleop()
        keyboard.reset()

    def _inject_command():
        """키보드 커맨드를 velocity_term에 주입. env.step() 이후 호출해야 obs에 반영됨."""
        if keyboard is None or velocity_term is None:
            return
        teleop_command = keyboard.get_command()
        cmd_tensor = torch.tensor(teleop_command, device=env.unwrapped.device, dtype=torch.float32)
        velocity_term.command[:] = cmd_tensor

    # 첫 스텝 전에 초기 명령 주입
    _inject_command()

    # ────────────────────────────────────────────────────────
    # [13] 메인 시뮬레이션 루프
    #      흐름: policy(obs) → env.step(actions) → _inject_command()
    #      - --real-time: dt 기준으로 sleep하여 실시간 속도 유지
    #      - --video: video_length 스텝 후 루프 종료
    # ────────────────────────────────────────────────────────
    while simulation_app.is_running():
        start_time = time.time()

        with torch.inference_mode():
            actions = policy(obs)
            obs, _, dones, _ = env.step(actions)

        # env.step() 이후 주입해야 다음 obs에 최신 명령이 반영됨
        _inject_command()

        # if args_cli.video:
        #     timestep += 1
        #     if timestep == args_cli.video_length:
        #         break

        # 실시간 모드: 남은 시간만큼 대기하여 dt 주기 맞춤
        sleep_time = dt - (time.time() - start_time)
        if args_cli.real_time and sleep_time > 0:
            time.sleep(sleep_time)

    # ────────────────────────────────────────────────────────
    # [14] 정리(Cleanup)
    # ────────────────────────────────────────────────────────
    if keyboard is not None:
        keyboard.close()

    env.close()


if __name__ == "__main__":
    main()
    simulation_app.close()
