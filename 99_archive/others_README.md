# 📈 Others - Personal Automation Pipelines

이 디렉토리는 금융 데이터 수집/매매 및 취업 모니터링 등 개인 효율성을 극대화하기 위해 구축한 자동화 파이프라인 프로젝트들을 포함하고 있습니다.

---

## 📂 Directory Structure

```text
03_others/
├── README.md                           # 👈 현재 파일 (Others 목차)
│
├── 01_quant_trading/                   # 📈 WebSocket 기반 글로벌 자산 스크리닝 및 자동 매매 시스템
│   └── README.md
│
└── 02_job_crawler/                     # 🔍 Gmail API 기반 채용 공고 실시간 모니터링 및 알림 파이프라인
    └── README.md
```

---

## 🛠 Projects Overview

### 1. [01_quant_trading](./01_quant_trading/)
* **Description**: WebSocket 실시간 스트리밍 체결 데이터 수집, 비동기 트래픽 Rate Limiter 제어 및 안전 예외 처리를 접목한 자동 매매 시스템.
* **Key Techs**: Python, FastAPI, WebSockets, PostgreSQL, Redis, Upbit API

### 2. [02_job_crawler](./02_job_crawler/)
* **Description**: Google Gmail API 및 텔레그램 봇 API를 연동하여 특정 키워드/플랫폼의 신규 채용 공고를 실시간으로 모니터링하고 알림을 전송하는 파이프라인.
* **Key Techs**: Python, Gmail API (OAuth2), Telegram Bot API, Windows Task Scheduler
