================================================================================
🐾 Spot-Doosan Arm Locomotion & Manipulation Execution Guide (README)
================================================================================

1. 개발 및 가상환경 활성화 (Environment Setup)
--------------------------------------------------------------------------------
본 프로젝트는 Isaac Lab 전용 가상환경(venv) 및 ROS2 Humble 아키텍처 상에서 구동됩니다.
시뮬레이션 및 학습 스크립트를 실행하기 전, 새 터미널을 열고 아래 명령어를 순서대로 
입력하여 가상환경 활성화 및 작업 디렉토리 진입을 수행하십시오.

$source ~/dev_ws/venv/isaaclab/bin/activate$ cd ~/dev_ws/isaac_sim/IsaacLab

💡 [TIP] 매번 입력하기 번거롭다면 '~/.bashrc' 맨 아래에 단축어(alias)를 등록하세요:
$ gedit ~/.bashrc
(맨 아랫줄에 다음 추가 후 저장)
alias goisaac="source ~/dev_ws/venv/isaaclab/bin/activate && cd ~/dev_ws/isaac_sim/IsaacLab"

등록 후 터미널에 'goisaac'만 입력하면 환경 활성화와 디렉토리 이동이 동시에 수행됩니다.


2. 프로젝트 주요 파일 및 에셋 위치 (Project Structure)
--------------------------------------------------------------------------------
순정 Isaac Lab 패키지 상태에서는 Doosan Arm 무게중심 튜닝 모델 및 커스텀 에셋이 누락되어
있습니다. 프로젝트 클론 후 반드시 아래 커스텀 파일들을 지정된 경로에 배치하십시오.

1) 로봇 및 시뮬레이션 환경 설정 (Python Config & Scripts)
   * 4족 로봇 상벌점 및 환경 가중치 설정 파일 세트:
     ├── isaaclab_tasks/manager_based/locomotion/velocity/config/spot/flat_env_cfg.py
     └── isaaclab_tasks/manager_based/locomotion/velocity/config/spot/__init__.py
     ※ Doosan Arm 하중(stand_still_scale=25.0) 최적화 및 태스크 등록 정보가 반영된 핵심 파일입니다.

   * 터미널 명령어 인자(Arguments) 파싱 및 학습 제어 유틸리티:
     └── scripts/reinforcement_learning/rsl_rl/cli_args.py
     ※ 이어학습(--resume), 가중치 로드(--checkpoint) 등 터미널 명령어를 제어하는 매개체입니다.

   * 학습 메인 실행 스크립트:
     ├── scripts/reinforcement_learning/rsl_rl/train.py
     └── scripts/reinforcement_learning/rsl_rl/play.py

2) 3D 로봇 및 센서 에셋 (USD Files)
   * Spot 로봇 원본 및 Doosan Arm, XT-32 라이다 결합용 3D 에셋 위치:
     └── ~/dev_ws/isaac_sim/src/
         ├── my_spot.usd              (순정형 Spot 4족 로봇 원본 에셋)
         ├── robot_arm.usd            (Doosan Arm 매니퓰레이터 단독 에셋)
         ├── XT-32.usd                (상단 장착형 3D 라이다 센서 에셋)
         └── my_spot_arm_visual.usd   (Spot + 라이다 + 로봇팔이 최종 결합된 시뮬레이션 메인 에셋)
   ※ 주의: 시뮬레이션 구동 시 위 4개 USD 파일이 반드시 'src' 폴더 내에 함께 존재해야 
     조인트 및 비주얼 링크 붕괴 현상이 발생하지 않습니다.

3) 최종 학습 완료 가중치 파일 (PyTorch Model)
   * 복사할 목적지 경로:
     └── ~/dev_ws/isaac_sim/IsaacLab/logs/rsl_rl/spot_flat/2026-06-11_09-53-39/model_39998.pt
   ※ Mean Reward 397.51을 달성하여 보행 및 제자리 정지 밸런스가 완비된 최적의 소뇌(Policy) 모델 가중치입니다.


3. 강화학습 실행 가이드 (Reinforcement Learning)
--------------------------------------------------------------------------------
※ 대규모 병렬 환경 구동 시 메모리 부족(Killed) 에러가 발생할 수 있습니다.
   이를 방지하기 위해 'flat_env_cfg.py' 내에서 병렬 환경 수를 최적화(num_envs = 64)하고,
   Linux Swap 가상 메모리(32GB)를 확보한 후 학습을 진행하는 것을 권장합니다.

A. 처음부터 새롭게 학습을 시작할 때 (Scratch Training)
   $ python scripts/reinforcement_learning/rsl_rl/train.py --task Isaac-Velocity-Flat-Spot-v0

B. 기존에 중단된 체크포인트부터 이어서 파인튜닝할 때 (Resume Training)
   $ python scripts/reinforcement_learning/rsl_rl/train.py --task Isaac-Velocity-Flat-Spot-v0 --resume --load_run 2026-06-11_09-53-39 --checkpoint "model_.*"


4. 모델 검증 및 원격 제어 (Play & Teleoperation)
--------------------------------------------------------------------------------
학습이 완료된 인공신경망 정책(Policy) 파일(*.pt)의 물리 거동을 시뮬레이터에서 검증하고,
키보드 또는 조이스틱 인터페이스를 활용해 Spot 로봇을 원격으로 수동 조종하는 명령어입니다.

$ python scripts/reinforcement_learning/rsl_rl/play.py --task Isaac-Velocity-Flat-Spot-v0 --num_envs=1 --checkpoint /home/rokey/dev_ws/isaac_sim/IsaacLab/logs/rsl_rl/spot_flat/2026-06-11_09-53-39/model_39998.pt --teleop


5. 제어 공학적 팁: 영점 흐름 방지 (Deadzone Filter)
--------------------------------------------------------------------------------
강화학습 모델 수렴 이후, 영점 지령(정지 상태) 시 로봇이 미세 노이즈나 과보정 여파로 
인해 '좌측 전방'으로 조금씩 밀려 나가는 미세 흐름 현상이 관찰될 수 있습니다.

이를 해결하기 위해 모델을 처음부터 다시 재학습하지 말고, 로봇을 구동하는 최상위 파이썬 
제어 스크립트(Hermes 상위 에이전트 혹은 Task 시퀀서단) 내 환경 step 함수 호출 직전에 
아래와 같이 데드존(Deadzone) 필터 코드를 주입하여 완전 고정 메커니즘을 완성하십시오.

[적용 코드 스니펫 예시]
--------------------------------------------------------------------------------
raw_cmd_x = commands[0]  # 전진 지령 속도
raw_cmd_y = commands[1]  # 좌우 지령 속도

# 0.05 m/s 이하의 미세한 흐름 노이즈 속도는 강제로 완전 정지(0) 처리
filtered_cmd_x = 0.0 if abs(raw_cmd_x) < 0.05 else raw_cmd_x
filtered_cmd_y = 0.0 if abs(raw_cmd_y) < 0.05 else raw_cmd_y

# 최종 필터링된 지령을 소뇌 정책 신경망(Policy) 입력값으로 주입
env.step(action_or_commands=[filtered_cmd_x, filtered_cmd_y, cmd_yaw])
--------------------------------------------------------------------------------

이 보정 필터는 'suction_grasp'(흡착 잡기) 및 'search_qr'(QR 스캔) 태스크 진입 시 
로봇 바디를 강력하게 홀딩시켜 전체 하이브리드 자율 주행 시퀀스의 성공률을 극대화합니다.
================================================================================
