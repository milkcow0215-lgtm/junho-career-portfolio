# 춘식이 VLA Brain Center README

이 문서는 **춘식이 VLA 프로젝트의 PC1 대뇌 계층**을 실행하기 위한 정리 문서입니다.
현재 구조는 PC2가 Vision/ROS 계층에서 환경 정보를 생성해 PC1로 보내고, PC1이 Hermes Agent + 로컬 DeepSeek-R1을 통해 Task JSON을 생성한 뒤 다시 PC2로 전송하는 방식입니다.

---

## 1. 전체 시스템 구조

```text
PC2 Vision/ROS Layer
- Camera / Florence-2 / YOLO / ROS2
- 환경 정보 JSON 생성
- PC1의 8889 포트로 전송

        ↓ WebSocket

PC1 VLA Brain Layer
- Streamlit 관제 UI
- Hermes CLI 호출
- AGENTS.md 기반 환경 추론
- DeepSeek-R1:14B-64K 로컬 추론
- Task JSON 파싱/검증
- PC2의 9999 포트로 전송

        ↓ WebSocket

PC2 Action/Cerebellum Layer
- Task JSON 수신
- ROS2 / Isaac Sim / 실제 로봇 실행 코드로 변환
```

현재 실행 파일은 **`vla_brain_center.py`**입니다.
예전에 사용하던 `hermes_agent.py`는 STT + ZeroMQ 실험용 구버전 파일이므로 현재 최종 구조에서는 사용하지 않습니다.

---

## 2. 주요 파일 구조

권장 디렉터리 구조:

```text
~/vla_brain/
├── vla_brain_center.py              # 최종 대뇌 실행 파일
├── AGENTS.md                        # Hermes가 읽는 환경/좌표/시나리오 규칙 파일
├── memory/
│   ├── pc1_parse_errors.jsonl       # PC1 파싱/검증 오류 기록
│   └── pc1_success_packets.jsonl    # 성공적으로 생성된 Task Packet 기록
└── README.md                        # 본 문서
```

### 파일별 역할

| 파일 | 역할 |
|---|---|
| `vla_brain_center.py` | Streamlit UI, PC2 환경정보 수신, Hermes 호출, JSON 검증, PC2 전송 |
| `AGENTS.md` | warehouse/farm/mars 규칙, 좌표, task, sequence 정의 |
| `memory/pc1_parse_errors.jsonl` | Hermes/LLM 출력이 JSON 파싱 실패했을 때 기록 |
| `memory/pc1_success_packets.jsonl` | 성공적으로 PC2로 보낸 Task JSON 기록 |
| `hermes_agent.py` | 구버전. 현재 최종 구조에서는 사용하지 않음 |

---

## 3. 현재 통신 포트

`vla_brain_center.py` 상단에서 설정합니다.

```python
PC2_WS_URL = "ws://<PC2_IP>:9999"
PC1_SERVER_PORT = 8889
```

의미:

```text
PC2 → PC1: 환경 정보 JSON 전송
          PC1이 8889 포트에서 수신

PC1 → PC2: Task JSON 전송
          PC2가 9999 포트에서 수신
```

예시:

```python
PC2_WS_URL = "ws://192.168.10.36:9999"
PC1_SERVER_PORT = 8889
```

실제 IP는 실행 환경에 맞게 반드시 확인해야 합니다.

---

## 4. PC2가 PC1로 보내야 하는 입력 JSON 포맷

PC2 Vision/ROS 계층은 PC1 `ws://<PC1_IP>:8889`로 아래 형태의 JSON 문자열을 전송합니다.

```json
{
  "objects": {
    "labels": ["box", "fire extinguisher", "light bulb"],
    "counts": {
      "box": 18,
      "fire extinguisher": 1,
      "light bulb": 12
    }
  },
  "caption": "The scene is an industrial warehouse with boxes, pallets, shelves, yellow walls, concrete floor, and overhead lights.",
  "source": "florence2",
  "timestamp": "2026-06-10T12:16:10"
}
```

