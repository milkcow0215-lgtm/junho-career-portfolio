# Copyright (c) 2022-2026, The Isaac Lab Project Developers.
# All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause

"""Abstract LiftEnvCfg for the M0609 suction lift task."""

from dataclasses import MISSING

import isaaclab.sim as sim_utils
from isaaclab.assets import ArticulationCfg, AssetBaseCfg, RigidObjectCfg
from isaaclab.envs import ManagerBasedRLEnvCfg
from isaaclab.managers import CurriculumTermCfg as CurrTerm
from isaaclab.managers import EventTermCfg as EventTerm
from isaaclab.managers import ObservationGroupCfg as ObsGroup
from isaaclab.managers import ObservationTermCfg as ObsTerm
from isaaclab.managers import RewardTermCfg as RewTerm
from isaaclab.managers import SceneEntityCfg
from isaaclab.managers import TerminationTermCfg as DoneTerm
from isaaclab.scene import InteractiveSceneCfg
from isaaclab.sensors.frame_transformer.frame_transformer_cfg import FrameTransformerCfg
from isaaclab.sim.spawners.from_files.from_files_cfg import GroundPlaneCfg, UsdFileCfg
from isaaclab.utils import configclass
from isaaclab.utils.assets import ISAAC_NUCLEUS_DIR

from . import mdp


@configclass
class ObjectTableSceneCfg(InteractiveSceneCfg):
    robot: ArticulationCfg = MISSING
    ee_frame: FrameTransformerCfg = MISSING
    object: RigidObjectCfg = MISSING

    # Table is used as the visual/physical working surface.
    # Robot base is spawned at the same x/y position in doosan.py.
    table = AssetBaseCfg(
        prim_path="{ENV_REGEX_NS}/Table",
        init_state=AssetBaseCfg.InitialStateCfg(
            pos=[-0.9, 0.0, 0.0],
            rot=[0.707, 0.0, 0.0, 0.707],
        ),
        spawn=UsdFileCfg(
            usd_path=f"{ISAAC_NUCLEUS_DIR}/Props/Mounts/SeattleLabTable/table_instanceable.usd"
        ),
    )

    # Keep the ground below the table.  The table top is treated as z=0.
    plane = AssetBaseCfg(
        prim_path="/World/GroundPlane",
        init_state=AssetBaseCfg.InitialStateCfg(pos=[0.0, 0.0, -0.9]),
        spawn=GroundPlaneCfg(),
    )

    light = AssetBaseCfg(
        prim_path="/World/light",
        spawn=sim_utils.DomeLightCfg(color=(0.75, 0.75, 0.75), intensity=3000.0),
    )


@configclass
class CommandsCfg:
    """Pose command terms."""

    object_pose = mdp.UniformPoseCommandCfg(
        asset_name="robot",
        body_name=MISSING,
        resampling_time_range=(6.0, 6.0),
        debug_vis=False,
        ranges=mdp.UniformPoseCommandCfg.Ranges(
            # Command ranges are in robot-root frame.
            # Robot base: world x=-0.9
            # Cube init:  world x=-1.2
            # Therefore cube is roughly x=-0.3 in robot-root frame.
            pos_x=(-0.65, -0.45),
            pos_y=(-0.15, 0.15),
            pos_z=(0.15, 0.35),
            roll=(0.0, 0.0),
            pitch=(0.0, 0.0),
            yaw=(0.0, 0.0),
        ),
    )


@configclass
class ActionsCfg:
    """Action specs; filled in by concrete env cfg."""

    arm_action: mdp.JointPositionActionCfg | mdp.DifferentialInverseKinematicsActionCfg = MISSING
    gripper_action: mdp.BinaryJointPositionActionCfg | None = None


@configclass
class ObservationsCfg:
    """Single policy observation group."""

    @configclass
    class PolicyCfg(ObsGroup):
        joint_pos = ObsTerm(func=mdp.joint_pos_rel)  # 6 arm joints
        joint_vel = ObsTerm(func=mdp.joint_vel_rel)
        object_position = ObsTerm(func=mdp.object_position_in_robot_root_frame_ext)
        target_object_position = ObsTerm(
            func=mdp.generated_commands,
            params={"command_name": "object_pose"},
        )
        actions = ObsTerm(func=mdp.last_action)  # 6 arm actions

        def __post_init__(self):
            self.enable_corruption = True
            self.concatenate_terms = True

    policy: PolicyCfg = PolicyCfg()


