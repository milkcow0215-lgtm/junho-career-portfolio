import sys
import os
import json
import re
import subprocess
import streamlit as st
# import ollama  # Hermes CLI 호출 방식에서는 직접 사용하지 않음

import asyncio
import threading
import websocket  # pip install websocket-client 필수
from websocket import create_connection
import websockets # yolo 수신용
from streamlit_autorefresh import st_autorefresh # pip install streamlit-autorefresh
from datetime import datetime 
# ==========================================
# 🌐 네트워크 및 환경 주소 설정
# ==========================================
PC2_WS_URL = "ws://192.168.10.36:9999"
PC1_SERVER_PORT = 8889
PROJECT_DIR = os.path.expanduser("~/vla_brain")
AGENTS_MD_PATH = os.path.join(PROJECT_DIR, "AGENTS.md")

@st.cache_resource
def get_vision_data_store():
    return {
        "objects": {},
        "caption": "실시간 데이터 대기 중..."
    }

GLOBAL_VISION_DATA = get_vision_data_store()

# ==========================================
# 📡 PC 3(Vision) 데이터 수신용 백그라운드 웹소켓 서버
# ==========================================
def run_ws_server_for_pc3():
    async def handler(websocket):
        global GLOBAL_VISION_DATA
        print(f"📡 [PC 1] PC 3와 연결 성공! 데이터 대기 중...")
        try:
            async for message in websocket:
                data = json.loads(message)
                GLOBAL_VISION_DATA["objects"] = data.get("objects", {})
                GLOBAL_VISION_DATA["caption"] = data.get("caption", "")
                await websocket.send("ACK")
            try:
                st.rerun()
            except:
                pass
        except Exception as e:
            print(f"❌ [PC 1] 수신 에러: {e}")
        finally:
            print("🛑 [PC 1] 연결 종료됨")

    async def main_server():
        async with websockets.serve(handler, "0.0.0.0", PC1_SERVER_PORT, ping_interval=None, ping_timeout=180):
            await asyncio.Future()

    asyncio.run(main_server())

@st.cache_resource
def start_vision_server():
    print(f"🤖 [PC 1] PC 3 수신용 백그라운드 서버 시작 (포트: {PC1_SERVER_PORT})")
    thread = threading.Thread(target=run_ws_server_for_pc3, daemon=True)
    thread.start()
    return thread

start_vision_server()

# =====================================================================
# 🛠️ [Hermes 전용 도구] 완벽 검증된 JSON 패킷을 PC 2(소뇌)로 토스하는 스킬
# =====================================================================
def hermes_tool_send_to_pc2(validated_payload: dict) -> bool:
    """
    Hermes Agent가 최종 가드레일을 통과시킨 무결성 JSON을
    하위 로봇 코더 계층으로 안전하게 발행하는 전용 스킬 도구입니다.
    """
    try:
        payload_hash = json.dumps(validated_payload, ensure_ascii=False, sort_keys=True)

        if st.session_state.get("last_sent_payload_hash") == payload_hash:
            print("⚠️ [Hermes Tool] 동일 Task Packet 중복 전송 차단")
            st.session_state["last_send_blocked"] = True
            return False

        st.session_state["last_send_blocked"] = False

        print(f"🚀 [Hermes Tool] 코더 컴퓨터로 최종 기획서 전송 시도: {PC2_WS_URL}")
        ws = create_connection(PC2_WS_URL, timeout=10)
        ws.send(json.dumps(validated_payload, ensure_ascii=False))
        ws.close()

        st.session_state["last_sent_payload_hash"] = payload_hash

        print("✅ [Hermes Tool] 소뇌 전송 완료!")
        return True

    except Exception as e:
        print(f"🚨 [Hermes Tool] 소뇌 전송 실패: {e}")
        return False
    
# =====================================================================
# 🧠 PC1 오류 기억 저장소 + Task Packet Normalize / Validate
# =====================================================================

PC1_PARSE_ERROR_LOG = os.path.expanduser("~/vla_brain/memory/pc1_parse_errors.jsonl")
PC1_SUCCESS_LOG = os.path.expanduser("~/vla_brain/memory/pc1_success_packets.jsonl")

