from __future__ import annotations

import torch

from .perception import get_box_pose_w


def _get_num_envs(env) -> int:
    """Return number of parallel environments."""
    if hasattr(env, "num_envs"):
        return env.num_envs
    return env.scene.num_envs


def _get_device(env):
    """Return simulation device."""
    if hasattr(env, "device"):
        return env.device
    return env.scene.device


def _ensure_suction_buffers(env):
    """Create suction state buffers lazily."""
    num_envs = _get_num_envs(env)
    device = _get_device(env)

    if not hasattr(env, "suction_attached"):
        env.suction_attached = torch.zeros(
            num_envs,
            dtype=torch.bool,
            device=device,
        )


def reset_suction_state(env, env_ids: torch.Tensor | None):
    """
    Reset suction attachment state.

    EventTerm calls this with:
        env, env_ids
    """

    _ensure_suction_buffers(env)

    if env_ids is None:
        env.suction_attached[:] = False
    else:
        env.suction_attached[env_ids] = False


def update_suction_attachment(
    env,
    env_ids: torch.Tensor | None,
    threshold: float = 0.035,
    attach_offset_z: float = -0.025,
):
    """
    Simplified suction model for Isaac Lab RL.

    Behavior:
    1. If suction_tcp is close enough to the box pose, mark the object as attached.
    2. Once attached, force the real sim object root pose to follow suction_tcp.
    3. Object velocity is zeroed while attached.
    """

    _ensure_suction_buffers(env)

    obj = env.scene["object"]
    ee_frame = env.scene["ee_frame"]

    num_envs = _get_num_envs(env)
    device = _get_device(env)

    if env_ids is None:
        env_ids = torch.arange(num_envs, device=device)

    # target frame 0 = "end_effector" = suction_tcp
    ee_pos_w = ee_frame.data.target_pos_w[:, 0, :]
    ee_quat_w = ee_frame.data.target_quat_w[:, 0, :]

    # 현재는 sim ground-truth, 나중에는 RGB-D/QR pose로 교체 가능한 통합 pose provider
    box_pos_w, _ = get_box_pose_w(env)

    # 선택된 env들에 대해서만 거리 검사
    dist = torch.norm(ee_pos_w[env_ids] - box_pos_w[env_ids], dim=-1)

    newly_attached_local = dist < threshold
    newly_attached_env_ids = env_ids[newly_attached_local]

    if newly_attached_env_ids.numel() > 0:
        env.suction_attached[newly_attached_env_ids] = True

    attached_ids = env.suction_attached.nonzero(as_tuple=False).squeeze(-1)

    if attached_ids.numel() == 0:
        return

    # 실제 sim object root state 복사 후, 붙은 env만 갱신
    new_root_state = obj.data.root_state_w.clone()

    new_obj_pos_w = ee_pos_w.clone()
    new_obj_pos_w[:, 2] += attach_offset_z

    new_root_state[attached_ids, 0:3] = new_obj_pos_w[attached_ids]
    new_root_state[attached_ids, 3:7] = ee_quat_w[attached_ids]

    # 붙어 있는 동안 선속도/각속도 제거
    new_root_state[attached_ids, 7:13] = 0.0

    obj.write_root_state_to_sim(
        new_root_state[attached_ids],
        env_ids=attached_ids,
    )