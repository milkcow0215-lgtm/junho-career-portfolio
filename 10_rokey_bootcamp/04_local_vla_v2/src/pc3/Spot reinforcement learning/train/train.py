# Copyright (c) 2022-2026, The Isaac Lab Project Developers (https://github.com/isaac-sim/IsaacLab/blob/main/CONTRIBUTORS.md).
# All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause

"""Script to train RL agent with RSL-RL."""

"""Launch Isaac Sim Simulator first."""

import argparse
import sys

# Isaac Sim 앱을 초기화하고 시뮬레이터 인스턴스를 생성하는 런처
from isaaclab.app import AppLauncher

# local imports
import cli_args  # isort: skip

# --- CLI 인자 정의 ---
# 학습 실행 시 커맨드라인에서 제어 가능한 옵션들을 등록
parser = argparse.ArgumentParser(description="Train an RL agent with RSL-RL.")
parser.add_argument("--video", action="store_true", default=False, help="Record videos during training.")
parser.add_argument("--video_length", type=int, default=200, help="Length of the recorded video (in steps).")
parser.add_argument("--video_interval", type=int, default=2000, help="Interval between video recordings (in steps).")
parser.add_argument("--num_envs", type=int, default=None, help="Number of environments to simulate.")
parser.add_argument("--task", type=str, default=None, help="Name of the task.")
parser.add_argument(
    "--agent", type=str, default="rsl_rl_cfg_entry_point", help="Name of the RL agent configuration entry point."
)
parser.add_argument("--seed", type=int, default=None, help="Seed used for the environment")
parser.add_argument("--max_iterations", type=int, default=None, help="RL Policy training iterations.")
parser.add_argument(
    "--distributed", action="store_true", default=False, help="Run training with multiple GPUs or nodes."
)
parser.add_argument("--export_io_descriptors", action="store_true", default=False, help="Export IO descriptors.")
parser.add_argument(
    "--ray-proc-id", "-rid", type=int, default=None, help="Automatically configured by Ray integration, otherwise None."
)
# RSL-RL 전용 인자(load_run, checkpoint 등) 추가
cli_args.add_rsl_rl_args(parser)
# Isaac Sim AppLauncher 전용 인자(headless, device 등) 추가
AppLauncher.add_app_launcher_args(parser)
# 알려진 인자와 Hydra용 나머지 인자를 분리하여 파싱
args_cli, hydra_args = parser.parse_known_args()

# 비디오 녹화 시 카메라 렌더링 강제 활성화
if args_cli.video:
    args_cli.enable_cameras = True

# Hydra가 sys.argv를 직접 파싱하므로, Isaac/argparse 인자를 제거하고 Hydra 인자만 남김
sys.argv = [sys.argv[0]] + hydra_args

# --- Isaac Sim 앱 초기화 ---
# 이 시점부터 GPU/렌더링 컨텍스트가 활성화되며, 이후 모든 isaac 모듈을 임포트할 수 있음
app_launcher = AppLauncher(args_cli)
simulation_app = app_launcher.app

"""Check for minimum supported RSL-RL version."""

import importlib.metadata as metadata
import platform

from packaging import version

# 설치된 rsl-rl-lib 버전이 최소 요구 버전(3.0.1) 이상인지 확인
RSL_RL_VERSION = "3.0.1"
installed_version = metadata.version("rsl-rl-lib")
if version.parse(installed_version) < version.parse(RSL_RL_VERSION):
    if platform.system() == "Windows":
        cmd = [r".\isaaclab.bat", "-p", "-m", "pip", "install", f"rsl-rl-lib=={RSL_RL_VERSION}"]
    else:
        cmd = ["./isaaclab.sh", "-p", "-m", "pip", "install", f"rsl-rl-lib=={RSL_RL_VERSION}"]
    print(
        f"Please install the correct version of RSL-RL.\nExisting version is: '{installed_version}'"
        f" and required version is: '{RSL_RL_VERSION}'.\nTo install the correct version, run:"
        f"\n\n\t{' '.join(cmd)}\n"
    )
    exit(1)

"""Rest everything follows."""

import logging
import os
import time
from datetime import datetime