@configclass
class EventCfg:
    """Reset and suction events."""

    reset_all = EventTerm(func=mdp.reset_scene_to_default, mode="reset")

    reset_object_position = EventTerm(
        func=mdp.reset_root_state_uniform,
        mode="reset",
        params={
            # Start with small randomization around cube init position.
            "pose_range": {"x": (-0.04, 0.04), "y": (-0.10, 0.10), "z": (0.0, 0.0)},
            "velocity_range": {},
            # "asset_cfg": SceneEntityCfg("object", body_names="Object"),
            "asset_cfg": SceneEntityCfg("object", body_names="box1"),
        },
    )

    reset_suction = EventTerm(
        func=mdp.reset_suction_state,
        mode="reset",
    )

    suction_attach = EventTerm(
        func=mdp.update_suction_attachment,
        mode="interval",
        interval_range_s=(0.01, 0.01),
        params={
            "threshold": 0.2,
            "attach_offset_z": -0.075,
        },
    )


@configclass
class RewardsCfg:
    """Reward terms — Franka-lift recipe baseline."""

    reaching_object = RewTerm(
        func=mdp.object_ee_distance,
        params={"std": 0.1},
        weight=1.0,
    )

    lifting_object = RewTerm(
        func=mdp.object_is_lifted,
        params={"minimal_height": 0.04},
        weight=15.0,
    )

    object_goal_tracking = RewTerm(
        func=mdp.object_goal_distance,
        params={"std": 0.3, "minimal_height": 0.04, "command_name": "object_pose"},
        weight=16.0,
    )

    object_goal_tracking_fine_grained = RewTerm(
        func=mdp.object_goal_distance,
        params={"std": 0.05, "minimal_height": 0.04, "command_name": "object_pose"},
        weight=5.0,
    )

    dropping_penalty = RewTerm(
        func=mdp.is_terminated_term,
        params={"term_keys": "object_dropping"},
        weight=-5.0,
    )

    action_rate = RewTerm(func=mdp.action_rate_l2, weight=-1e-4)

    joint_vel = RewTerm(
        func=mdp.joint_vel_l2,
        weight=-1e-4,
        params={"asset_cfg": SceneEntityCfg("robot")},
    )


@configclass
class TerminationsCfg:
    """Termination conditions."""

    time_out = DoneTerm(func=mdp.time_out, time_out=True)

    object_dropping = DoneTerm(
        func=mdp.root_height_below_minimum,
        params={"minimum_height": -0.05, "asset_cfg": SceneEntityCfg("object")},
    )


@configclass
class CurriculumCfg:
    """Curriculum terms."""

    action_rate = CurrTerm(
        func=mdp.modify_reward_weight,
        params={"term_name": "action_rate", "weight": -1e-2, "num_steps": 50_000_000},
    )

    joint_vel = CurrTerm(
        func=mdp.modify_reward_weight,
        params={"term_name": "joint_vel", "weight": -1e-2, "num_steps": 50_000_000},
    )

    dropping_penalty = CurrTerm(
        func=mdp.modify_reward_weight,
        params={"term_name": "dropping_penalty", "weight": -10.0, "num_steps": 30_000_000},
    )


@configclass
class LiftEnvCfg(ManagerBasedRLEnvCfg):
    """Abstract lift environment configuration for M0609."""

    scene: ObjectTableSceneCfg = ObjectTableSceneCfg(num_envs=4096, env_spacing=2.5)
    observations: ObservationsCfg = ObservationsCfg()
    actions: ActionsCfg = ActionsCfg()
    commands: CommandsCfg = CommandsCfg()
    rewards: RewardsCfg = RewardsCfg()
    terminations: TerminationsCfg = TerminationsCfg()
    events: EventCfg = EventCfg()
    curriculum: CurriculumCfg = CurriculumCfg()

    def __post_init__(self):
        self.decimation = 2
        self.episode_length_s = 5.0
        self.sim.dt = 0.01
        self.sim.render_interval = self.decimation
        self.sim.physx.bounce_threshold_velocity = 0.01
        self.sim.physx.gpu_found_lost_aggregate_pairs_capacity = 1024 * 1024 * 4
        self.sim.physx.gpu_total_aggregate_pairs_capacity = 16 * 1024
        self.sim.physx.friction_correlation_distance = 0.00625
