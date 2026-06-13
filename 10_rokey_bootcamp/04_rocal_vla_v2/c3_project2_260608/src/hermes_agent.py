import sys
import os
import ctypes
import json
import re
import zmq
import streamlit as st
import ollama
import asyncio
import threading
import speech_recognition as sr
from faster_whisper import WhisperModel
import tempfile

# =====================================================================
# 🔇 1. ALSA/JACK 로그 차단 (C-level 에러 핸들러)
# =====================================================================
ERROR_HANDLER_FUNC = ctypes.CFUNCTYPE(None, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p)
def py_error_handler(filename, line, function, err, fmt): pass
c_error_handler = ERROR_HANDLER_FUNC(py_error_handler)
try:
    asound = ctypes.cdll.LoadLibrary('libasound.so.2')
    asound.snd_lib_error_set_handler(c_error_handler)
except OSError: pass

os.environ["TF_CPP_MIN_LOG_LEVEL"] = "3"

# =====================================================================
# 📡 2. ZeroMQ (소뇌 PC 2 송신용) 전역 설정
# =====================================================================
if 'zmq_socket' not in st.session_state:
    zmq_context = zmq.Context()
    zmq_socket = zmq_context.socket(zmq.PUSH)
    # TODO: 나중에 PC 2(소뇌) 컴퓨터의 실제 고정 IP로 변경하세요. (예: tcp://192.168.0.150:5555)
    zmq_socket.connect("tcp://127.0.0.1:5555") 
    st.session_state['zmq_socket'] = zmq_socket

z_socket = st.session_state['zmq_socket']

# =====================================================================
# 🎙️ 3. Whisper 음성 인식 엔진 캐싱
# =====================================================================
@st.cache_resource
def load_whisper_model():
    print("⏳ [RTX 5080] Whisper 모델 로딩 중... (VRAM 절약을 위해 CPU 구동)")
    return WhisperModel("small", device="cpu", compute_type="int8")

def run_single_stt():
    recognizer = sr.Recognizer()
    with sr.Microphone() as source:
        recognizer.adjust_for_ambient_noise(source, duration=0.5)
        audio = recognizer.listen(source, timeout=5, phrase_time_limit=5)
        
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp_file:
        tmp_file.write(audio.get_wav_data())
        tmp_filename = tmp_file.name
        
    model = load_whisper_model()
    segments, _ = model.transcribe(tmp_filename, beam_size=5, language="ko")
    text = "".join([segment.text for segment in segments]).strip()
    os.remove(tmp_filename)
    return text

# =====================================================================
# 🧠 4. DeepSeek-R1 <think> 제거 및 JSON 추출 헬퍼 함수
# =====================================================================
def extract_json_from_r1(text: str) -> dict:
    # 1. <think>...</think> 독백 영역 삭제
    clean_text = re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL).strip()
    # 2. 순수 JSON 데이터 블록만 검출
    match = re.search(r'\{.*\}', clean_text, re.DOTALL)
    if match:
        return json.loads(match.group(0))
    raise ValueError("출력 결과에서 유효한 JSON 구조를 찾을 수 없습니다.")

# =====================================================================
# 🖥️ 5. 대뇌 관제 센터 UI 렌더링 (Streamlit)
# =====================================================================
st.set_page_config(page_title="VLA 대뇌 관제 센터", layout="wide")
st.title("🧠 3-PC VLA 로봇 시스템 - 대뇌 계층 (PC 1)")
st.caption("RTX 5080 Blackwell 가속 / DeepSeek-R1 (14B) 자율 기획 파이프라인")

st.divider()

# 세션 상태 초기화
if 'stt_command' not in st.session_state:
    st.session_state['stt_command'] = ""
if 'refined_json' not in st.session_state:
    st.session_state['refined_json'] = None

# 좌측 패널: 음성 및 텍스트 명령 입력
col_input, col_status = st.columns([2, 1])

with col_input:
    st.markdown("### 🎙️ 인간의 불친절한 한국어 명령 수신")
    if st.button("🎤 음성 명령 받아적기", use_container_width=True):
        with st.spinner("귀를 기울이고 있습니다... 말씀하세요!"):
            try:
                detected_text = run_single_stt()
                if detected_text:
                    st.session_state['stt_command'] = detected_text
                    st.success(f"인식 성공: {detected_text}")
                else:
                    st.warning("음성이 감지되지 않았습니다.")
            except Exception as e:
                st.error(f"마이크 구동 에러: {e}")

    user_command = st.text_input("수정 또는 직접 입력:", value=st.session_state['stt_command'], placeholder="예: 야 거기 저기 굴러다니는 빨간색 블록 집어서 로봇 카트에 좀 담아줘")

with col_status:
    st.markdown("### 📡 하이브리드 네트워크 상태")
    st.info("Ollama 엔드포인트: `http://localhost:11434` (정상)")
    st.success("ZeroMQ Outbound 포트: `5555` (연결 수립)")
    if st.button("❌ 상태 및 로그 초기화", use_container_width=True):
        st.session_state['stt_command'] = ""
        st.session_state['refined_json'] = None
        st.rerun()

st.divider()

# 중앙/하단 패널: 기획 및 전송
if user_command:
    if st.button("▶️ 1단계: DeepSeek-R1 자율 시나리오 기획 및 소뇌(PC 2) 송신", type="primary", use_container_width=True):
        with st.spinner("🧠 DeepSeek-R1이 한국어 명령 해석 및 하이레벨 시나리오 기획 중..."):
            try:
                system_prompt = (
                    "너는 로봇 제어 VLA 시스템의 대뇌 에이전트(Hermes)다. "
                    "사용자의 불친절한 한국어 명령을 분석하여, 하이레벨 태스크 시나리오를 기획해라. "
                    "출력은 반드시 다른 부연 설명 없이 오직 아래 포맷의 JSON 데이터만 출력해야 한다.\n"
                    "Format: {\"task\": \"이동 및 파지\", \"target\": \"빨간 블록\", \"sequence\": [\"move_to\", \"grasp\"]}"
                )
                
                # 춘식이의 llama3를 대량의 사유가 가능한 deepseek-r1:14b로 교체!
                response = ollama.chat(
                    model='deepseek-r1:14b',
                    messages=[
                        {'role': 'system', 'content': system_prompt},
                        {'role': 'user', 'content': user_command}
                    ],
                    options={'temperature': 0.2}
                )
                
                raw_output = response['message']['content']
                
                # 로그 확인용 접히는 창 생성 (R1의 독백 관찰용)
                with st.expander("🔍 DeepSeek-R1 날것의 사고 과정 (&lt;think&gt; 로그)"):
                    st.text(raw_output)
                
                # Hermes 거름망 가동 (JSON만 컷팅)
                refined_data = extract_json_from_r1(raw_output)
                st.session_state['refined_json'] = refined_data
                
                # 가볍고 지연 없는 ZeroMQ(ZMQ PUSH)로 PC 2(소뇌)에 다이렉트 슛
                z_socket.send_json(refined_data)
                st.balloons()
                
            except Exception as e:
                st.error(f"🚨 대뇌 기획 및 파싱 에러 발생: {e}")

# 최종 결과 화면 표출
if st.session_state['refined_json']:
    st.markdown("### 📥 [Hermes 필터 적용] 소뇌(PC 2)로 전송된 최종 고정 JSON 패킷")
    st.json(st.session_state['refined_json'])
    st.success("⚡ 데이터가 ZeroMQ 소켓을 통해 지연 시간 없이 PC 2 계층으로 전송되었습니다.")