# generate_aruco.py
import cv2
import numpy as np
import os
# Dictionary 선택: 6x6 비트 패턴, 최대 250개 ID, 검출 안정성 양호
aruco_dict = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_6X6_250)

MARKER_ID = 0
MARKER_PX = 600# 마커 본체 해상도
QUIET_ZONE_PX = 60# 흰색 여백 (검출 안정성에 중요)
# 마커 본체 생성

marker = cv2.aruco.generateImageMarker(aruco_dict, MARKER_ID, MARKER_PX)

OUT_DIR = os.path.expanduser("~/dev_ws/issac_sim/aruco_marker_6x6")
os.makedirs(OUT_DIR, exist_ok=True)
for id in range(10):
    MARKER_ID = id

    # 마커 본체 생성
    marker = cv2.aruco.generateImageMarker(aruco_dict, MARKER_ID, MARKER_PX)
    
    # 흰 여백을 더해 최종 텍스처 이미지 만들기
    total = MARKER_PX + 2 * QUIET_ZONE_PX
    img = np.full((total, total), 255, dtype=np.uint8)
    img[QUIET_ZONE_PX:QUIET_ZONE_PX + MARKER_PX, QUIET_ZONE_PX:QUIET_ZONE_PX + MARKER_PX] = marker

    path = os.path.join(OUT_DIR, f"aruco_id{MARKER_ID}.png")
    cv2.imwrite(path, img)
    print(f"saved aruco_id{MARKER_ID}.png ({total}x{total})")