필수 항목:

```text
objects.labels
caption
```

권장 항목:

```text
objects.counts
source
timestamp
```

주의:

```text
사람이 보는 로그 문자열이 아니라, 반드시 json.dumps()로 만든 JSON 문자열을 보내야 함.
caption이 너무 길면 LLM 추론이 느려질 수 있으므로 1~2문장 요약 권장.
```

---

## 5. PC1이 PC2로 보내는 출력 Task JSON 포맷

PC1은 Hermes 추론 결과를 파싱/검증한 뒤 PC2 `9999` 포트로 아래 형태를 전송합니다.

```json
{
  "environment": "warehouse",
  "task": "목표 상자를 흡착 그리퍼로 잡고 컨베이어 벨트까지 이동",
  "target": "box",
  "amr_pickup_pos": [-8.2, 3.0, 1.4],
  "amr_drop_pos": [2.0, 15.0, -0.2],
  "sequence": ["move_to_box", "suction_grasp", "move_to_conveyor", "release"],
  "confidence": 0.95,
  "reason": "상자와 창고 구조물이 감지되어 warehouse로 판단함",
  "recovery_hint": "인식이 불안정하면 카메라를 재정렬 후 재시도"
}
```

현재 warehouse 최신 좌표:

```text
amr_pickup_pos: [-8.2, 3.0, 1.4]
amr_drop_pos:   [2.0, 15.0, -0.2]
```

warehouse sequence에서 `search_qr`는 제거되었습니다.

---

## 6. AGENTS.md 관리 방식

`AGENTS.md`는 Hermes가 읽는 핵심 규칙 파일입니다.
좌표나 task sequence를 바꾸고 싶으면 우선 이 파일을 수정합니다.

### 최신 warehouse 설정

```md
warehouse:
task: 목표 상자를 흡착 그리퍼로 잡고 컨베이어 벨트까지 이동
target: box
amr_pickup_pos: [-8.2, 3.0, 1.4]
amr_drop_pos: [2.0, 15.0, -0.2]
sequence: ["move_to_box", "suction_grasp", "move_to_conveyor", "release"]
```

주의:

```text
Hermes 출력이 정상일 때는 AGENTS.md의 좌표가 우선 사용됨.
코드 내부 fallback template이 남아 있다면, Hermes 출력 실패 시 fallback 좌표가 사용될 수 있음.
따라서 실제 환경 좌표를 완전히 최신화하려면 AGENTS.md와 코드 내부 FALLBACK_ENV_TEMPLATES를 함께 확인하는 것이 안전함.
```

---

## 7. 의존성 설치

### 7.1 Python 가상환경

현재 터미널에서는 `hermes_env`를 사용하는 흐름으로 정리합니다.
기존 컴퓨터에서 가상환경 이름이 `hermes_enc`라면 해당 이름으로 바꿔서 실행하면 됩니다.

```bash
cd ~
python3 -m venv hermes_env
source ~/hermes_env/bin/activate
python -m pip install --upgrade pip
```

### 7.2 Python 패키지 설치

```bash
pip install streamlit ollama websockets websocket-client streamlit-autorefresh
```

현재 Hermes CLI 버전에서는 Python 코드가 직접 `ollama.chat()`을 쓰지 않더라도, 기존 코드 호환을 위해 `ollama` 패키지는 설치해두는 것을 권장합니다.

---

## 8. Docker Ollama 설정

### 8.1 Ollama 컨테이너 실행 확인

```bash
docker ps
```

`ollama-brain`이 보이지 않으면:

```bash
docker start ollama-brain
```

### 8.2 Ollama API 확인

```bash
curl http://127.0.0.1:11434/v1/models
```

정상 예시:

```json
{
  "data": [
    {"id": "deepseek-r1:14b-64k"}
  ]
}
```

