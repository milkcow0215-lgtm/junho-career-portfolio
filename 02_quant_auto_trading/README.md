# 📈 자산 스크리닝 자동 매매 및 모니터링 파이프라인 (Asset Screening Automated Trading & Monitoring Pipeline)

본 프로젝트는 주식, 가상자산 등 금융 자산의 데이터를 실시간으로 수집하고, 고유의 퀀트 팩터 알고리즘을 기반으로 유망 자산을 스크리닝하여 자동으로 주문을 실행 및 모니터링하는 통합 자동화 시스템입니다.

---

## 1. 프로젝트 개요 (Project Overview)
* **개발 기간**: 20XX.XX ~ 진행 중
* **개발 목적**: 정량적 분석 기반의 투자 자동화 구축 및 리스크 관리 자동화, 실시간 모니터링 환경 구현
* **주요 역할**: 실시간 데이터 수집 파이프라인 설계, 투자 전략(Factor & Signal) 구현, 자동 매매 봇 및 대시보드 웹앱 개발

---

## 2. 사용 기술 스택 (Tech Stack)
* **Backend & Logic**: Python, FastAPI
* **Database**: PostgreSQL (시계열 데이터 적재), Redis (실시간 시세 캐싱 및 세션 관리)
* **Web UI / Dashboard**: Streamlit (혹은 Next.js)
* **Data & Analysis**: Pandas, NumPy, Backtrader (백테스팅 라이브러리)
* **DevOps**: Docker, Docker Compose, Windows Task Scheduler / Linux Cronjob
* **APIs**: 한국투자증권 API, Upbit API, Telegram Bot API (알림 송신)

---

## 3. 소프트웨어 시스템 아키텍처 (System Architecture)

```text
[ Data Collector (API Polling / WebSockets) ]
                    │
                    ▼
          [ Redis Cache (Real-time) ]
                    │
                    ├──────────────────────┐
                    ▼                      ▼
           [ Database Engine ]     [ Strategy Executor ] ──> [ Broker API (Order Execution) ]
         (PostgreSQL Time-Series)          │
                                           ▼
                                [ Notification Service ] ──> [ Telegram Alert ]
                                           ▲
                                           │ (Query / Controls)
                                [ Monitoring Dashboard ]
                                (FastAPI + UI Dashboard)
```

---

## 4. 핵심 기능 및 구현 내용 (Core Features)
* **다중 자산 실시간 시세 파이프라인**: Upbit/한국투자증권 API를 활용하여 실시간 호가 및 체결 데이터를 수집하고 Redis에 인메모리 캐싱하여 데이터 응답 지연을 최소화함.
* **퀀트 백테스팅 및 전략 엔진**: `Backtrader` 라이브러리를 통해 과거 5년 데이터 기반 전략 시뮬레이션을 진행하고, MDD(최대 낙폭) 및 샤프 지수(Sharpe Ratio)를 자동 계산하여 전략 리스크 검증.
* **조건식 기반 자동 자산 스크리닝**: 일일 거래대금, 볼린저 밴드 상하한선 돌파, 이동평균선 정배열 등 복수 팩터를 조합하여 매일 아침 유망 종목 리스트를 스크리닝하고 우선순위를 산출.
* **실시간 투자 모니터링 대시보드**: 총자산 평가액, 현재 보유 종목 현황, 실시간 미체결 주문 내역, 오늘 실행된 매매 내역 및 당일 손익률을 실시간 차트로 표현.

---

## 5. 엔지니어링 이슈 및 Troubleshooting
### [이슈] OpenAPI 요청 제한(Rate Limit) 초과로 인한 시세 수집 지연 및 누락
* **현상**: 모니터링 대상 종목이 늘어남에 따라 다수의 종목 시세를 동시에 요청(REST API Polling)하자, 증권사 API 서버로부터 `429 Too Many Requests` 에러가 반환되며 일부 종목 시세 수집이 누락됨.
* **원인 분석**: 증권사 및 거래소는 초당 요청 제한(예: 한국투자증권은 초당 10회 제한)이 있으며, 동기식 멀티스레드 루프 방식으로 매번 API를 직접 호출한 점이 제한을 초과하는 요인이 됨.
* **해결 방법**:
  1. REST API 기반의 동기식 수집 방식에서 **WebSocket 실시간 스트리밍(Publish/Subscribe)** 방식으로 전면 전환하여 하나의 소켓 연결로 다중 종목 시세를 실시간 갱신받도록 수정.
  2. 부득이하게 REST API를 써야 하는 종목 정보 및 잔고 조회의 경우, 파이썬의 **Asyncio 및 Semaphore**를 활용한 비동기 데코레이터를 구현하여 초당 요청 수가 임계치(10회)를 넘지 않도록 자동 조절(Rate Limiter) 구현.
* **결과**: API 요청 수 제한 차단이 발생하지 않으며, CPU 점유율을 30% 절감하는 동시에 실시간 시세 수집 딜레이를 평균 50ms 이내로 안정화함.
