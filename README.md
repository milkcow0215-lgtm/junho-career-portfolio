# 🚀 Junho's Career & Portfolio Space

Welcome! 이 저장소는 로봇 공학 및 기계공학을 기반으로 하드웨어와 소프트웨어를 유기적으로 통합하고, 비정형 환경의 물리적 변수를 엔지니어링 적으로 해결하는 저의 핵심 역량과 대표 프로젝트들을 체계적으로 관리하는 공간입니다.

---

## 👨‍💻 About Me

* **Name**: 양준호 (Junho Yang)
* **Goal**: 현장 문제를 이해하고 HW-SW 통합 기반의 안정적이고 확장 가능한 로봇 시스템을 구축·운용하는 로보틱스 엔지니어입니다.
* **Focus**: ROS2 기반 로봇 아키텍처 설계, 시스템 통합, 제어 알고리즘 최적화 및 데이터 기반의 실용적 솔루션 도출

---

## 🛠 Tech Stack & Engineering Skills

| 구분 | 보유 스킬 및 프레임워크 |
| :--- | :--- |
| **Languages** | Python, C/C++, MATLAB |
| **Frameworks & Middleware** | ROS2 (Humble/Foxy), FastAPI |
| **AI / Machine Learning** | PyTorch, YOLOv8, Ollama (Qwen, Llama) |
| **Environment & DevOps** | Ubuntu, Docker, Windows, Git |
| **Hardware & Boards** | Raspberry Pi 4, ESP32, Arduino, Doosan M0609 |
| **CAD & CAE Interpretation** | AutoCAD, Catia, Autodesk Fusion 360, ANSYS Mechanical |

---

## 📂 Project Directory Index

이 워크스페이스는 다음과 같은 구조로 프로젝트를 최신순으로 관리합니다. 각 폴더 내부의 `README.md`에서 상세한 시스템 아키텍처와 트러블슈팅 내역을 확인하실 수 있습니다.

```text
C:\Anti_workspace/
│
├── README.md                           # 👈 현재 파일 (포트폴리오 대문)
├── .gitignore                          # Git 제외 규칙 설정 파일
├── .env                                # 로컬 환경 변수 설정 파일 (비공개)
│
├── 01_quant_trading/                  # 📈 글로벌 자산 스크리닝 자동 매매 파이프라인
├── 02_job_crawler/                    # ✉️ Gmail 취업 모니터링 파이프라인
│
├── 10_rokey_bootcamp/                 # 🎓 ROKEY Bootcamp 관련 프로젝트
│   ├── 01_robot_arm_assembly/         # 🤖 투명 사출물 결함 검수 및 로봇 자동화 공정 시스템
│   ├── 02_turtlebot_guidance/         # 🚜 SLAM 기반 건설현장 유도원 자동화 시스템 (오라이봇)
│   ├── 03_local_vla_v1/               # 🦾 로컬 VLA 제어 시스템 (버전 1)
│   ├── 04_local_vla_v2/               # 🦾 로컬 VLA 제어 시스템 (버전 2)
│   └── 99_archive/                    # 📂 보관된 레거시 스크립트 및 테스트 파일들
│
├── 20_my_projects/                    # 📂 개인/학부 프로젝트
│   └── 01_railway_inspection/         # 🚊 철도 유지보수 자동화를 위한 자율주행 결함 검출 로봇 설계
│
└── 99_archive/                        # 📂 기타 보관용 아카이브 방
```

---

## 🌟 Featured Projects

### 1. 🤖 투명 사출물 결함 검수 및 로봇 자동화 공정 시스템 ([01_gear_assembly_robot_arm](./10_rokey_bootcamp/01_robot_arm_assembly/))
* **개요**: 비전 카메라의 한계를 극복하기 위해 두산 협동로봇(M0609)의 내장 토크 센서를 활용한 물리 표면 스캔 및 비전-프리 결함 감지 시스템
* **핵심 구현**: 컴플라이언스(순응) 제어 알고리즘 적용 및 곡률 밀착 최적화, 3차원 스플라인 보간 기반 형상 편차 산출, 비동기 멀티스레딩 아키텍처 도입을 통한 통신 지연 제어
* **Tech Stack**: Doosan M0609, ROS2, Arduino, Python, Firebase, Plotly.js, OpenCV

### 2. 🚜 SLAM 기반 건설현장 유도원 자동화 시스템 - 오라이봇 ([02_construction_truck_guidance](./10_rokey_bootcamp/02_turtlebot_guidance/))
* **개요**: 비정형 건설 현장에서 중장비 충돌 예방을 위해 두 대의 TurtleBot4를 활용해 실시간 객체 인식 및 자율주행을 수행하는 다중 로봇 협업 시스템 (PM 수행)
* **핵심 구현**: 단일 토픽 기반 리더-팔로워 주행 동기화 구조 설계, 백분위수 필터(Percentile Filter)를 통한 RGB-D 거리 계측 노이즈 상쇄, FastDDS QoS 튜닝 및 임베디드 Watchdog 안전 인터럽트 구축
* **Tech Stack**: TurtleBot4, ROS2 (Humble), Nav2, YOLOv8m, OAK-D Pro, RPLIDAR A1, FastDDS

### 3. 🚊 철도 유지보수 자동화를 위한 자율주행 결함 검출 로봇 설계 ([03_autonomous_railway_robot](./20_my_projects/01_railway_inspection/))
* **개요**: 레일 표면 균열과 궤간 틀림 탐지를 위해 다중 센서 피드백 루프를 구축한 소형 무인 자율주행 로봇 시스템 (팀장 수행)
* **핵심 구현**: ANSYS 유한요소/진동 해석 및 가우시안 프로세스 회귀(GPR) 연동을 통한 기구부 진동 오차 최소화 설계, 아두이노 기반 다중 센서 타스크 제어 및 단계별 교차 검증 디버깅
* **Tech Stack**: Arduino Mega 2560, MPU6050, DC Motor & Encoder, ANSYS Mechanical, Fusion 360, Python

### 4. 📈 글로벌 자산 스크리닝 자동 매매 및 Gmail 취업 모니터링 파이프라인 ([01_quant_trading](./01_quant_trading/) 및 [02_job_crawler](./02_job_crawler/))
* **개요**: 데이터 수집, 가상 예외 처리 로직 및 외부 API 연동 인프라 역량을 다각화한 데이터 자동화 파이프라인 (개인 사이드 프로젝트)
* **핵심 구현**: WebSocket 실시간 스트리밍 및 비동기 API Rate Limiter 설정을 통한 제한 방지, Gmail API 기반 채용 공고 실시간 파싱 및 텔레그램 알림 자동화
* **Tech Stack**: Python, FastAPI, PostgreSQL, Redis, Streamlit, Upbit API, Telegram Bot API, Gmail API

---

## ✉️ Contact
* **GitHub**: [@milkcow0215-lgtm](https://github.com/milkcow0215-lgtm)
* **Email**: milkcow0215@gmail.com