### 8.3 64K 모델이 없을 때 생성

먼저 기본 모델이 있는지 확인합니다.

```bash
docker exec -it ollama-brain ollama list
```

`deepseek-r1:14b`는 있는데 `deepseek-r1:14b-64k`가 없다면:

```bash
docker exec -i ollama-brain sh -c 'cat > /tmp/Modelfile.deepseek-r1-14b-64k' <<'MODELFILE'
FROM deepseek-r1:14b
PARAMETER num_ctx 65536
MODELFILE

docker exec -it ollama-brain ollama create deepseek-r1:14b-64k -f /tmp/Modelfile.deepseek-r1-14b-64k
```

생성 확인:

```bash
docker exec -it ollama-brain ollama list
```

---

## 9. Hermes 설정

### 9.1 Hermes 명령어 확인

```bash
hermes --help
```

정상적으로 help가 나오면 Hermes CLI 설치가 된 상태입니다.

### 9.2 Hermes 모델 설정

```bash
hermes setup model
```

선택값:

```text
Provider: Custom endpoint
API base URL: http://127.0.0.1:11434/v1
API key: ollama
API compatibility mode: Chat Completions
Model: deepseek-r1:14b-64k
```

설정 확인:

```bash
hermes config | grep -i -E "model|provider|url|context"
```

예상:

```text
Model: deepseek-r1:14b-64k
Provider: custom
Base URL: http://127.0.0.1:11434/v1
API mode: chat_completions
```

### 9.3 Hermes 단독 테스트

`~/vla_brain` 경로에서 실행해야 `AGENTS.md`를 잘 읽습니다.

```bash
cd ~/vla_brain
hermes -z 'Read AGENTS.md and follow it strictly. Return only one valid JSON object. Vision: objects box x3, shelves x1. Caption: warehouse with boxes and shelves.'
```

정상이라면 JSON이 출력됩니다.

---

## 10. 실행 순서

PC1에서 실행합니다.

```bash
cd ~/vla_brain
source ~/hermes_env/bin/activate

docker start ollama-brain
curl http://127.0.0.1:11434/v1/models

streamlit run vla_brain_center.py
```

브라우저 접속:

```text
Local URL:   http://localhost:8501
Network URL: http://<PC1_IP>:8501
```

실행 시 PC1은 자동으로 8889 포트에서 PC2 환경 정보를 기다립니다.

---

## 11. 정상 동작 로그 예시

PC2가 환경 정보를 보내면 PC1 터미널에 다음과 같이 표시됩니다.

```text
[PC 1] PC 3 수신용 백그라운드 서버 시작 (포트: 8889)
server listening on 0.0.0.0:8889
connection open
[PC 1] PC 3와 연결 성공! 데이터 대기 중...
```

버튼을 눌러 Task를 생성하면:

```text
[Hermes 백엔드] AGENTS.md 기반 Task JSON 생성 및 검증 완료.
[Hermes Tool] 코더 컴퓨터로 최종 기획서 전송 시도: ws://<PC2_IP>:9999
[Hermes Tool] 소뇌 전송 완료!
```

---

## 12. 중복 실행 방지

Streamlit 버튼을 두 번 누르면 Task가 두 번 생성될 수 있습니다.
최신 코드에서는 아래 방식으로 중복을 방지하는 것을 권장합니다.

### 12.1 session_state 추가

세션 초기화 부분에 아래 항목이 있어야 합니다.

```python
if 'run_requested' not in st.session_state:
    st.session_state['run_requested'] = False
if 'is_analyzing' not in st.session_state:
    st.session_state['is_analyzing'] = False
if 'pending_vision_input' not in st.session_state:
    st.session_state['pending_vision_input'] = ""
if 'last_sent_payload_hash' not in st.session_state:
    st.session_state['last_sent_payload_hash'] = ""
if 'last_send_blocked' not in st.session_state:
    st.session_state['last_send_blocked'] = False
```

