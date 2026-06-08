# 🚀 Junho's Career & Portfolio Space

Welcome! 이 저장소는 저의 **커리어 여정, 핵심 역량, 그리고 대표 프로젝트들**을 한눈에 볼 수 있도록 정리한 포트폴리오 공간입니다. 

---

## 👨‍💻 About Me
* **Name**: 양준호 (Junho Yang)
* **Goal**: 비즈니스 가치를 창출하고, 견고하며 확장 가능한 아키텍처를 설계하는 소프트웨어 엔지니어입니다.
* **Focus**: 백엔드 시스템 구축, 효율적인 알고리즘 설계 및 최적화, 데이터 기반의 실용적 솔루션 도출

---

## 🛠 Tech Stack

### Languages & Frameworks
* **Languages**: C++, Python, Java / Spring Boot, ROS2, FastAPI
* **Database**: PostgreSQL, MySQL, Redis
* **DevOps & Tools**: Docker, AWS, GitHub Actions, Modbus/TCP, Git

---

## 📂 Project Directory Index

이 워크스페이스는 다음과 같은 구조로 포트폴리오 프로젝트를 체계적으로 관리합니다.

```text
C:\career-portfolio/
│
├── README.md                           # 👈 현재 파일 (포트폴리오 대문)
├── .gitignore                          # Git 제외 규칙 설정 파일
├── .env                                # 로컬 환경 변수 설정 파일 (비공개)
│
├── 01_gear_assembly_robot_arm/         # Doosan M0609 Robot Arm Project
│   └── README.md
├── 02_construction_truck_guidance/     # TurtleBot4 Truck Guidance System PM Project
│   └── README.md
├── 03_autonomous_railway_robot/        # Autonomous Railway Robot Graduation Project
│   └── README.md
└── others/                             # Automated Trading & Notification Pipeline
    └── README.md
```

---

## 🌟 Featured Projects

### 1. [Doosan Robotics M0609 기어 조립 및 검사 시스템](./01_gear_assembly_robot_arm/)
* **역할**: 로봇 암 제어 알고리즘 구현 (DRL 스크립트 작성), Modbus/TCP 연동 및 OpenCV 비전 검사 구현
* **주요 성과**: 순응 제어 및 나선형 탐색 알고리즘을 도입하여 기어 조립 충돌 보호 정지 발생률을 0%로 단축
* **Tech Stack**: Python, DRL, Modbus/TCP, OpenCV, Robotiq 2F-85, FLIR Camera

### 2. [TurtleBot4 활용 건설 현장 트럭 유도 시스템](./02_construction_truck_guidance/)
* **역할**: 프로젝트 매니징(PM) 및 일정 관리, TurtleBot4 기반 ROS2 시스템 프로토타이핑 및 UWB 측위 검증
* **주요 성과**: 무선 네트워크 단절에 따른 Watchdog 및 FastDDS QoS 정책 커스텀 튜닝을 통해 실시간 비상 정지(0.1초 이내) 보장
* **Tech Stack**: ROS2 (Humble), Python, C++, OAK-D Lite, RPLIDAR A1, UWB

### 3. [자율주행 철도 점검 로봇 시스템](./03_autonomous_railway_robot/)
* **역할**: 자율주행 알고리즘 설계, LiDAR & Camera 센서 퓨전 구현, 로봇 제어 시스템 최적화
* **주요 성과**: TensorRT FP16 양자화를 통한 YOLOv8 추론 속도 개선 (8 FPS -> 32 FPS) 및 실시간 안전 주행 실현
* **Tech Stack**: ROS2 (Foxy), C++, Python, LiDAR, RealSense Camera, YOLOv8, STM32

### 4. [글로벌 자산 스크리닝 자동 매매 및 Gmail 취업 모니터링 파이프라인](./others/)
* **역할**: 실시간 데이터 수집 및 이메일 파싱 파이프라인 설계, 투자 전략 구현, 통합 모니터링 대시보드 구축
* **주요 성과**: WebSocket 실시간 스트리밍 도입 및 비동기 API Rate Limiter 설정을 통한 API 제한 방지, Gmail API 기반의 채용 공고 실시간 파이프라인 구축
* **Tech Stack**: Python, FastAPI, PostgreSQL, Redis, Streamlit, Upbit API, Telegram Bot API, Gmail API

---

## ✉️ Contact
* **GitHub**: [@milkcow0215-lgtm](https://github.com/milkcow0215-lgtm)
* **Email**: milkcow0215@gmail.com
