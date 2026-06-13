from __future__ import annotations

import cv2
import numpy as np
import torch
from isaaclab.utils.math import quat_apply, quat_mul


def _get_num_envs(env) -> int:
    if hasattr(env, "num_envs"):
        return env.num_envs
    return env.scene.num_envs


def _get_device(env):
    if hasattr(env, "device"):
        return env.device
    return env.scene.device


def _ensure_perception_buffers(env):
    """
    Future RGB-D / QR pose input buffer.

    box_pos_w_from_perception:
        camera/QR로 추정한 box position in world frame

    box_quat_w_from_perception:
        camera/QR로 추정한 box orientation in world frame

    use_perception_pose:
        False면 sim ground-truth 사용
        True면 perception buffer 사용
    """
    num_envs = _get_num_envs(env)
    device = _get_device(env)

    if not hasattr(env, "box_pos_w_from_perception"):
        env.box_pos_w_from_perception = torch.zeros(
            num_envs, 3, dtype=torch.float32, device=device
        )

    if not hasattr(env, "box_quat_w_from_perception"):
        env.box_quat_w_from_perception = torch.zeros(
            num_envs, 4, dtype=torch.float32, device=device
        )
        env.box_quat_w_from_perception[:, 0] = 1.0

    if not hasattr(env, "use_perception_pose"):
        env.use_perception_pose = False


def set_box_pose_from_perception(env, box_pos_w: torch.Tensor, box_quat_w: torch.Tensor, env_ids=None):
    """
    Later hook for RGB-D / QR detector.

    box_pos_w:
        shape = (N, 3)

    box_quat_w:
        shape = (N, 4), wxyz
    """
    _ensure_perception_buffers(env)

    if env_ids is None:
        env.box_pos_w_from_perception[:] = box_pos_w
        env.box_quat_w_from_perception[:] = box_quat_w
    else:
        env.box_pos_w_from_perception[env_ids] = box_pos_w
        env.box_quat_w_from_perception[env_ids] = box_quat_w

    env.use_perception_pose = True


def get_box_pose_w(env):
    """
    Unified box pose provider.

    현재 학습:
        sim object ground-truth pose 반환

    나중에 RGB-D/QR 연결:
        env.use_perception_pose = True이면 perception pose 반환
    """
    _ensure_perception_buffers(env)

    obj = env.scene["object"]

    if env.use_perception_pose:
        return env.box_pos_w_from_perception, env.box_quat_w_from_perception

    return obj.data.root_pos_w, obj.data.root_quat_w


def object_position_in_robot_root_frame_ext(env):
    """
    Policy observation용 object position.

    기존 mdp.object_position_in_robot_root_frame을 바로 쓰지 않고,
    나중에 perception pose로 바꿔도 observation 구조가 유지되도록 만든 함수.
    """
    box_pos_w, _ = get_box_pose_w(env)

    robot = env.scene["robot"]
    robot_root_pos_w = robot.data.root_pos_w

    return box_pos_w - robot_root_pos_w


# [캘리브레이션] 손목 TCP 중심에서 카메라 렌즈 중심까지의 고정된 Offset
EE_TO_CAMERA_OFFSET_POS = [0.0, 0.0, 0.0]  # 필요시 실제 물리적 오프셋 대입 (m)
EE_TO_CAMERA_OFFSET_QUAT = [1.0, 0.0, 0.0, 0.0]  # [w, x, y, z]


