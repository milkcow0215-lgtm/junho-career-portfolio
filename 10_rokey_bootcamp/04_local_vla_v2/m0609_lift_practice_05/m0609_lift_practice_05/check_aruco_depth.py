from __future__ import annotations

import argparse
import os
import sys

THIS_DIR = os.path.dirname(os.path.abspath(__file__))
if THIS_DIR not in sys.path:
    sys.path.insert(0, THIS_DIR)

from isaaclab.app import AppLauncher

parser = argparse.ArgumentParser(description="Check ArUco marker from wrist camera with formal calibration.")
parser.add_argument("--task", type=str, default="My_Isaac-M0609-Play-v0")
parser.add_argument("--num_envs", type=int, default=1)
parser.add_argument("--agent", type=str, default="rsl_rl_cfg_entry_point")

AppLauncher.add_app_launcher_args(parser)
args_cli, hydra_args = parser.parse_known_args()
sys.argv = [sys.argv[0]] + hydra_args

app_launcher = AppLauncher(args_cli)
simulation_app = app_launcher.app

import cv2
import gymnasium as gym
import numpy as np
import torch

import isaaclab_tasks  # noqa: F401
import m0609_lift  # noqa: F401

from isaaclab.envs import ManagerBasedRLEnvCfg
from isaaclab_tasks.utils.hydra import hydra_task_config
from isaaclab.utils.math import quat_apply, quat_rotate, quat_mul

from pxr import UsdGeom
import omni.usd


# ======================================================================
# User settings & Calibration Parameters
# ======================================================================

TARGET_ARUCO_ID = 0
ARUCO_DICT = cv2.aruco.DICT_6X6_250

CAMERA_PRIM_PATH = (
    "/World/envs/env_0/Robot/Xform/m0609_suction_gripper/"
    "gripper_body/realsense_d455/RSD455/Camera_Pseudo_Depth"
)

# [중요] 손목(ee_frame TCP) 중심에서 카메라 렌즈 중심까지의 고정된 Offset (캘리브레이션용)
# 만약 필요하다면 실제 로봇 설계값이나 USD Stage 값을 대입하세요. 기본값은 0 오프셋입니다.
EE_TO_CAMERA_OFFSET_POS = [0.0, 0.0, 0.0]  # [x, y, z] in meters
EE_TO_CAMERA_OFFSET_QUAT = [1.0, 0.0, 0.0, 0.0]  # [w, x, y, z]

ARUCO_CANDIDATE_PATHS = [
    "/World/envs/env_0/Object/box1/aruco",
    "/World/envs/env_0/Object/box1/aruco/Plane",
    "/World/envs/env_0/Object/aruco",
    "/World/envs/env_0/Object/aruco/Plane",
]

OBJECT_CANDIDATE_PATHS = [
    "/World/envs/env_0/Object",
    "/World/envs/env_0/Object/box1",
    "/World/envs/env_0/Object/SM_CardBox_A_01",
]

DEBUG_IMAGE_PATH = "/tmp/aruco_debug.png"


# ======================================================================
# Utility functions
# ======================================================================

def to_uint8_rgb(rgb: torch.Tensor) -> np.ndarray:
    rgb_np = rgb.detach().cpu().numpy()
    if rgb_np.shape[-1] == 4:
        rgb_np = rgb_np[..., :3]
    if rgb_np.max() <= 1.0:
        rgb_np = (rgb_np * 255).astype(np.uint8)
    else:
        rgb_np = rgb_np.astype(np.uint8)
    return rgb_np


def get_depth_value(depth: torch.Tensor, u: int, v: int, patch_size: int = 7) -> float | None:
    depth_np = depth.detach().cpu().numpy()
    depth_np = np.squeeze(depth_np)

    h, w = depth_np.shape[:2]
    r = patch_size // 2

    u0 = max(u - r, 0)
    u1 = min(u + r + 1, w)
    v0 = max(v - r, 0)
    v1 = min(v + r + 1, h)

    patch = depth_np[v0:v1, u0:u1]
    valid = patch[np.isfinite(patch)]
    valid = valid[valid > 0]

    if len(valid) == 0:
        return None

    return float(np.median(valid))


