# 🚊 자율주행 철도 점검 로봇 시스템 (Autonomous Railway Inspection Robot System)

본 프로젝트는 철도 선로의 결함 및 장애물을 실시간으로 감지하여 유지보수 효율성을 극대화하고 사고를 예방하는 자율주행 로봇 시스템입니다.

---

## 1. 프로젝트 개요 (Project Overview)
* **개발 기간**: 20XX.XX ~ 20XX.XX (졸업 프로젝트)
* **개발 목적**: 선로 점검 인력의 안전 확보 및 결함 감지 자동화를 통한 철도 유지보수 비용 절감
* **주요 역할**: 자율주행 알고리즘 설계, LiDAR & Camera 센서 퓨전 구현, 로봇 제어 시스템 최적화

---

## 2. 사용 기술 스택 (Tech Stack)
* **OS & Middleware**: Ubuntu 20.04 LTS, ROS2 (Foxy)
* **Languages**: C++, Python
* **Sensors**: Velodyne 3D LiDAR, RealSense Depth Camera, IMU, GPS
* **Control & Embedded**: Jetson Xavier NX, STM32 MCU
* **AI/CV**: YOLOv8, OpenCV, PyTorch

---

## 3. 하드웨어/소프트웨어 시스템 아키텍처 (System Architecture)

### Hardware Architecture
```text
[Sensors (LiDAR, Camera, IMU)] ──> [Jetson Xavier NX (Main Computer)] ──> [STM32 (Motor Control)] ──> [BLDC Motors]
                                      │
                                      └──> [LTE Module] ──> [Control Center Web Dashboard]
```

### Software Architecture (ROS2 Nodes)
* **/sensors_node**: LiDAR 점구름(Point Cloud) 및 카메라 이미지 데이터 발행(Publish)
* **/perception_node**: YOLOv8 기반 결함/장애물 감지 및 LiDAR 퓨전을 통한 거리 측정
* **/navigation_node**: Nav2 기반 선로 추종 주행 경로(Path Planning) 및 SLAM 지도 생성
* **/control_node**: 모터 제어 명령(Twist)을 STM32로 Serial 통신 송신

---

## 4. 핵심 기능 및 구현 내용 (Core Features)
* **센서 퓨전 기반 정밀 장애물 감지**: LiDAR의 3D 공간 데이터와 카메라의 2D 객체 인식 데이터를 매핑하여 오차 3cm 이내로 장애물 위치를 측정
* **실시간 선로 결함 진단**: YOLOv8 모델을 경량화(TensorRT 적용)하여 Jetson 보드에서 선로 크랙 및 체결구 이탈을 실시간(30 FPS 이상) 진단
* **자율 선로 추종 주행**: 카메라 이미지 차선 감지 알고리즘과 LiDAR 3D 맵을 결합하여 갈림길 및 곡선 구간에서 안정적인 자율주행 구현
* **원격 모니터링 대시보드**: ROS2 토픽을 WebRTC 및 WebSocket을 통해 중앙 관제 센터 대시보드로 실시간 영상 및 결함 로그 전송

---

## 5. 엔지니어링 이슈 및 Troubleshooting
### [이슈] Jetson Xavier NX 보드에서의 딥러닝 모델 연산 지연 및 실시간성 저하
* **현상**: 이미지 기반 객체 검출(YOLO)과 3D LiDAR 포인트클라우드 처리를 동시에 수행할 때 ROS2 노드의 프레임 드롭 발생 (약 8~10 FPS로 저하).
* **원인 분석**: 딥러닝 모델의 파라미터 수가 많아 GPU 메모리 병목 및 CPU-GPU 간 데이터 전송 지연 발생.
* **해결 방법**: 
  1. PyTorch 모델을 **TensorRT FP16 양자화(Quantization)** 포맷으로 변환하여 추론 속도를 대폭 개선.
  2. 불필요한 이미지 픽셀 영역을 자르고(ROI 설정), 3D LiDAR 포인트클라우드 데이터를 **Voxel Grid Filter**를 통해 다운샘플링하여 연산 부하 축소.
* **결과**: 추론 성능이 **32 FPS**로 향상되었으며, 지연 시간(Latency)을 120ms에서 **35ms**로 단축하여 실시간 안전 제어 주행 규격을 만족함.