def update_aruco_perception_pose(env):
    """
    매 스텝마다 실행되어 모든 병렬 환경(num_envs)의 카메라 이미지를 기반으로
    ArUco 마커를 탐지하고, 보정된 3D 월드 좌표를 계산하여 버퍼에 실시간 업데이트합니다.
    """
    _ensure_perception_buffers(env)
    
    num_envs = _get_num_envs(env)
    device = _get_device(env)
    cam = env.scene["wrist_camera"]
    ee_frame = env.scene["ee_frame"]
    
    # 1. 센서 버퍼 데이터 가져오기 (전체 환경 대상)
    rgb_tensors = cam.data.output["rgb"]  # Shape: (N, H, W, 4) 또는 (N, H, W, 3)
    depth_tensors = cam.data.output["distance_to_image_plane"]  # Shape: (N, H, W, 1)
    intrinsic_matrices = cam.data.intrinsic_matrices  # Shape: (N, 3, 3)
    
    # 2. 로봇 손목 및 카메라 쿼터니언 정보 가져오기
    ee_pos_w = ee_frame.data.target_pos_w[:, 0]     # (N, 3)
    ee_quat_w = ee_frame.data.target_quat_w[:, 0]   # (N, 4)
    
    if hasattr(cam.data, "quat_w_ros"):
        final_cam_quat = cam.data.quat_w_ros  # (N, 4)
    else:
        # 내장 quat_w_ros가 없을 경우 손목 포즈와 오프셋 결합
        offset_quat = torch.tensor(EE_TO_CAMERA_OFFSET_QUAT, device=device, dtype=torch.float32).repeat(num_envs, 1)
        final_cam_quat = quat_mul(ee_quat_w, offset_quat)

    offset_pos = torch.tensor(EE_TO_CAMERA_OFFSET_POS, device=device, dtype=torch.float32).repeat(num_envs, 1)
    cam_pos_w = ee_pos_w + quat_apply(ee_quat_w, offset_pos)

    # ArUco 디텍터 설정
    dictionary = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_6X6_250)
    detector = cv2.aruco.ArucoDetector(dictionary, cv2.aruco.DetectorParameters())

    # 결과를 담을 임시 텐서
    updated_pos_w = env.box_pos_w_from_perception.clone()

    # 3. OpenCV 이미지 처리는 환경 개수(N)만큼 루프를 돌며 타겟 마커 픽셀 추출
    for env_id in range(num_envs):
        # 텐서를 uint8 numpy 이미지로 변환
        rgb_np = rgb_tensors[env_id].detach().cpu().numpy()
        if rgb_np.shape[-1] == 4:
            rgb_np = rgb_np[..., :3]
        if rgb_np.max() <= 1.0:
            rgb_np = (rgb_np * 255).astype(np.uint8)
        else:
            rgb_np = rgb_np.astype(np.uint8)
            
        gray = cv2.cvtColor(rgb_np, cv2.COLOR_RGB2GRAY)
        corners, ids, _ = detector.detectMarkers(gray)
        
        # 타겟 마커(ID=0)가 정상 검출되었을 때만 3D 복원 진행
        if ids is not None and 0 in ids.flatten():
            idx = np.where(ids.flatten() == 0)[0][0]
            pts = corners[idx].reshape(4, 2)
            u, v = int(pts[:, 0].mean()), int(pts[:, 1].mean())
            
            # 뎁스 맵에서 중심부 중간값(Median) 추출
            depth_np = depth_tensors[env_id].squeeze().detach().cpu().numpy()
            h, w = depth_np.shape[:2]
            r = 3  # patch size 7x7
            patch = depth_np[max(v-r, 0):min(v+r+1, h), max(u-r, 0):min(u+r+1, w)]
            valid = patch[np.isfinite(patch)]
            valid = valid[valid > 0]
            
            if len(valid) > 0:
                depth_val = np.median(valid)
                
                # 인트린직 기반 카메라 프레임 3D 좌표 복원 (ROS Optical Frame)
                K = intrinsic_matrices[env_id]
                z_c = float(depth_val)
                x_c = (float(u) - float(K[0, 2])) * z_c / float(K[0, 0])
                y_c = (float(v) - float(K[1, 2])) * z_c / float(K[1, 1])
                
                p_cam_ros = torch.tensor([x_c, y_c, z_c], device=device, dtype=torch.float32)
                
                # 4. 🔥 우리가 검증한 내장 유틸 행렬곱으로 월드 좌표 변환 및 저장
                p_world = cam_pos_w[env_id] + quat_apply(final_cam_quat[env_id].unsqueeze(0), p_cam_ros.unsqueeze(0)).squeeze(0)
                updated_pos_w[env_id] = p_world

    # 5. 최종 보정된 위치를 버퍼에 덮어쓰고, Perception 모드를 활성화(True) 시킵니다.
    env.box_pos_w_from_perception[:] = updated_pos_w
    # 마커가 안 보일 때는 이전 프레임의 위치를 유지하도록 쿼터니언은 기본값 유지 혹은 ground-truth 추종 가능
    env.box_quat_w_from_perception[:] = env.scene["object"].data.root_quat_w
    
    env.use_perception_pose = True
# perception.py 맨 밑에 검증용 로그 심기
    print("==========================================")
    print("[실시간 아르코 버퍼 갱신 검증]")
    print(f"현재 0번 환경 마커 추정 좌표: {env.box_pos_w_from_perception[0].detach().cpu().numpy()}")
    print(f"실제 시뮬레이션 상자 절대 좌표: {env.scene['object'].data.root_pos_w[0].detach().cpu().numpy()}")
    print("==========================================")

    # 확인 후 코드가 계속 실행되서 터미널이 올라가버리는걸 막기 위해 강제 종료 시그널
    import sys; sys.exit("[확인 완료] 첫 스텝 버퍼가 성공적으로 찍혀 프로세스를 종료합니다.")
