# Copyright (c) 2022-2026, The Isaac Lab Project Developers.
# All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause

"""M0609 joint-position-control lift environment configuration.

Suction-gripper version:
- Uses only M0609 arm joints as actions.
- Removes RG2 gripper joint action because the suction gripper has no driven finger joints.
- Uses suction_tcp as the end-effector frame.
"""

from isaaclab.assets import RigidObjectCfg
from isaaclab.markers.config import FRAME_MARKER_CFG
from isaaclab.sensors import FrameTransformerCfg
from isaaclab.sensors.frame_transformer.frame_transformer_cfg import OffsetCfg
from isaaclab.sim.schemas.schemas_cfg import RigidBodyPropertiesCfg
from isaaclab.sim.spawners.from_files.from_files_cfg import UsdFileCfg
from isaaclab.utils import configclass
from isaaclab.utils.assets import ISAAC_NUCLEUS_DIR

from . import mdp
from .doosan import DOOSAN_M0609_RG2_LIFT_CFG, EE_BODY_NAME
from .lift_env_cfg import LiftEnvCfg
from isaaclab.sensors import CameraCfg

BOX_USD_PATH = "/home/rokey/dev_ws/issac_sim/assets/box_aruco2.usd"

@configclass
class M0609LiftEnvCfg(LiftEnvCfg):
    """Full-training env: 4096 envs, obs corruption on."""

    def __post_init__(self):
        super().__post_init__()

        # ------------------------------------------------------------------ #
        # Robot
        # ------------------------------------------------------------------ #
        self.scene.robot = DOOSAN_M0609_RG2_LIFT_CFG.replace(
            prim_path="{ENV_REGEX_NS}/Robot"
        )

        # ------------------------------------------------------------------ #
        # Actions — 6-dim arm only
        # ------------------------------------------------------------------ #
        self.actions.arm_action = mdp.JointPositionActionCfg(
            asset_name="robot",
            joint_names=["joint_[1-6]"],
            scale=0.5,
            use_default_offset=True,
        )

        # Suction gripper has no driven finger joints.
        # Keep gripper_action disabled.
        self.actions.gripper_action = None

        # ------------------------------------------------------------------ #
        # Command: target pose body
        # ------------------------------------------------------------------ #
        # EE_BODY_NAME should be "suction_tcp" in doosan.py.
        self.commands.object_pose.body_name = EE_BODY_NAME

        # ------------------------------------------------------------------ #
        # Object — DexCube scaled to ~0.04m
        # ------------------------------------------------------------------ #
        self.scene.object = RigidObjectCfg(
            prim_path="{ENV_REGEX_NS}/Object",
            init_state=RigidObjectCfg.InitialStateCfg(
                # 박스 초기 위치.
                # z는 박스가 테이블 위에 살짝 올라오도록 조정 필요.
                pos=[-1.0, 0.1, 0.0],

                # 일단 USD에서 이미 눕힌 상태로 저장했다면 회전은 그대로 둔다.
                rot=[1.0, 0.0, 0.0, 0.0],
            ),
            spawn=UsdFileCfg(
                usd_path=BOX_USD_PATH,

                # box1.usd 자체 크기가 이미 맞으면 scale은 1.0 유지.
                scale=(0.3, 0.3, 0.3),

                rigid_props=RigidBodyPropertiesCfg(
                    solver_position_iteration_count=16,
                    solver_velocity_iteration_count=1,
                    max_angular_velocity=1000.0,
                    max_linear_velocity=1000.0,
                    max_depenetration_velocity=5.0,
                    disable_gravity=False,
                ),
            ),
        )

        # ------------------------------------------------------------------ #
        # EE frame — suction_tcp
        # ------------------------------------------------------------------ #
        marker_cfg = FRAME_MARKER_CFG.copy()
        marker_cfg.markers["frame"].scale = (0.1, 0.1, 0.1)
        marker_cfg.prim_path = "/Visuals/FrameTransformer"

        self.scene.ee_frame = FrameTransformerCfg(
            prim_path="{ENV_REGEX_NS}/Robot/Xform/m0609_suction_gripper/base_link",
            debug_vis=False,
            visualizer_cfg=marker_cfg,
            target_frames=[
                FrameTransformerCfg.FrameCfg(
                    prim_path=f"{{ENV_REGEX_NS}}/Robot/Xform/m0609_suction_gripper/{EE_BODY_NAME}",
                    name="end_effector",
                    offset=OffsetCfg(pos=[0.0, 0.0, 0.0]),
                ),
            ],
        )

        # ------------------------------------------------------------------ #
        # Wrist camera — RealSense D455 depth camera
        # ------------------------------------------------------------------ #
        self.scene.wrist_camera = CameraCfg(
            prim_path="{ENV_REGEX_NS}/Robot/Xform/m0609_suction_gripper/gripper_body/realsense_d455/RSD455/Camera_Pseudo_Depth",
            update_period=0.05,
            height=240,
            width=320,
            data_types=["rgb", "distance_to_image_plane"],
            spawn=None,
        )


@configclass
class M0609LiftEnvCfg_PLAY(M0609LiftEnvCfg):
    """Play variant: 50 envs, no obs noise."""

    def __post_init__(self):
        super().__post_init__()
        self.scene.num_envs = 50
        self.scene.env_spacing = 2.5
        self.observations.policy.enable_corruption = False
