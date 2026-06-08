# 📊 글로벌 자산 스크리닝 자동 매매 및 Gmail 취업 모니터링 파이프라인 (Global Asset Screening Automated Trading & Gmail Job Monitoring Pipeline)

본 프로젝트는 금융 자산(주식, 가상자산)의 실시간 시세 수집 및 자동 스크리닝·매매 기능과 더불어, 채용 플랫폼들로부터 발송되는 Gmail 알림을 자동으로 수집·분석하여 대시보드에 모니터링하는 통합 자동화 파이프라인입니다.

---

## 1. 프로젝트 개요 (Project Overview)
* **개발 기간**: 20XX.XX ~ 진행 중
* **개발 목적**: 정량적 분석 기반 투자 자동화 및 채용 공고 모니터링 자동화를 통한 효율적인 자산 및 취업 활동 관리
* **주요 역할**: 실시간 데이터 수집 및 이메일 파싱 파이프라인 설계, 투자 전략 구현, 통합 모니터링 대시보드 구축

---

## 2. 사용 기술 스택 (Tech Stack)
* **Backend & Logic**: Python, FastAPI, IMAPlib / Gmail API
* **Database**: PostgreSQL (시계열 데이터 및 공고 데이터 적재), Redis
* **Web UI / Dashboard**: Streamlit (혹은 Next.js)
* **Data & Analysis**: Pandas, BeautifulSoup4 (메일 HTML 파싱)
* **DevOps**: Docker, Docker Compose, Task Scheduler / Cronjob
* **APIs**: 한국투자증권 API, Upbit API, Telegram Bot API (알림 송신)

---

## 3. 소프트웨어 시스템 아키텍처 (System Architecture)

```text
[ Data Source (Market API / WebSockets) ] ──┐
                                             ├──> [ ETL Pipeline (Python) ] ──> [ DB / Redis Cache ]
[ Mail Source (Gmail API / IMAP) ] ──────────┘                                   │
                                                                                 ▼
                                                                     [ Streamlit Dashboard ]
                                                                                 │
                                                                                 ▼
                                                                       [ Telegram Notification ]
```

---

## 4. 핵심 기능 및 구현 내용 (Core Features)
* **다중 자산 실시간 시세 파이프라인**: Upbit/한국투자증권 API를 활용하여 실시간 호가 및 체결 데이터를 수집하고 Redis에 인메모리 캐싱하여 데이터 응답 지연을 최소화함.
* **Gmail 기반 취업 모니터링 파이프라인**: 원티드, 링크드인 등 채용 플랫폼에서 수신되는 Gmail 알림 메일을 Gmail API/IMAP을 통해 백그라운드에서 주기적으로 수집하고, BeautifulSoup4로 채용 공고 정보(회사명, 직무, 마감일, 링크)를 추출하여 PostgreSQL에 자동 적재.
* **실시간 투자 및 채용 모니터링 대시보드**: 총자산 평가액 및 당일 손익 그래프와 함께, 금일 신규 등록된 채용 공고 및 지원 상태 현황판을 Streamlit 대시보드 하나로 통합 시각화.
* **이벤트 기반 Telegram 실시간 알림**: 퀀트 매매 매수/매도 시그널 발생 시점 및 중요 기업 채용 공고 매칭 시 Telegram 봇을 통해 모바일로 상세 정보 즉시 알림 송신.

---

## 5. 엔지니어링 이슈 및 Troubleshooting
### [이슈] OpenAPI 요청 제한(Rate Limit) 초과로 인한 시세 수집 지연 및 누락
* **현상**: 모니터링 대상 종목이 늘어남에 따라 다수의 종목 시세를 동시에 요청(REST API Polling)하자, 증권사 API 서버로부터 `429 Too Many Requests` 에러가 반환되며 일부 종목 시세 수집이 누락됨.
* **원인 분석**: 증권사 및 거래소는 초당 요청 제한(예: 한국투자증권은 초당 10회 제한)이 있으며, 동기식 멀티스레드 루프 방식으로 매번 API를 직접 호출한 점이 제한을 초과하는 요인이 됨.
* **해결 방법**:
  1. REST API 기반의 동기식 수집 방식에서 **WebSocket 실시간 스트리밍(Publish/Subscribe)** 방식으로 전면 전환하여 하나의 소켓 연결로 다중 종목 시세를 실시간 갱신받도록 수정.
  2. 부득이하게 REST API를 써야 하는 종목 정보 및 잔고 조회의 경우, 파이썬의 **Asyncio 및 Semaphore**를 활용한 비동기 데코레이터를 구현하여 초당 요청 수가 임계치(10회)를 넘지 않도록 자동 조절(Rate Limiter) 구현.
* **결과**: API 요청 수 제한 차단이 발생하지 않으며, CPU 점유율을 30% 절감하는 동시에 실시간 시세 수집 딜레이를 평균 50ms 이내로 안정화함.