ENV_TEMPLATES = {
    "warehouse": {
        "task": "목표 상자 QR을 찾아서 흡착 그리퍼로 잡고 컨베이어 벨트까지 이동",
        "target": "box",
        "amr_pickup_pos": [-6.0, -1.0, 0.0],
        "amr_drop_pos": [-10.0, -5.0, 0.0],
        "sequence": ["search_qr", "move_to_box", "suction_grasp", "move_to_conveyor", "release"],
    },
    "farm": {
        "task": "성숙한 작물을 식별하고 절단 그리퍼로 수확하여 바구니에 담기",
        "target": "crop",
        "amr_pickup_pos": [2.5, 4.0, 0.0],
        "amr_drop_pos": [7.0, -2.5, 0.0],
        "sequence": ["scan_crops", "move_to_plant", "cut_crop", "move_to_basket", "release"],
    },
    "mars": {
        "task": "지정된 암석 샘플을 채취하여 탐사선 분석기 슬롯에 삽입",
        "target": "rock",
        "amr_pickup_pos": [15.0, -3.0, 0.5],
        "amr_drop_pos": [0.0, 0.0, 0.0],
        "sequence": ["scan_rock", "move_to_rock", "grasp_sample", "move_to_analyzer", "insert"],
    },
}

def now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")

def append_jsonl(path: str, data: dict):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(data, ensure_ascii=False) + "\n")

def load_recent_jsonl(path: str, limit: int = 5) -> str:
    if not os.path.exists(path):
        return "No records."
    with open(path, "r", encoding="utf-8") as f:
        lines = f.readlines()[-limit:]
    return "".join(lines) if lines else "No records."

def load_recent_pc1_parse_errors(limit: int = 5) -> str:
    return load_recent_jsonl(PC1_PARSE_ERROR_LOG, limit)

def append_pc1_parse_error(vision_text: str, raw_output: str, error_message: str, stage: str):
    append_jsonl(PC1_PARSE_ERROR_LOG, {
        "type": "pc1_parse_error",
        "timestamp": now_iso(),
        "stage": stage,
        "vision_text": vision_text,
        "raw_output": raw_output,
        "error": error_message,
        "lesson": "다음 출력에서는 JSON schema를 엄격히 지키고 target은 box/crop/rock 중 하나만 사용한다."
    })

def append_pc1_success_packet(vision_text: str, final_packet: dict):
    append_jsonl(PC1_SUCCESS_LOG, {
        "type": "pc1_success_packet",
        "timestamp": now_iso(),
        "vision_text": vision_text,
        "final_packet": final_packet,
    })

def normalize_environment(value: str) -> str:
    value = str(value).strip().lower()
    mapping = {
        "물류창고": "warehouse",
        "창고": "warehouse",
        "warehouse": "warehouse",
        "farm": "farm",
        "농장": "farm",
        "mars": "mars",
        "화성": "mars",
    }
    return mapping.get(value, value)

def _as_xyz(value, fallback):
    """좌표가 [x, y, z] 숫자 배열이면 그대로 사용하고, 아니면 fallback을 사용."""
    if isinstance(value, list) and len(value) == 3:
        try:
            return [float(value[0]), float(value[1]), float(value[2])]
        except Exception:
            pass
    return fallback