import gymnasium as gym
import torch
# OnPolicyRunner: PPO 등 on-policy 알고리즘 학습 루프
# DistillationRunner: 교사-학생 정책 증류(distillation) 학습 루프
from rsl_rl.runners import DistillationRunner, OnPolicyRunner

from isaaclab.envs import (
    DirectMARLEnv,
    DirectMARLEnvCfg,
    DirectRLEnvCfg,
    ManagerBasedRLEnvCfg,
    multi_agent_to_single_agent,
)
from isaaclab.utils.dict import print_dict
from isaaclab.utils.io import dump_yaml

# RslRlVecEnvWrapper: Isaac 환경을 RSL-RL이 요구하는 VecEnv 인터페이스로 변환
from isaaclab_rl.rsl_rl import RslRlBaseRunnerCfg, RslRlVecEnvWrapper, handle_deprecated_rsl_rl_cfg

from isaaclab_tasks.utils import get_checkpoint_path
# hydra_task_config: 태스크 이름으로 env_cfg와 agent_cfg를 Hydra를 통해 자동 주입하는 데코레이터
from isaaclab_tasks.utils.hydra import hydra_task_config

logger = logging.getLogger(__name__)

# PLACEHOLDER: Extension template (do not remove this comment)

# TF32 및 cuDNN 설정: 학습 속도와 재현성 간의 트레이드오프 조정
torch.backends.cuda.matmul.allow_tf32 = True   # matmul에 TF32 허용 (속도 향상)
torch.backends.cudnn.allow_tf32 = True          # cuDNN에 TF32 허용 (속도 향상)
torch.backends.cudnn.deterministic = False      # 결정론적 연산 비활성화 (속도 우선)
torch.backends.cudnn.benchmark = False          # 자동 커널 최적화 비활성화 (안정성 우선)


