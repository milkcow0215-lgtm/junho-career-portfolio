# 🚜 오라이 봇 
> 건설 현장 트럭 유도 시스템 (Construction Site Truck Guidance System)

본 프로젝트는 비정형 환경인 건설 현장에서 대형 트럭의 원활하고 안전한 진출입 및 하역 지점 유도를 위해 자율 모바일 로봇(TurtleBot4)을 테스트베드로 구축하고 차량 검출, 경로 유도 및 안전 주행 제어를 검증한 PM(Project Manager) 수행 프로젝트입니다.

---

## 1. 프로젝트 개요 (Project Overview)
* **개발 기간**: 20XX.XX ~ 20XX.XX
* **개발 목적**: 비정형/다이내믹 건설 현장에서 대형 트럭 운전자의 시야 사각지대 문제를 해결하고, 충돌 방지 및 안전한 주행 경로 가이드 라인을 로봇 시스템을 활용해 제시함.
* **주요 역할**: 프로젝트 매니징(PM) 및 일정 관리, TurtleBot4 기반 ROS2 시스템 프로토타이핑, UWB 센서 기반 측위 검증

---

## 2. 사용 기술 스택 (Tech Stack)
* **Target Robot Platforms**: Clearpath TurtleBot4 (ROS2 Humble, Raspberry Pi 4, Create3 Base)
* **OS**: Ubuntu 22.04 LTS
* **Middleware**: ROS2 (Humble)
* **Languages**: Python, C++
* **Sensors**: OAK-D Lite Depth Camera, RPLIDAR A1, UWB (Ultra-Wideband) Positioning Module
* **Network & Comm**: FastDDS, Wi-Fi Roaming Access Point, WebRTC
* **Management Tools**: Jira (Schedule Management), Git/GitHub

---

## 3. 하드웨어/소프트웨어 시스템 아키텍처 (System Architecture)

```text
[ Remote Operations Center (ROS2 Web Bridge) ]
                     ▲
                     │ (Wi-Fi Comm)
                     ▼
       [ Raspberry Pi 4 (Main CPU) ] <───────> [ Create3 Mobile Base ]
         - ROS2 Humble Navigation2             - Odometry & Drive Control
         - FastDDS Configuration
         - OAK-D Image Processing
                     ▲
                     ├──────────────────────┐
                     ▼                      ▼
           [ RPLIDAR A1 (LiDAR) ]    [ UWB Positioning Node ]
```

---

## 4. 핵심 기능 및 구현 내용 (Core Features)
* **비정형 환경 SLAM 및 자율주행**: 정해진 경계가 없는 건설 현장에서 장애물(흙더미, 드럼통 등)이 포함된 동적 지도를 작성(SLAM-Toolbox)하고, Nav2(Navigation2) 스택의 Costmap 파라미터를 현장 특성에 맞춰 커스텀 튜닝하여 장애물 우회 자율주행을 실현.
* **UWB 및 GPS 기반 고정밀 차량-로봇 상대 위치 측위**: 대형 트럭과 유도 로봇에 각각 UWB 모듈을 장착하여 GPS가 차단되는 영역(가건물 내부 등)에서도 오차 범위 10cm 이내로 트럭과 로봇의 상대적 위치를 측정.
* **트럭 검출 및 추적 알고리즘**: OAK-D 카메라의 공간 인공지능 모듈을 사용해 트럭 및 건설 장비 클래스를 실시간 인식하고 Depth 데이터를 융합해 상대적 거리 정보 획득.
* **이벤트 기반 자율 정지 및 대피 알고리즘**: 트럭이 비정상 경로로 접근하거나 로봇의 센서가 차단되는 위험 상황 시 즉각 주행을 멈추고 현장 외곽 안전구역으로 자동 대피(Escape behavior)하는 행동 트리(Behavior Tree) 구현.

---

## 5. 엔지니어링 이슈 및 Troubleshooting
### [이슈] 건설 현장의 광범위한 다이내믹 환경에서 무선 네트워크 단절로 인한 로봇 오작동
* **현상**: 비정형 넓은 공터에서 로봇 주행 테스트 중 통신 사각지대에 진입할 때 ROS2 노드 간 통신(DDS) 레이턴시가 500ms 이상으로 증가하다 결국 연결이 끊겨 로봇이 마지막 명령 상태로 계속 직진하는 위험 상황 발생.
* **원인 분석**: 기본 ROS2 멀티캐스트 설정 및 DDS 프로토콜의 대역폭 점유율이 높아 무선 환경이 취약한 실외에서 패킷 드롭이 쉽게 일어남.
* **해결 방법**:
  1. ROS2의 미들웨어를 기본 설정에서 **FastDDS**로 명시하고, XML 설정 파일을 생성하여 네트워크 품질이 나쁠 경우 재전송 횟수를 제한하고 패킷 단위를 소형화하는 **QoS(Quality of Service) 정책 커스텀 튜닝** (Reliability: Best Effort, Durability: Volatile 위주 적용).
  2. 로봇 내부에 **통신 하트비트 모니터링 노드(Watchdog)**를 작성하여 메인 제어기와의 통신 단절이 1.5초 이상 지속될 시 즉시 모바일 베이스에 비상 정지 명령(`Twist (0,0)`)을 주도록 하드웨어 안전 로직 추가.
* **결과**: 통신 단절 시의 비상 정지 반응 속도를 **0.1초 이하**로 끌어올려 안전 사고 위험을 완벽히 제거함.