def normalize_task_packet(data: dict) -> dict:
    """
    Hermes/AGENTS.md가 생성한 값을 우선 사용한다.
    단, 누락되거나 깨진 필드는 ENV_TEMPLATES를 fallback으로 사용한다.
    """
    env = normalize_environment(data.get("environment", ""))

    if env not in ENV_TEMPLATES:
        raise ValueError(f"알 수 없는 environment 값입니다: {env}")

    template = ENV_TEMPLATES[env]

    confidence = data.get("confidence", 0.8)
    try:
        confidence = float(confidence)
    except Exception:
        confidence = 0.8
    confidence = max(0.0, min(1.0, confidence))

    reason = str(data.get("reason", "")).strip()
    recovery_hint = str(data.get("recovery_hint", "")).strip()

    if not reason:
        reason = f"{env} 환경 단서가 감지되어 해당 시나리오로 판단함"
    if not recovery_hint:
        recovery_hint = "인식이 불안정하면 카메라를 재정렬 후 재시도"

    task = str(data.get("task", template["task"])).strip() or template["task"]
    target = str(data.get("target", template["target"])).strip() or template["target"]

    sequence = data.get("sequence", template["sequence"])
    if not isinstance(sequence, list) or not all(isinstance(x, str) for x in sequence):
        sequence = template["sequence"]

    return {
        "environment": env,
        "task": task,
        "target": target,
        "amr_pickup_pos": _as_xyz(data.get("amr_pickup_pos"), template["amr_pickup_pos"]),
        "amr_drop_pos": _as_xyz(data.get("amr_drop_pos"), template["amr_drop_pos"]),
        "sequence": sequence,
        "confidence": confidence,
        "reason": reason[:120],
        "recovery_hint": recovery_hint[:120],
    }

def validate_task_packet(packet: dict) -> bool:
    """
    최종 송신 전 구조 검증.
    AGENTS.md에서 좌표/시퀀스를 바꿀 수 있도록 값 자체를 고정 비교하지 않고,
    타입과 필수 키 중심으로만 검증한다.
    """
    required_keys = [
        "environment", "task", "target", "amr_pickup_pos", "amr_drop_pos",
        "sequence", "confidence", "reason", "recovery_hint"
    ]

    for key in required_keys:
        if key not in packet:
            raise ValueError(f"필수 key 누락: {key}")

    env = packet["environment"]
    if env not in ENV_TEMPLATES:
        raise ValueError(f"environment 값 오류: {env}")

    if not isinstance(packet["task"], str) or not packet["task"].strip():
        raise ValueError("task는 비어 있지 않은 문자열이어야 합니다.")

    if not isinstance(packet["target"], str) or not packet["target"].strip():
        raise ValueError("target은 비어 있지 않은 문자열이어야 합니다.")

    for pos_key in ["amr_pickup_pos", "amr_drop_pos"]:
        pos = packet[pos_key]
        if not isinstance(pos, list) or len(pos) != 3:
            raise ValueError(f"{pos_key}는 숫자 3개짜리 리스트여야 합니다.")
        for v in pos:
            if not isinstance(v, (int, float)):
                raise ValueError(f"{pos_key} 내부 값은 숫자여야 합니다: {pos}")

    if not isinstance(packet["sequence"], list) or not packet["sequence"]:
        raise ValueError("sequence는 비어 있지 않은 문자열 리스트여야 합니다.")
    if not all(isinstance(x, str) and x.strip() for x in packet["sequence"]):
        raise ValueError("sequence 내부 값은 비어 있지 않은 문자열이어야 합니다.")

    if not isinstance(packet["confidence"], (int, float)):
        raise ValueError("confidence는 숫자여야 합니다.")

    return True

