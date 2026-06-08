# 🤖 기어 조립 및 검사 로봇 암 시스템 (Gear Assembly & Inspection Robot Arm System)

본 프로젝트는 산업용 협동 로봇(Doosan Robotics M0609)을 활용하여 부품 피킹, 정밀 기어 조립, 2D 비전 기반 외관 검사를 수행하고 최종 불량 여부를 판별하는 스마트 팩토리 공정 자동화 시스템 프로젝트입니다.

---

## 1. 프로젝트 개요 (Project Overview)
* **개발 기간**: 20XX.XX ~ 20XX.XX
* **개발 목적**: 조립 공정의 정밀도를 개선하고 작업자 부상 방지를 위한 기어 조립 자동화 및 비전 검사 시스템 연동 개발
* **주요 역할**: 로봇 암 제어 알고리즘 구현 (DRL 스크립트 작성), 모드버스(Modbus/TCP) 연동, OpenCV 비전 검사 알고리즘 구현

---

## 2. 사용 기술 스택 (Tech Stack)
* **Manipulator Platform**: Doosan Robotics M0609 (6축 협동 로봇, Doosan Controller)
* **Programming Languages**: Python, DRL (Doosan Robot Language)
* **Control Protocols**: Modbus/TCP, Socket 통신 (TCP/IP)
* **Computer Vision**: OpenCV, Python Image Library (PIL)
* **Gripper**: Robotiq 2F-85 Adaptive Gripper
* **Vision Camera**: FLIR Industrial Area Scan Camera

---

## 3. 하드웨어/소프트웨어 시스템 아키텍처 (System Architecture)

```text
                  [ Master PC (Python Logic / GUI) ]
                    │                        │
  (Modbus/TCP Comm) │                        │ (TCP/IP Socket Comm)
                    ▼                        ▼
     [ Doosan Controller ]             [ FLIR Camera / OpenCV ]
     - DRL Script Execution                  - Dimension & Defect Inspection
     - 6-axis Articulated Control
                    │
                    ▼
     [ Robotiq Gripper ] (Modbus RTU)
```

---

## 4. 핵심 기능 및 구현 내용 (Core Features)
* **DRL(Doosan Robot Language) 기반 정밀 궤적 제어**: 기어 조립에 필요한 힘 제어(Compliance Control) 및 스파이럴 찾기(Spiral Search) 궤적을 DRL로 작성하여 백래시와 유격을 최소화한 0.05mm 조립 정밀도를 확보.
* **Modbus/TCP 프로토콜을 통한 로봇-PC 연동**: Master PC에서 로봇 제어기의 레지스터 값을 직접 모니터링하고 가속도, 힘 한계치 조절 및 동작 트리거 신호를 제어하는 인터페이스 구축.
* **2D 비전 기반 외관 치수 검사**: FLIR 카메라로 촬영된 기어 이미지를 실시간 수신하여 OpenCV 기반 Edge Detection 및 Contour Analysis 알고리즘을 통해 기어 치(Teeth) 외곽의 치수 및 피치각을 측정하고 설계치와의 오차율 계산.
* **그리퍼 정밀 핸들링**: Robotiq 2F-85 그리퍼에 피드백 제어 모듈을 적용하여 집는 힘(Gripping Force)과 스트로크를 가공 소재 재질에 따라 유연하게 제어.

---

## 5. 엔지니어링 이슈 및 Troubleshooting
### [이슈] 기어 맞물림 시 마찰력 및 중심 불일치로 인한 조립 걸림 현상 및 로봇 보호 정지
* **현상**: 로봇이 수직 하강 방식으로 기어를 샤프트에 삽입하는 조립 과정 중, 두 기어의 치(Teeth) 방향이 정확히 맞물리지 않고 마찰을 일으키며 기어 손상(긁힘)이 발생하거나 힘 한계치(Joint Torque Limit) 초과로 인한 제어기 보호 정지(Collistion Detection) 수시 발생.
* **원인 분석**: 로봇의 강성(Stiffness)이 지나치게 강해 중심축의 미세 오차(Misalignment)가 충돌력으로 그대로 흡수되었고, 두 기어가 회전하며 부드럽게 맞물리는 피팅 로직이 없었음.
* **해결 방법**:
  1. 기어 조립 진입 구간에서 로봇의 강성을 인위적으로 낮추는 **순응 제어(Compliance Mode)**를 적용하여 외부 힘에 의해 암이 미세하게 밀리며 축 정렬이 스스로 맞추어지도록 DRL 스크립트 수정.
  2. 수직 누름 도중 일정 토크 이상 검출 시 삽입을 중단하고 로봇 손목 조인트를 미세 회전시키며 재도입하는 **나선형 탐색 알고리즘(Spiral / Rotary Search Pattern)**을 구현.
* **결과**: 조립 도중 충돌 보호 정지 발생률을 **0%**로 낮췄으며, 조립 성공률을 **99.5%** 이상으로 확보하여 안정적인 생산 공정을 구성함.