# hydra_task_config 데코레이터가 --task와 --agent 인자를 바탕으로
# env_cfg(환경 설정)와 agent_cfg(학습 알고리즘 설정)를 자동으로 주입
@hydra_task_config(args_cli.task, args_cli.agent)
def main(env_cfg: ManagerBasedRLEnvCfg | DirectRLEnvCfg | DirectMARLEnvCfg, agent_cfg: RslRlBaseRunnerCfg):
    """Train with RSL-RL agent."""
    # CLI 인자로 Hydra 기본 설정을 덮어씀 (num_envs, seed, max_iterations 등)
    agent_cfg = cli_args.update_rsl_rl_cfg(agent_cfg, args_cli)
    env_cfg.scene.num_envs = args_cli.num_envs if args_cli.num_envs is not None else env_cfg.scene.num_envs
    agent_cfg.max_iterations = (
        args_cli.max_iterations if args_cli.max_iterations is not None else agent_cfg.max_iterations
    )

    # 구버전 rsl-rl 설정 필드를 현재 버전 형식으로 자동 변환
    agent_cfg = handle_deprecated_rsl_rl_cfg(agent_cfg, installed_version)

    # 환경 시드 및 시뮬레이션 디바이스 설정
    env_cfg.seed = agent_cfg.seed
    env_cfg.sim.device = args_cli.device if args_cli.device is not None else env_cfg.sim.device
    if args_cli.distributed and args_cli.device is not None and "cpu" in args_cli.device:
        raise ValueError(
            "Distributed training is not supported when using CPU device. "
            "Please use GPU device (e.g., --device cuda) for distributed training."
        )

    # 멀티 GPU 분산 학습: 각 프로세스가 고유한 GPU와 시드를 사용하도록 설정
    if args_cli.distributed:
        env_cfg.sim.device = f"cuda:{app_launcher.local_rank}"
        agent_cfg.device = f"cuda:{app_launcher.local_rank}"
        # 각 워커가 서로 다른 시드를 갖도록 local_rank를 더함
        seed = agent_cfg.seed + app_launcher.local_rank
        env_cfg.seed = seed
        agent_cfg.seed = seed

    # 로그 저장 경로: logs/rsl_rl/<experiment_name>/<timestamp>_<run_name>
    log_root_path = os.path.join("logs", "rsl_rl", agent_cfg.experiment_name)
    log_root_path = os.path.abspath(log_root_path)
    print(f"[INFO] Logging experiment in directory: {log_root_path}")
    log_dir = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    print(f"Exact experiment name requested from command line: {log_dir}")
    if agent_cfg.run_name:
        log_dir += f"_{agent_cfg.run_name}"
    log_dir = os.path.join(log_root_path, log_dir)

    # IO 디스크립터 내보내기는 ManagerBasedRLEnv에서만 지원
    if isinstance(env_cfg, ManagerBasedRLEnvCfg):
        env_cfg.export_io_descriptors = args_cli.export_io_descriptors
    else:
        logger.warning(
            "IO descriptors are only supported for manager based RL environments. No IO descriptors will be exported."
        )

    env_cfg.log_dir = log_dir

    # --- 환경 생성 ---
    # gymnasium.make로 Isaac 시뮬레이션 환경 인스턴스화
    env = gym.make(args_cli.task, cfg=env_cfg, render_mode="rgb_array" if args_cli.video else None)

    # 멀티에이전트 환경은 단일 에이전트 인터페이스로 래핑하여 RSL-RL과 호환
    if isinstance(env.unwrapped, DirectMARLEnv):
        env = multi_agent_to_single_agent(env)

    # 학습 재개 또는 증류 학습 시 체크포인트 경로 탐색
    if agent_cfg.resume or agent_cfg.algorithm.class_name == "Distillation":
        resume_path = get_checkpoint_path(log_root_path, agent_cfg.load_run, agent_cfg.load_checkpoint)

    # 비디오 녹화 래퍼: 일정 스텝 간격마다 에피소드를 mp4로 저장
    if args_cli.video:
        video_kwargs = {
            "video_folder": os.path.join(log_dir, "videos", "train"),
            "step_trigger": lambda step: step % args_cli.video_interval == 0,
            "video_length": args_cli.video_length,
            "disable_logger": True,
        }
        print("[INFO] Recording videos during training.")
        print_dict(video_kwargs, nesting=4)
        env = gym.wrappers.RecordVideo(env, **video_kwargs)

    start_time = time.time()

    # Isaac 환경을 RSL-RL VecEnv 형식으로 변환 (액션 클리핑 포함)
    env = RslRlVecEnvWrapper(env, clip_actions=agent_cfg.clip_actions)

    # --- Runner 생성 ---
    # 알고리즘 종류에 따라 적절한 Runner 선택
    if agent_cfg.class_name == "OnPolicyRunner":
        # 표준 on-policy 학습 (PPO 등)
        runner = OnPolicyRunner(env, agent_cfg.to_dict(), log_dir=log_dir, device=agent_cfg.device)
    elif agent_cfg.class_name == "DistillationRunner":
        # 교사 정책으로부터 학생 정책을 증류하는 학습
        runner = DistillationRunner(env, agent_cfg.to_dict(), log_dir=log_dir, device=agent_cfg.device)
    else:
        raise ValueError(f"Unsupported runner class: {agent_cfg.class_name}")

    # TensorBoard 로그에 현재 git 커밋 정보 기록 (재현성 추적용)
    runner.add_git_repo_to_log(__file__)

    # 이전 체크포인트에서 모델 가중치 및 옵티마이저 상태 복원
    if agent_cfg.resume or agent_cfg.algorithm.class_name == "Distillation":
        print(f"[INFO]: Loading model checkpoint from: {resume_path}")
        runner.load(resume_path)

    # 환경/에이전트 설정을 YAML로 저장하여 실험 재현 가능하게 기록
    dump_yaml(os.path.join(log_dir, "params", "env.yaml"), env_cfg)
    dump_yaml(os.path.join(log_dir, "params", "agent.yaml"), agent_cfg)

    # --- 학습 시작 ---
    # max_iterations 횟수만큼 정책 업데이트, 초기 에피소드 길이는 랜덤으로 시작
    runner.learn(num_learning_iterations=agent_cfg.max_iterations, init_at_random_ep_len=True)

    print(f"Training time: {round(time.time() - start_time, 2)} seconds")
    env.close()


if __name__ == "__main__":
    main()
    # 학습 완료 후 Isaac Sim 앱 종료
    simulation_app.close()