# =====================================================================
# 🧠 Hermes Agent Core 오케스트레이션 엔진 (Hermes CLI + AGENTS.md + Ollama)
# =====================================================================
class IntegratedHermesAgent:
    def __init__(self, hermes_cmd="hermes"):
        self.hermes_cmd = hermes_cmd

    def _load_agents_md(self) -> str:
        if not os.path.exists(AGENTS_MD_PATH):
            raise FileNotFoundError(
                f"AGENTS.md를 찾을 수 없습니다: {AGENTS_MD_PATH}\n"
                "좌표/시나리오를 AGENTS.md에 정의한 뒤 다시 실행하세요."
            )
        with open(AGENTS_MD_PATH, "r", encoding="utf-8") as f:
            return f.read()

    def _call_hermes(self, prompt: str, timeout: int = 600) -> str:
        """
        Hermes CLI를 비대화형으로 호출한다.
        Hermes 설정은 사전에 `hermes setup model`에서 custom endpoint
        http://127.0.0.1:11434/v1 + deepseek-r1:14b-64k 로 잡아둔다.
        """
        result = subprocess.run(
            [self.hermes_cmd, "-z", prompt],
            cwd=PROJECT_DIR,
            capture_output=True,
            text=True,
            timeout=timeout,
        )

        if result.returncode != 0:
            raise RuntimeError(
                "Hermes CLI 호출 실패\n"
                f"[STDERR]\n{result.stderr}\n\n"
                f"[STDOUT]\n{result.stdout}"
            )

        return result.stdout.strip()

    def run_cycle(self, vision_text: str):
        """Hermes가 AGENTS.md를 바탕으로 환경 추론 및 Task JSON 생성을 수행."""
        max_retries = 3
        recent_errors = load_recent_pc1_parse_errors(limit=3)
        agents_md = self._load_agents_md()

        current_prompt = f"""
너는 PC1 VLA Brain이다.
아래 AGENTS.md 규칙을 최우선으로 따르고, Vision 입력을 분석해서 PC2로 보낼 Task JSON을 생성하라.

[AGENTS.md]
{agents_md}

[최근 PC1 파싱/검증 오류 기록]
{recent_errors}

[Vision Input]
{vision_text}

[출력 규칙]
- 반드시 JSON object 하나만 출력한다.
- Markdown code block을 쓰지 않는다.
- <think> 내용, 설명문, 주석을 출력하지 않는다.
- 필수 키:
  environment, task, target, amr_pickup_pos, amr_drop_pos, sequence, confidence, reason, recovery_hint
"""

        raw_text = ""

        for attempt in range(1, max_retries + 1):
            try:
                if attempt > 1:
                    print(f"🔄 [Hermes 백엔드] {attempt}차 자가 치유(Self-Correction) 명령 가동.")

                raw_text = self._call_hermes(current_prompt)

                clean_text = re.sub(r'<think>.*?</think>', '', raw_text, flags=re.DOTALL).strip()
                json_match = re.search(r'\{.*\}', clean_text, re.DOTALL)
                if not json_match:
                    raise ValueError("Hermes 출력에서 JSON 오브젝트를 찾을 수 없습니다.")

                parsed_json = json.loads(json_match.group(0))

                final_json = normalize_task_packet(parsed_json)
                validate_task_packet(final_json)
                append_pc1_success_packet(vision_text, final_json)

                print("🎯 [Hermes 백엔드] AGENTS.md 기반 Task JSON 생성 및 검증 완료.")
                send_result = hermes_tool_send_to_pc2(final_json)

                return final_json, raw_text, send_result

            except Exception as error_msg:
                print(f"❌ [Hermes 백엔드] 에러 감지: {str(error_msg)}")
                append_pc1_parse_error(
                    vision_text=vision_text,
                    raw_output=raw_text,
                    error_message=str(error_msg),
                    stage=f"attempt_{attempt}",
                )

                current_prompt += f"""

[Hermes 가드레일 피드백]
직전 출력이 실패했다.
원인: {str(error_msg)}

수정 지시:
- 오직 JSON object 하나만 다시 출력하라.
- 필수 키를 모두 포함하라.
- 좌표는 반드시 [x, y, z] 숫자 배열로 출력하라.
- sequence는 문자열 리스트로 출력하라.
"""

        return None, "3회 자가 치유 루프 내 실패", False

# 에이전트 객체 선언
hermes_core = IntegratedHermesAgent()

# =====================================================================
# 🖥️ 스트림릿 프론트엔드 UI 파트
# =====================================================================
st.set_page_config(page_title="VLA 대뇌 관제 센터", layout="wide")
st.title("🧠 3-PC VLA - 대뇌 자율 인지 시스템 (PC 1)")
st.caption("Nous Hermes 에이전트 프레임워크 기반 작업 관리 및 자가 치유 레이어 통합")

st.divider()

if 'is_analyzing' not in st.session_state:
    st.session_state['is_analyzing'] = False
if 'refined_json' not in st.session_state:
    st.session_state['refined_json'] = None
if 'think_log' not in st.session_state:
    st.session_state['think_log'] = ""

if 'run_requested' not in st.session_state:
    st.session_state['run_requested'] = False

