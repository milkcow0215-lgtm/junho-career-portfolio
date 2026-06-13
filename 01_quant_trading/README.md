# 📈 WebSocket 기반 글로벌 자산 스크리닝 및 자동 매매 시스템 (quant_trading)

본 프로그램은 가상자산 및 글로벌 금융 데이터의 실시간 변동성을 모니터링하고, 정의된 퀀트 알고리즘 조건 충족 시 API를 통해 즉각적인 거래 명령을 수행하는 비동기 데이터 처리 및 자동 매매 인프라 시스템입니다.

---

## 1. 사용 기술 스택
* **Language**: Python 3
* **Libraries**: FastAPI, NumPy, Pandas, WebSockets, Requests
* **Database & Cache**: PostgreSQL (체결 로그 및 거래 데이터 적재), Redis (실시간 시세 캐싱 및 호가 버퍼)
* **API Integration**: Upbit Open API, Telegram Bot API

---

## 2. 핵심 기능 및 엔지니어링 이슈 해결
* **WebSocket 실시간 스트리밍**: HTTP 폴링 방식의 네트워크 병목을 해결하기 위해 WebSocket 프로토콜 연결을 상시 오픈하여 밀리초(ms) 단위의 체결 데이터(Orderbook) 유입 파이프라인 구축.
* **비동기 API Rate Limiter 제어**: 거래소 오픈 API 호출 제한(초당 요청 수 제한)으로 인한 IP 블로킹 오류를 방지하기 위해, 파이썬 비동기 큐와 슬라이딩 윈도우 기반의 Rate Limiter 알고리즘을 커스텀 구현하여 트래픽 안정성 확보.
* **안전 예외 처리 메커니즘**: 자산 매매 중 발생할 수 있는 네트워크 단절, 잔고 부족, API 키 만료 등의 리스크를 제어하기 위해 단계별 try-except 예외 처리 및 비상 코스트(Coast) 모드를 설계하여 비정상 자산 손실 방지.

---

## 3. 사용 및 구동 방법
```bash
# 1. 시스템 의존성 설치
pip install fastapi websockets pandas psycopg2-binary redis

# 2. 메인 자동매매 코어 엔진 기동
python3 main_trading_engine.py
```
