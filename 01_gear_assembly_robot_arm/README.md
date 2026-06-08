# 🤖 Doosan M0609 정밀 돔 검사 및 스마트 팩토리 제어 시스템 (Dome Inspection & Control System)

본 프로젝트는 6축 산업용 협동 로봇(Doosan Robotics M0609)을 활용하여 부품 피킹, 정밀 압입, 태스크 순응 제어 기반의 3D 돔(Dome) 표면 검사 스캐닝을 수행하고, 실시간 관절 토크 감지 및 3D 형상 오차 분석을 통해 불량을 검출하여 웹 대시보드와 동기화하는 스마트 공정 자동화 시스템입니다.

---

## 1. 프로젝트 개요 (Project Overview)
* **개발 기간**: 20XX.XX ~ 20XX.XX
* **개발 목적**: 정밀 돔 스캐닝 경로 생성과 실시간 외력 토크 센싱을 연동하여 미세 크랙 및 치수 불량을 비파괴 방식으로 검사하고, 클라우드(Firebase)를 통해 공정 제어 및 대시보드 모니터링 자동화 구축.
* **주요 역할**: ROS2 패키지 설계 및 마스터 제어 노드 구현, 실시간 외력 토크 기반 불량 분석 엔진 및 3D 오차 리포팅 웹 파이프라인 개발, ROS2-Firebase 양방향 통신 브리지 구축.

---

## 2. 사용 기술 스택 (Tech Stack)
* **Robot & Controller**: Doosan Robotics M0609 (6축 협동 로봇), Doosan Controller (DRL 지원)
* **Middleware**: ROS2 (Foxy / Humble), FastDDS
* **Languages**: Python 3 (FastAPI, NumPy, SciPy), C++ (Arduino IDE)
* **Databases & Cloud**: Firebase Realtime Database (실시간 상태 동기화), Firebase Cloud Storage (HTML 불량 리포트 적재)
* **Robotics Math**: DH Parameter 기반 Forward Kinematics (순운동학 구현), Cubic Spline (3차원 스플라인 보간)
* **Hardware & Components**: Arduino (컨베이어 센서 브리지), Robotiq 2F-85 Gripper, FLIR Camera
* **Web UI**: HTML5/CSS3/JavaScript, Plotly.js (3D 인터랙티브 그래프 시각화)

---

## 3. 시스템 아키텍처 (System Architecture)

```text
  [ Web UI Dashboard ] <────────────── (WebSockets / REST API) ─────────────> [ Firebase Cloud ]
           │                                                                     ▲     ▲
     (Manual Commands)                                                  (Report) │     │ (Status)
           ▼                                                                     │     │
[ ROS2 Firebase Bridge Node ] <─────── (ROS2 Topics/Services) ───────> [ ROS2 Torque Monitor Node ]
  - robot/control & command polling                                      - Forward Kinematics (FK)
  - JointState/Task pos publishing                                      - GetExternalTorque (20Hz)
           │                                                            - Cubic Spline Path Analysis
           ▼                                                                     ▲
[ ROS2 Master Control Node ]                                                     │
  - DRL (Doosan Robot Language) Engine                                           │
  - Modbus/TCP & Serial Communication                                           │
           │                                                                     │
           ├───────────────────────────────┬─────────────────────────────────────┤
           ▼                               ▼                                     ▼
 [ Doosan M0609 Robot ]          [ Robotiq 2F-85 Gripper ]             [ Arduino Conveyor Sensor ]
```

---

## 4. 핵심 기능 및 구현 내용 (Core Features)

### ① 실시간 관절 외력 감지 및 3D 크랙 검출 (`torque_monitor_09.py`)
* **순운동학 (Forward Kinematics) 구현**: M0609의 DH 파라미터를 기반으로 자체 FK 수학 모델 라이브러리를 작성하여, 조인트 각도 피드백 토픽(`/dsr01/joint_states`)으로부터 실시간 TCP의 3D 공간 좌표 `[X, Y, Z]`를 20Hz 주기로 정밀 계산.
* **외력 토크 실시간 센싱**: `GetExternalTorque` 서비스 클라이언트를 비동기로 호출하여, 모션 구동 중의 가상 마찰력을 배제한 순수 외력 토크 스파이크를 모니터링. 토크 임계치(1.7 Nm) 초과 시 표면 크랙 발생 구간으로 실시간 플래깅.

### ② 스플라인 보간 기반 형상 편차 분석 및 HTML 리포트 자동 생성
* **Cubic Spline 궤적 분석**: 크랙 감지 시점의 전후 윈도우 프레임 데이터를 추출하고, 정상 궤적 데이터 점들을 대상으로 `SciPy` 라이브러리의 3차원 스플라인 보간(`CubicSpline`)을 적용하여 설계 대비 미세 변형 편차(`e_max`)를 산출. (허용 오차율 기준 5.0% 초과 시 최종 불량 판정)
* **Plotly.js 연동 3D 리포팅**: 정상 궤적(Blue)과 크랙 검출 궤적(Red)을 3D 점군 데이터로 시각화하는 인터랙티브 **Plotly.js 기반 HTML 리포트**를 자동 생성하여 Firebase Cloud Storage에 업로드하고, URL 메타데이터를 Realtime DB에 적재하여 작업자 대시보드에 팝업을 즉시 트리거.