if 'pending_vision_input' not in st.session_state:
    st.session_state['pending_vision_input'] = ""

if 'last_sent_payload_hash' not in st.session_state:
    st.session_state['last_sent_payload_hash'] = ""

if 'last_send_blocked' not in st.session_state:
    st.session_state['last_send_blocked'] = False
col_input, col_status = st.columns([2, 1])

with col_input:
    st.markdown("### 👁️ 비전 모델 (Florence-2) 실시간 상황 인식 데이터")

    if not st.session_state['is_analyzing']:
        st_autorefresh(interval=2000, limit=None, key="vision_autorefresh")
        
    if st.button("🔄 수신 데이터 새로고침", use_container_width=True):
        st.rerun()

    received_data = GLOBAL_VISION_DATA
    caption = received_data.get("caption", "실시간 데이터 대기 중...")
    objects_raw = received_data.get("objects", {})
    
    if isinstance(objects_raw, dict) and "counts" in objects_raw:
        counts = objects_raw["counts"]
        objects_str = ", ".join([f"{label} x{count}" for label, count in counts.items()])
    elif isinstance(objects_raw, dict) and "labels" in objects_raw:
        labels = objects_raw["labels"]
        unique_labels = sorted(set(labels))
        objects_str = ", ".join([f"{label} x{labels.count(label)}" for label in unique_labels])
    else:
        objects_str = "탐지된 물체 없음"

    formatted_vision_text = f"탐지된 물체: {objects_str}\n설명: {caption}"
    vision_input = st.text_area("현재 시야 설명 (Vision Text):", value=formatted_vision_text, height=150)

    with st.expander("🛠️ 수신된 원본 JSON 데이터 확인"):
        st.json(received_data)

# =====================================================================
# 🚀 Hermes 에이전트 구동 트리거
# =====================================================================
if vision_input:
    if st.button(
        "▶️ Hermes Agent 자율 관제 및 태스크 할당 시작",
        type="primary",
        use_container_width=True,
        disabled=st.session_state.get("is_analyzing", False)
    ):
        if not st.session_state.get("is_analyzing", False):
            st.session_state["is_analyzing"] = True
            st.session_state["run_requested"] = True
            st.session_state["pending_vision_input"] = vision_input
            st.rerun()


if st.session_state.get("run_requested", False) and st.session_state.get("is_analyzing", False):
    # 같은 요청이 rerun 때문에 반복 실행되지 않도록 먼저 False 처리
    st.session_state["run_requested"] = False

    pending_input = st.session_state.get("pending_vision_input", vision_input)

    try:
        with st.spinner("🤖 Nous Hermes Agent가 AGENTS.md 기반으로 환경 추론 및 Task JSON 생성을 진행 중..."):
            result_json, raw_thinking, is_sent = hermes_core.run_cycle(pending_input)

            st.session_state["refined_json"] = result_json
            st.session_state["think_log"] = raw_thinking

            if is_sent:
                st.balloons()
            elif st.session_state.get("last_send_blocked", False):
                st.warning("⚠️ 동일한 Task Packet이라 중복 전송을 차단했습니다.")
            elif result_json is None:
                st.error("🚨 Hermes Agent가 자가 치유(Self-Correction)에 최종 실패했습니다. 로그를 검토하세요.")

    finally:
        st.session_state["is_analyzing"] = False
        st.rerun()

# 결과 출력 창
if st.session_state['think_log']:
    with st.expander("🔍 DeepSeek-R1 사고 과정 (<think> 로그)"):
        st.text(st.session_state['think_log'])

if st.session_state['refined_json']:
    st.markdown("### 📥 [Hermes Agent 가드레일 통과] 소뇌(PC 2)로 전송된 최종 보전 태스크 패킷")
    st.json(st.session_state['refined_json'])
    st.success("⚡ Hermes Agent 전송 도구가 무결성이 확보된 데이터를 소뇌(PC 2) 계층으로 안전하게 송신 완료했습니다.")
    with st.expander("🧠 PC1 Hermes 최근 파싱/검증 오류 기억"):
        st.text(load_recent_pc1_parse_errors(limit=5))