### 12.2 버튼 동작 방식

권장 흐름:

```text
버튼 클릭
→ run_requested=True 저장
→ st.rerun()
→ 버튼 비활성화 상태에서 실제 Hermes 실행
→ 실행 완료 후 is_analyzing=False
```

### 12.3 동일 Task Packet 전송 차단

`hermes_tool_send_to_pc2()` 내부에서 payload hash를 저장해 동일 JSON이면 전송하지 않도록 합니다.

```python
payload_hash = json.dumps(validated_payload, ensure_ascii=False, sort_keys=True)

if st.session_state.get("last_sent_payload_hash") == payload_hash:
    print("[Hermes Tool] 동일 Task Packet 중복 전송 차단")
    st.session_state["last_send_blocked"] = True
    return False
```

---

## 13. 오류 해결 가이드

### 13.1 Hermes APIConnectionError / Connection error

증상:

```text
Endpoint: http://127.0.0.1:11434/v1
Error: Connection error
API call failed after 3 retries
```

원인:

```text
Ollama 컨테이너가 꺼져 있거나 11434 포트가 열려 있지 않음.
```

해결:

```bash
docker start ollama-brain
curl http://127.0.0.1:11434/v1/models
```

그래도 안 되면 포트 매핑 확인:

```bash
docker ps | grep ollama-brain
```

출력에 아래 형태가 있어야 합니다.

```text
0.0.0.0:11434->11434/tcp
```

---

### 13.2 request exceeds available context size 4096

증상:

```text
request exceeds the available context size (4096 tokens)
```

원인:

```text
deepseek-r1:14b 기본 4K 모델을 호출 중.
AGENTS.md + caption + 오류 로그가 4096 토큰을 초과함.
```

해결:

```text
Hermes model을 deepseek-r1:14b-64k로 변경.
필요하면 memory 오류 로그를 비움.
```

명령:

```bash
hermes setup model
# model: deepseek-r1:14b-64k

> ~/vla_brain/memory/pc1_parse_errors.jsonl
```

---

### 13.3 출력에서 JSON 객체를 찾을 수 없습니다

증상:

```text
[Hermes 백엔드] 에러 감지: Hermes 출력에서 JSON 오브젝트를 찾을 수 없습니다.
```

원인:

```text
Hermes/LLM이 설명문, markdown, <think>만 출력하고 JSON을 출력하지 않음.
AGENTS.md 규칙이 약하거나, prompt가 너무 복잡함.
```

해결:

1. `AGENTS.md`에 아래 규칙이 있는지 확인:

```md
Return only one valid JSON object.
Never return markdown.
Never include explanations outside JSON.
Never wrap JSON in code fences.
```

2. Hermes 단독 테스트:

```bash
cd ~/vla_brain
hermes -z 'Read AGENTS.md and follow it strictly. Return only one valid JSON object. Vision: box, shelves, warehouse.'
```

3. 너무 긴 caption을 PC2에서 요약해서 보내도록 수정.

---

### 13.4 PC2 전송 실패: Connection refused

증상:

```text
[Hermes Tool] 소뇌 전송 실패: [Errno 111] Connection refused
```

원인:

```text
PC2의 9999 WebSocket 서버가 안 켜져 있음.
PC2 IP 또는 포트가 틀림.
```

확인:

PC2에서:

```bash
ss -lntp | grep 9999
```

Windows라면:

```powershell
netstat -ano | findstr 9999
```

PC1에서:

```bash
nc -vz <PC2_IP> 9999
```

해결:

```text
PC2 수신 서버 실행.
PC2_WS_URL을 실제 PC2 IP와 포트로 수정.
```

---

### 13.5 PC2/PC1 연결이 계속 끊겼다 붙음

증상:

```text
connection open
연결 성공
연결 종료됨
connection open
연결 성공
```

원인:

