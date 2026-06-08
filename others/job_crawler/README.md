# 🔍 Gmail API 기반 채용 공고 실시간 모니터링 및 알림 파이프라인 (job_crawler)

본 프로그램은 취업 준비 과정에서의 정보 수집 피로도를 최소화하고 핵심 채용 정보를 실시간으로 확보하기 위해, 구글 이메일 인프라와 메시징 API를 연동하여 구축한 데이터 파이프라인 자동화 시스템입니다.

---

## 1. 시스템 아키텍처 및 데이터 흐름
1. **Trigger**: Windows Task Scheduler (매일 아침 지정 시간 배치 잡 실행)
2. **Data Extraction**: Google Gmail API (OAuth2 인증 기반 특정 키워드 및 채용 플랫폼 정보 파싱)
3. **Data Processing**: Python 3 로직 기반 정규식 필터링 및 텍스트 데이터 정제
4. **Notification**: Telegram Bot API (비동기 HTTP 요청을 통한 개인 관제 채널 전송)

---

## 2. 핵심 기능 및 구현 내용
* **OAuth2 기반 인증 보안**: Google Cloud Console 권한 관리를 통해 안전한 API 토큰 인증 방식을 적용, 실시간으로 이메일 데이터 레이어를 쿼리(Query)함.
* **중복 수집 및 부하 방지**: 긁어온 메일의 고유 ID(`Message-ID`)를 파싱하여 이전에 전송된 공고와 대조하는 예외 처리를 통해 중복 알림을 원천 차단.
* **정적 배치(Batch) 스케줄링**: 가상환경(`venv`)과 패키지 의존성을 독립시킨 후 Windows 스케줄러 구동 스크립트(`.bat`)를 매핑하여 로컬 서버의 백그라운드 상시 가동 환경 확보.

---

## 3. 사용 및 구동 방법
```bash
# 1. 의존성 라이브러리 설치
pip install google-auth-oauthlib google-api-python-client requests

# 2. 최초 실행 및 구글 OAuth 인증 (token.json 생성)
python3 job_monitor_crawler.py
```

* **구동 변수 설정**: 환경 변수(`.env`) 파일 내에 `TELEGRAM_BOT_TOKEN`, `CHAT_ID`, `GOOGLE_APPLICATION_CREDENTIALS` 경로 바인딩 필수.