def pixel_depth_to_camera_point(
    cam,
    u: int,
    v: int,
    depth_value: float,
    device: torch.device | str,
) -> torch.Tensor:
    """픽셀과 depth 데이터를 바탕으로 ROS Optical 프레임(X:우, Y:하, Z:전방) 기준 3D 좌표 복원"""
    K = cam.data.intrinsic_matrices[0]

    fx = K[0, 0]
    fy = K[1, 1]
    cx = K[0, 2]
    cy = K[1, 2]

    z = torch.tensor(depth_value, device=device, dtype=torch.float32)
    u_t = torch.tensor(float(u), device=device, dtype=torch.float32)
    v_t = torch.tensor(float(v), device=device, dtype=torch.float32)

    x = (u_t - cx) * z / fx
    y = (v_t - cy) * z / fy

    return torch.stack([x, y, z], dim=-1).unsqueeze(0)  # Shape: (1, 3)


def compute_calibrated_world_point(cam, raw_env, p_cam_ros: torch.Tensor, device: torch.device | str) -> torch.Tensor:
    """
    하드코딩 추정 없이, Isaac Lab 내장 변환 연산(quat_apply)을 활용해 
    정확하게 카메라 월드 행렬을 계산하여 3D 포인트를 월드 좌표계로 변환합니다.
    """
    # 1. 로봇 손목 프레임 정보 가져오기
    ee_frame = raw_env.scene["ee_frame"]
    ee_pos_w = ee_frame.data.target_pos_w[0, 0].unsqueeze(0)     # (1, 3)
    ee_quat_w = ee_frame.data.target_quat_w[0, 0].unsqueeze(0)   # (1, 4)

    # 2. 고정 오프셋 반영하여 카메라의 정확한 월드 포즈 계산
    offset_pos = torch.tensor(EE_TO_CAMERA_OFFSET_POS, device=device, dtype=torch.float32).unsqueeze(0)
    offset_quat = torch.tensor(EE_TO_CAMERA_OFFSET_QUAT, device=device, dtype=torch.float32).unsqueeze(0)

    # 카메라 월드 위치 = 손목 위치 + 손목 회전이 적용된 오프셋 거리
    cam_pos_w = ee_pos_w + quat_apply(ee_quat_w, offset_pos)
    # 카메라 월드 쿼터니언 = 손목 쿼터니언 * 오프셋 쿼터니언
    cam_quat_w = quat_mul(ee_quat_w, offset_quat)

    # 3. Isaac Lab의 카메라 센서가 바라보는 쿼터니언(quat_w_ros) 선택
    # 만약 데이터셋에 quat_w_ros가 있다면 이를 우선 사용
    if hasattr(cam.data, "quat_w_ros"):
        final_cam_quat = cam.data.quat_w_ros[0].unsqueeze(0)
    else:
        final_cam_quat = cam_quat_w

    # 4. 카메라 센서 월드 원점 기준 최종 3D 월드 좌표 계산
    p_world = cam_pos_w + quat_apply(final_cam_quat, p_cam_ros)
    return p_world


def get_usd_aruco_bbox_center(device: torch.device | str) -> torch.Tensor | None:
    stage = omni.usd.get_context().get_stage()
    bbox_cache = UsdGeom.BBoxCache(0, [UsdGeom.Tokens.default_, UsdGeom.Tokens.render], useExtentsHint=False)

    for path in ARUCO_CANDIDATE_PATHS:
        prim = stage.GetPrimAtPath(path)
        if not prim.IsValid():
            continue
        bound = bbox_cache.ComputeWorldBound(prim)
        aligned_range = bound.ComputeAlignedRange()
        center = aligned_range.GetMidpoint()
        return torch.tensor([[float(center[0]), float(center[1]), float(center[2])]], device=device, dtype=torch.float32)
    return None