```text
PC2 송신 코드가 send → ACK 수신 → close 방식이면 정상적인 현상.
```

결과를 정상적으로 받아오면 치명적인 문제는 아닙니다.
실시간 연결 유지가 필요하면 PC2 송신 코드를 persistent WebSocket loop 구조로 바꾸면 됩니다.

---

### 13.6 Streamlit missing ScriptRunContext 경고

증상:

```text
Thread 'Thread-6': missing ScriptRunContext! This warning can be ignored when running in bare mode.
```

원인:

```text
Streamlit 백그라운드 WebSocket 서버 스레드에서 발생하는 경고.
```

해결:

```text
현재 통신과 추론에는 영향이 없으므로 무시 가능.
```

---

### 13.7 AGENTS.md 좌표를 바꿨는데 반영이 안 됨

확인할 것:

1. Streamlit을 재시작했는지 확인.

```bash
Ctrl + C
streamlit run vla_brain_center.py
```

2. `vla_brain_center.py`가 Hermes 호출 시 `cwd="~/vla_brain"`에서 실행되는지 확인.

3. 코드 내부 fallback template이 옛 좌표를 갖고 있지 않은지 확인.

4. Hermes 단독 테스트로 AGENTS.md 반영 여부 확인.

```bash
cd ~/vla_brain
hermes -z 'Read AGENTS.md and follow it strictly. Vision: warehouse with boxes. Return only one valid JSON object.'
```

---

### 13.8 속도가 너무 느림

원인:

```text
DeepSeek-R1 14B는 reasoning 모델이라 Hermes CLI 경유 시 느릴 수 있음.
caption이 길거나 AGENTS.md가 길면 더 느림.
```

해결:

```text
caption을 1~2문장으로 요약.
pc1_parse_errors.jsonl이 너무 크면 비움.
필요 시 qwen 계열 경량 모델로 교체.
```

오류 로그 초기화:

```bash
> ~/vla_brain/memory/pc1_parse_errors.jsonl
```

---

## 14. 빠른 상태 점검 명령어

```bash
# 1. venv 진입
source ~/hermes_env/bin/activate

# 2. Ollama 컨테이너 확인
docker ps | grep ollama-brain

# 3. Ollama API 확인
curl http://127.0.0.1:11434/v1/models

# 4. Hermes 설정 확인
hermes config | grep -i -E "model|provider|url|context"

# 5. Hermes 단독 테스트
cd ~/vla_brain
hermes -z 'Return only JSON: {"environment":"mars"}'

# 6. PC2 포트 확인
nc -vz <PC2_IP> 9999

# 7. Streamlit 실행
streamlit run vla_brain_center.py
```

---

## 15. 데모 전 체크리스트

```text
[ ] PC1에서 docker start ollama-brain 완료
[ ] curl http://127.0.0.1:11434/v1/models 정상
[ ] Hermes model이 deepseek-r1:14b-64k로 설정됨
[ ] AGENTS.md warehouse 좌표 최신화됨
[ ] PC2_WS_URL이 실제 PC2 IP:9999로 설정됨
[ ] PC2에서 9999 WebSocket 수신 서버 실행 중
[ ] PC2가 PC1 8889 포트로 환경 JSON 전송 가능
[ ] Streamlit UI에서 Vision Text 갱신 확인
[ ] 버튼은 한 번만 클릭
[ ] PC2 수신 로그에서 Task JSON 1회 수신 확인
```

---

## 16. 현재 최신 warehouse 시나리오 요약

```text
Environment: warehouse
Target: box
Task: 목표 상자를 흡착 그리퍼로 잡고 컨베이어 벨트까지 이동
Pickup: [-8.2, 3.0, 1.4]
Drop: [2.0, 15.0, -0.2]
Sequence:
  1. move_to_box
  2. suction_grasp
  3. move_to_conveyor
  4. release
```

`search_qr` 단계는 현재 제거되었습니다.