### ③ 태스크 순응 제어 (Task Compliance Control) 및 3D 돔 스캐닝 궤적 제어 (`total_control.py`)
* **3D 반구 스캔 궤적**: 반구형 대상 물체의 표면을 따라 face-on 방향을 유지하며 회전하는 10개 층(Layers)의 3D 원호 보간 경로 생성 알고리즘 구현.
* **컴플라이언스 모드**: DRL(Doosan Robot Language) 스크립트 기반으로 로봇의 축별 강성(Stiffness)을 `[500, 500, 3000, 300, 300, 300]`으로 낮추는 순응 제어(`task_compliance_ctrl`)를 적용하여 급격한 접촉 충격을 방지하고 균일한 밀착 스캔 유지.

### ④ ROS2 ↔ Firebase Realtime DB 양방향 통신 브리지 구축 (`ros_firebase_bridge.py`)
* **상태 동기화**: 로봇의 실시간 조인트 각도(`robot/joints`), 3D 태스크 좌표(`robot/task`), 통계 데이터(합격/불량 수량 및 합격률), 공정 진행 상태 코드를 0.2초 주기로 Firebase DB에 전송.
* **웹 원격 제어**: 웹 브라우저에서 발생하는 비상정지(E-Stop), 수동 조그(JOG), 그리퍼 동작, DRL 스크립트 호출 명령을 감지하여 ROS2 서비스로 변환·실행하는 비동기 이벤트 리스너 구현.

### ⑤ 보호정지(Protective Stop) 원격 복구 및 H2R (Human-to-Robot) 비상 해제
* **원격 안전 모드 제어**: 충돌 또는 과부하로 보호정지(State 5) 상태가 될 때, 제어기를 원격으로 복구 모드(`SAFETY_MODE_RECOVERY`)로 전환.
* **H2R 액션 제어**: 복구 모드 내에서 안전 저속 조건으로 `MovejH2r` 및 `MovelH2r` 액션 서버를 제어하여 로봇을 장애물로부터 안전하게 이탈시킨 후, 보호정지를 해제(`SetRobotControl(2)`)하여 정상 자율주행 모드로 원격 복귀시키는 오프라인 복구 파이프라인 구현.

---

## 5. 엔지니어링 이슈 및 Troubleshooting

### 🚨 [이슈 1] 가감속 구간 관성력으로 인한 궤적 극초반의 토크 스파이크 오탐지
* **현상**: 스캔 경로 진입 및 레이어 전환 직후, 가속 구간에서 발생하는 급격한 관성 부하로 인해 실시간 관절 토크가 임계치(1.7 Nm)를 초과하여 결함이 없음에도 불량(FAIL)으로 오진단되는 현상 발생.
* **원인 분석**: 정적인 힘 제어가 아닌 고속 3D 원호 모션 특성상 모션 시작부에 발생하는 동적 과도응답(Transient Response) 토크가 정상 범위의 밴드를 크게 벗어남.
* **해결 방법**: 각 레이어 스캔 모션이 기동하는 시점부터 1초간(20Hz 기준 20프레임 `IGNORE_START_FRAMES = 20`) 토크 스파이크 판정을 강제로 차단하는 **초기 안정화 필터링 알고리즘**을 추가 구현.
* **결과**: 가속 구간의 관성 노이즈로 인한 불량 오진단을 완전히 차단하여 검사 신뢰도 **99.8%** 확보.

### 🚨 [이슈 2] 단방향 대기 루프로 인한 ROS2 통신 차단 및 E-Stop 제어 불능
* **현상**: 공정 실행 중 모션 완료 시점까지 단순 `time.sleep`을 동기적으로 사용해 대기하자, ROS2 큐의 이벤트 스핀(Spin)이 차단되어 웹 대시보드에서 발행한 비상정지(E-Stop)나 일시정지 명령이 수 초간 딜레이되거나 무시되는 안전사고 위험 발생.
* **원인 분석**: 단일 스레드 구조에서 Blocking 대기 함수가 실행 루프를 점유하여 ROS2 통신 콜백 큐가 제때 비워지지 않음.
* **해결 방법**: `time.sleep`을 0.1초 단위 루프로 세분화하고 대기 주기마다 `rclpy.spin_once(self, timeout_sec=0.01)`를 강제로 호출해 이벤트를 비워주는 **비차단 스마트 대기 함수(`wait_smart`)**를 개발하여 로봇 모션 중에도 지속해서 비동기 통신 채널을 오픈.
* **결과**: 주행 제어 중 비상정지 및 일시정지 인터럽트 응답 레이턴시를 3초 이상에서 **35ms 이내**로 대폭 단축하여 국제 안전 규격을 충족함.