# ======================================================================
# Main Pipeline
# ======================================================================

@hydra_task_config(args_cli.task, args_cli.agent)
def main(env_cfg: ManagerBasedRLEnvCfg, agent_cfg):
    env_cfg.scene.num_envs = args_cli.num_envs
    env = gym.make(args_cli.task, cfg=env_cfg)
    raw_env = env.unwrapped
    env.reset()

    device = raw_env.device
    num_envs = raw_env.num_envs
    act_dim = env.action_space.shape[-1]
    zero_action = torch.zeros((num_envs, act_dim), device=device)

    # 물리엔진 및 버퍼 갱신 대기
    for _ in range(30):
        env.step(zero_action)

    if "wrist_camera" not in raw_env.scene.keys() or "ee_frame" not in raw_env.scene.keys():
        print("[ERROR] scene 구성 요소 부족 (wrist_camera 혹은 ee_frame 없음)")
        env.close()
        return

    cam = raw_env.scene["wrist_camera"]
    usd_aruco_center = get_usd_aruco_bbox_center(device)

    rgb_tensor = cam.data.output["rgb"][0]
    depth_tensor = cam.data.output["distance_to_image_plane"][0]

    rgb = to_uint8_rgb(rgb_tensor)
    gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)

    detector = cv2.aruco.ArucoDetector(
        cv2.aruco.getPredefinedDictionary(ARUCO_DICT), 
        cv2.aruco.DetectorParameters()
    )
    corners, ids, rejected = detector.detectMarkers(gray)
    debug = rgb.copy()

    if ids is None:
        print("[ARUCO DEBUG] 마커 탐지 실패.")
        cv2.imwrite(DEBUG_IMAGE_PATH, cv2.cvtColor(debug, cv2.COLOR_RGB2BGR))
        env.close()
        return

    cv2.aruco.drawDetectedMarkers(debug, corners, ids)
    obj_pos_w = raw_env.scene["object"].data.root_pos_w[0].unsqueeze(0)

    for i, marker_id in enumerate(ids.flatten()):
        if int(marker_id) != TARGET_ARUCO_ID:
            continue

        pts = corners[i].reshape(4, 2)
        u, v = int(pts[:, 0].mean()), int(pts[:, 1].mean())
        depth_value = get_depth_value(depth_tensor, u, v, patch_size=7)

        if depth_value is None:
            print("[WARN] Depth 값이 유효하지 않습니다.")
            continue

        # 1. 카메라 프레임 포인트 추출
        p_cam = pixel_depth_to_camera_point(cam, u, v, depth_value, device)

        # 2. 빌트인 캘리브레이션 함수를 통한 월드 좌표 변환
        p_world = compute_calibrated_world_point(cam, raw_env, p_cam, device)

        print("====================================")
        print(f"[ARUCO MARKER FOUND] ID: {marker_id}")
        print(f"Center Pixel: u={u}, v={v} | Depth: {depth_value:.4f}m")
        print(f"Calculated World Point: {p_world[0].detach().cpu().numpy()}")
        
        if usd_aruco_center is not None:
            print(f"Actual USD BBox Center: {usd_aruco_center[0].detach().cpu().numpy()}")
            error = torch.norm(p_world - usd_aruco_center).item()
            print(f"🎯 최종 보정 위치 오차(Error): {error * 1000:.2f} mm")
        
        print(f"Distance to Target Object: {torch.norm(p_world - obj_pos_w).item():.4f}m")
        print("====================================")

        cv2.circle(debug, (u, v), 5, (255, 0, 0), -1)

    cv2.imwrite(DEBUG_IMAGE_PATH, cv2.cvtColor(debug, cv2.COLOR_RGB2BGR))
    env.close()

if __name__ == "__main__":
    main()
    simulation_app.close()