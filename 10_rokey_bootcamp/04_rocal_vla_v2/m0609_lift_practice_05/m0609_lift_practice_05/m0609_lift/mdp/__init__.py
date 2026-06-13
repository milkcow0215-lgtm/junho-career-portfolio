# Copyright (c) 2022-2026, The Isaac Lab Project Developers.
# All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause

"""Re-exports the upstream lift-task MDP functions (claude_rl.md §5).

This thin shim lets m0609_lift modules do ``from . import mdp`` and access
all of ``isaaclab_tasks.manager_based.manipulation.lift.mdp`` without
modifying upstream files.
"""

from isaaclab_tasks.manager_based.manipulation.lift.mdp import *  # noqa: F401, F403
from .rewards import gripper_close_near_object  # noqa: F401

from .suction import reset_suction_state, update_suction_attachment  # noqa: F401
from .perception import (
    get_box_pose_w,
    object_position_in_robot_root_frame_ext,
    set_box_pose_from_perception,
)  # noqa: F401