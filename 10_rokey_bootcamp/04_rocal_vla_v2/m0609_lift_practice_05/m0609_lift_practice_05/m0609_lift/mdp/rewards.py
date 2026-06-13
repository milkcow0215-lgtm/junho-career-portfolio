# Copyright (c) 2022-2026, The Isaac Lab Project Developers.
# All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause

"""Custom reward functions for the M0609 lift task."""

from __future__ import annotations

from typing import TYPE_CHECKING

import torch

from isaaclab.assets import RigidObject
from isaaclab.managers import SceneEntityCfg
from isaaclab.sensors import FrameTransformer

# 🔥 [변경] 우리가 수정한 perception 파일에서 실시간 버퍼 업데이트 및 좌표 획득 함수를 가져옵니다.
from .perception import update_aruco_perception_pose, get_box_pose_w

if TYPE_CHECKING:
    from isaaclab.envs import ManagerBasedRLEnv


def gripper_close_near_object(
    env: ManagerBasedRLEnv,
    std: float = 0.08,
    gripper_action_name: str = "gripper_action",
    object_cfg: SceneEntityCfg = SceneEntityCfg("object"),
    ee_frame_cfg: SceneEntityCfg = SceneEntityCfg("ee_frame"),
) -> torch.Tensor:
    """Reward commanding gripper-close while the EE is near the object (ArUco Marker base).

    Uses the policy's *action intent* (raw command from the BinaryJointAction
    term) instead of the realised finger joint position.  Reason: when the
    fingers stall against the cube during a clumsy grasp the actual finger_pos
    barely changes, so an "actual closure" reward would give zero feedback for
    a policy that *did* try to close.  Rewarding the intent decouples the
    learning signal from the contact dynamics and lets the policy discover
    "close gripper at the cube" even if the first attempts physically fail.

    BinaryJointAction convention: raw action < 0 → close, ≥ 0 → open.

    Args:
        std: Distance scale for the tanh proximity kernel (metres).
        gripper_action_name: Name of the gripper action term in ActionsCfg.
        object_cfg: Scene entity config for the target object.
        ee_frame_cfg: Scene entity config for the end-effector frame sensor.

    Returns:
        Reward in [0, 1]: high only when EE is close *and* policy commanded close.
    """
    # 🔥 [핵심 추가] 보상 함수가 호출되는 매 스텝마다 카메라 이미지를 분석해서 
    # ArUco 마커의 3D 월드 보정 좌표 버퍼를 실시간으로 업데이트합니다.
    update_aruco_perception_pose(env)

    ee_frame: FrameTransformer = env.scene[ee_frame_cfg.name]

    # 🔥 [변경] 시뮬레이터 좌표 대신, 
    # perception 버퍼에 저장된 ArUco 마커의 보정된 실시간 월드 좌표를 가져옵니다.
    cube_pos_w, _ = get_box_pose_w(env)
    
    ee_w = ee_frame.data.target_pos_w[..., 0, :]
    dist = torch.norm(cube_pos_w - ee_w, dim=1)

    proximity = 1.0 - torch.tanh(dist / std)

    gripper_term = env.action_manager.get_term(gripper_action_name)
    gripper_close_intent = (gripper_term.raw_actions[:, 0] < 0).float()

    return proximity * gripper_close_intent
