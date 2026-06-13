# Copyright (c) 2022-2026, The Isaac Lab Project Developers.
# All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause

"""
M0609 + suction gripper USD를 Isaac Lab lift task에서 사용하기 위한 ArticulationCfg 정의 파일.

현재 목적:
- amr_robot_light_test_2_1.usd 안의 로봇팔 + 흡착 그리퍼를 사용한다.
- 로봇팔을 테이블 위치에 맞춰 spawn한다.
- 흡착 그리퍼는 구동 joint가 없으므로 RG2용 gripper actuator를 사용하지 않는다.
"""

from __future__ import annotations

import isaaclab.sim as sim_utils
from isaaclab.actuators import ImplicitActuatorCfg
from isaaclab.assets.articulation import ArticulationCfg
from isaaclab.sim.spawners.from_files.from_files_cfg import UsdFileCfg


# =============================================================================
# 1. 로봇 상수 정의
# =============================================================================

# M0609 기본 홈 자세. 단위는 radian.
# joint_1 = pi 로 두어 팔이 테이블/큐브 방향을 보도록 시작한다.
HOME_POSE: tuple[float, ...] = (3.14159, 0.0, 1.5708, 0.0, 1.5708, 0.0)

# 흡착 그리퍼 USD에서 end-effector로 사용할 body/prim 이름.
EE_BODY_NAME = "suction_tcp"


# =============================================================================
# 2. USD 기반 로봇 ArticulationCfg 정의
# =============================================================================

ROBOT_USD_PATH = "/home/rokey/dev_ws/issac_sim/assets/Collected_exex/exex2.usd"

# 테이블이 lift_env_cfg.py에서 pos=[-0.9, 0, 0]로 생성되므로,
# 로봇 root도 같은 x/y 위치에 둔다.
# table_instanceable.usd의 상판 높이를 z=0으로 쓰는 현재 배치 기준이다.
ROBOT_BASE_POS: tuple[float, float, float] = (-0.6, 0.0, 0.0)


DOOSAN_M0609_RG2_LIFT_CFG = ArticulationCfg(
    spawn=UsdFileCfg(
        usd_path=ROBOT_USD_PATH,

        rigid_props=sim_utils.RigidBodyPropertiesCfg(
            disable_gravity=False,
            max_depenetration_velocity=5.0,
        ),

        articulation_props=sim_utils.ArticulationRootPropertiesCfg(
            fix_root_link=True,
            enabled_self_collisions=False,
            solver_position_iteration_count=12,
            solver_velocity_iteration_count=1,
        ),
    ),

    init_state=ArticulationCfg.InitialStateCfg(
        pos=ROBOT_BASE_POS,
        rot=(1.0, 0.0, 0.0, 0.0),

        joint_pos={
            "joint_1": HOME_POSE[0],
            "joint_2": HOME_POSE[1],
            "joint_3": HOME_POSE[2],
            "joint_4": HOME_POSE[3],
            "joint_5": HOME_POSE[4],
            "joint_6": HOME_POSE[5],
        },
    ),

    actuators={
        "m0609_arm": ImplicitActuatorCfg(
            joint_names_expr=["joint_[1-6]"],
            effort_limit_sim=9600.0,
            velocity_limit_sim=2.618,
            stiffness=3000.0,
            damping=200.0,
        ),
    },

    soft_joint_pos_limit_factor=1.0,
)
