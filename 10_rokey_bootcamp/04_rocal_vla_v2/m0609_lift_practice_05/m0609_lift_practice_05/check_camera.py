from __future__ import annotations

import argparse
import os
import sys

THIS_DIR = os.path.dirname(os.path.abspath(__file__))
if THIS_DIR not in sys.path:
    sys.path.insert(0, THIS_DIR)

from isaaclab.app import AppLauncher

parser = argparse.ArgumentParser(description="Check wrist camera output.")
parser.add_argument("--task", type=str, default="My_Isaac-M0609-Play-v0")
parser.add_argument("--num_envs", type=int, default=1)
parser.add_argument(
    "--agent",
    type=str,
    default="rsl_rl_cfg_entry_point",
    help="RL agent config entry point key.",
)

AppLauncher.add_app_launcher_args(parser)
args_cli, hydra_args = parser.parse_known_args()

sys.argv = [sys.argv[0]] + hydra_args

app_launcher = AppLauncher(args_cli)
simulation_app = app_launcher.app

import gymnasium as gym
import numpy as np
import torch

import isaaclab_tasks  # noqa: F401
import m0609_lift  # noqa: F401

from isaaclab.envs import ManagerBasedRLEnvCfg
from isaaclab_tasks.utils.hydra import hydra_task_config


@hydra_task_config(args_cli.task, args_cli.agent)
def main(env_cfg: ManagerBasedRLEnvCfg, agent_cfg):
    # num_envs는 env 생성 전에 cfg에 넣어야 한다.
    env_cfg.scene.num_envs = args_cli.num_envs

    env = gym.make(args_cli.task, cfg=env_cfg)

    raw_env = env.unwrapped
    device = raw_env.device
    num_envs = raw_env.num_envs

    obs, info = env.reset()

    act_dim = env.action_space.shape[-1]
    zero_action = torch.zeros((num_envs, act_dim), device=device)

    # 카메라/센서 데이터가 업데이트되도록 몇 step 진행
    for _ in range(30):
        env.step(zero_action)

    print("====================================")
    print("[CAMERA DEBUG]")

    if "wrist_camera" not in raw_env.scene.keys():
        print("[ERROR] scene 안에 wrist_camera가 없음.")
        print("Available scene keys:", raw_env.scene.keys())
        env.close()
        return

    cam = raw_env.scene["wrist_camera"]

    print("camera object:", cam)
    print("available output keys:", cam.data.output.keys())

    for key, value in cam.data.output.items():
        print("[CAMERA DEBUG]", key, value.shape, value.dtype, value.device)

    if "rgb" in cam.data.output:
        rgb = cam.data.output["rgb"][0].detach().cpu().numpy()
        print("rgb min/max:", rgb.min(), rgb.max())
        np.save("/tmp/wrist_camera_rgb.npy", rgb)
        print("saved: /tmp/wrist_camera_rgb.npy")

    if "distance_to_image_plane" in cam.data.output:
        depth = cam.data.output["distance_to_image_plane"][0].detach().cpu().numpy()
        print("depth min/max:", np.nanmin(depth), np.nanmax(depth))
        np.save("/tmp/wrist_camera_depth.npy", depth)
        print("saved: /tmp/wrist_camera_depth.npy")

    print("====================================")

    env.close()


if __name__ == "__main__":
    main()
    simulation_app.close()