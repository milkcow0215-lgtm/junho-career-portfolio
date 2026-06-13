import sys
import os
import json
import re
# import zmq # 웹소켓으로 대체
import streamlit as st
import ollama

import asyncio
import threading
import websocket  # pip install websocket-client 필수
from websocket import create_connection
import websockets # yolo 수신용
from streamlit_autorefresh import st_autorefresh #pip install streamlit-autorefresh


# ==========================================
# 🌐 실행방법
# streamlit run c:/rokey/C3_project2/src/vla_brain_center.py
# python -m streamlit run c:/rokey/C3_project2/src/vla_brain_center.py
# 특정 의존성 파이썬 환경에서 실행시 hsu는 컴퓨터 사용자 이름이며 자신의 컴퓨터에 따라 변경할 것
# C:/Users/hsu/AppData/Local/Programs/Python/Python39/python.exe -m streamlit run c:/rokey/C3_project2/src/vla_brain_center.py
# ==========================================


# ==========================================
# 🌐 네트워크 주소 설정
# ==========================================
# PC 2 (소뇌)의 IP 주소를 입력하세요.
PC2_WS_URL = "ws://127.0.0.1:9999"
PC1_SERVER_PORT = 8887 # PC 3(감각)로부터 데이터를 받을 포트

# 💡 [핵심 해결책] 새로고침해도 절대 초기화되지 않는 영구 보관함 생성
@st.cache_resource
def get_vision_data_store():
    return {
        "objects": {}, 
        "caption": "실시간 데이터 대기 중..."
    }

# 징검다리 변수를 영구 보관함과 연결
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
                # 데이터 수신 즉시 로그 출력
                print(f"📥 [PC 1] 메시지 원본 길이: {len(message)}")
                data = json.loads(message)
                GLOBAL_VISION_DATA["objects"] = data.get("objects", {})
                GLOBAL_VISION_DATA["caption"] = data.get("caption", "")
                print(f"✅ [PC 1] 수신 성공: {GLOBAL_VISION_DATA['objects']}, {GLOBAL_VISION_DATA['caption'][:1000]}...")
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
        async with websockets.serve(handler, "0.0.0.0", PC1_SERVER_PORT, ping_interval=None, ping_timeout=180): # 8887로 포트 명시
            await asyncio.Future()

    asyncio.run(main_server())
    
@st.cache_resource
def start_vision_server():
    print(f"🤖 [PC 1] PC 3 수신용 백그라운드 서버 시작 (포트: {PC1_SERVER_PORT})")
    # add_script_run_ctx 등 복잡한 우회 로직 제거, 순수 스레드로 실행
    thread = threading.Thread(target=run_ws_server_for_pc3, daemon=True)
    thread.start()
    return thread

start_vision_server()

# ==========================================
# 🚀 PC 2(소뇌) 송신 및 헬퍼 함수
# ==========================================
def send_to_pc2(payload: dict):
    """만들어두신 안전한 웹소켓 전송 함수를 재활용합니다."""
    try:
        print("[PC 1] 송신용 웹소켓 시작 (포트: 9999)")
        ws = create_connection(PC2_WS_URL, timeout=10)
        ws.send(json.dumps(payload, ensure_ascii=False))
        ws.close()
        return True
    except Exception as e:
        st.error(f"🚨 PC 2(소뇌) 통신 실패: {e}\n네트워크와 포트(9999) 개방을 확인하세요.")
        return False


# =====================================================================
# 🧠 2. DeepSeek-R1 <think> 제거 및 JSON 추출 헬퍼 함수
# =====================================================================

def extract_json_from_r1(text: str) -> dict:
    clean_text = re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL).strip()
    match = re.search(r'\{.*\}', clean_text, re.DOTALL)
    if match:
        return json.loads(match.group(0))
    raise ValueError("출력 결과에서 유효한 JSON 구조를 찾을 수 없습니다.")


# =====================================================================
# 🖥️ 3. 대뇌 관제 센터 UI 렌더링 (Streamlit)
# =====================================================================
st.set_page_config(page_title="VLA 대뇌 관제 센터", layout="wide")
st.title("🧠 3-PC VLA - 대뇌 자율 인지 시스템 (PC 1)")
st.caption("비전 언어 모델(Florence-2) 텍스트 분석 및 자율 환경 템플릿 매핑")

st.divider()

# 💡 [핵심 추가] 추론 중인지 확인하는 상태 변수와 버튼 콜백 함수
if 'is_analyzing' not in st.session_state:
    st.session_state['is_analyzing'] = False

def trigger_analysis():
    # 버튼이 눌리면 이 함수가 가장 먼저 실행되어 새로고침을 차단합니다.
    st.session_state['is_analyzing'] = True


if 'refined_json' not in st.session_state:
    st.session_state['refined_json'] = None

col_input, col_status = st.columns([2, 1])

with col_input:
    st.markdown("### 👁️ 비전 모델 (Florence-2) 실시간 상황 인식 데이터")
    
    if not st.session_state['is_analyzing']:
        st_autorefresh(interval=2000, limit=None, key="vision_autorefresh")
    if st.button("🔄 수신 데이터 새로고침", use_container_width=True):
        st.rerun()
    
    # 💡 징검다리(전역 변수)에서 직접 데이터 가져오기
    received_data = GLOBAL_VISION_DATA
    caption = received_data.get("caption", "실시간 데이터 대기 중...")
    
    objects_raw = received_data.get("objects", {})
    if isinstance(objects_raw, dict) and "labels" in objects_raw:
        labels = objects_raw["labels"]
        unique_labels = sorted(set(labels))
        objects_str = ", ".join([f"{label} x{labels.count(label)}" for label in unique_labels])
    else:
        objects_str = "탐지된 물체 없음"

    formatted_vision_text = f"탐지된 물체: {objects_str}\n설명: {caption}"
    
    vision_input = st.text_area("현재 시야 설명 (Vision Text):", value=formatted_vision_text, height=150)
    
    with st.expander("🛠️ 수신된 원본 JSON 데이터 확인"):
        st.json(received_data)

# with col_input:
#     st.markdown("### 👁️ 비전 모델 (Florence-2) 상황 인식 데이터 수신")
    
#     # 빠른 테스트를 위한 예시 데이터 프리셋
#     preset = st.radio("테스트 시나리오 선택:", ["물류창고 (테스트)", "농장 (테스트)"])
#     if preset == "농장 (테스트)":
#         default_vision_text = """탐지된 물체: land vehicle x1, wheel x3
# 설명: The image shows a tractor plowing a field at sunset. The tractor is green and is in the center of the image... The field is vast and green, with rows of crops stretching out in all directions."""
#     else:
#         default_vision_text = """탐지된 물체: cardboard box x5, conveyor belt x1, forklift x1
# 설명: The image shows the inside of a large logistics warehouse. There are tall racks filled with packages and cardboard boxes. A conveyor belt is running in the center, and a forklift is parked nearby."""

#     vision_input = st.text_area("현재 시야 설명 (Vision Text):", value=default_vision_text, height=150)

# with col_status:
#     st.markdown("### 📋 사전 정의된 환경 템플릿")
#     st.info("1. **물류창고**: 상자 QR 탐색 ➔ 흡착 파지 ➔ 컨베이어벨트\n2. **농장**: 작물 확인 ➔ 절단 ➔ 바구니\n3. **화성**: 암석 탐색 ➔ 샘플 채취 ➔ 분석기")
#     if st.button("❌ 상태 및 로그 초기화", use_container_width=True):
#         st.session_state['refined_json'] = None
#         st.rerun()

# st.divider()

# =====================================================================
# 🚀 4. 시나리오 기획 및 소뇌 전송 로직
# =====================================================================
if vision_input:
    if st.button("▶️ 자율 환경 분석 및 태스크 기획 (소뇌 전송)", type="primary", use_container_width=True, on_click=trigger_analysis):
        st.session_state['is_analyzing'] = True  # 분석 시작 플래그 설정
        with st.spinner("🧠 DeepSeek-R1이 시야를 분석하여 환경을 추론 중..."):
            try:
                # 💡 핵심: 환경 매핑 템플릿 프롬프트
                system_prompt = """
                너는 로봇 제어 VLA 시스템의 대뇌 에이전트(Hermes)다.
                로봇의 시각 모델(Florence-2)이 분석한 텍스트 데이터가 주어질 것이다.
                너의 역할은 시각 데이터를 분석해 현재 로봇이 위치한 '환경'을 다음 3가지 템플릿 중에서 하나로 확정하고, 그에 맞는 '사전 정의된 태스크'를 할당하는 것이다.

                [환경 템플릿 및 할당 태스크]
                1. 물류창고 (Warehouse):
                    - 힌트: 상자, 박스, 선반, 컨베이어 벨트, 지게차 등
                    - 사전 정의 태스크: "목표 상자 QR을 찾아서 흡착 그리퍼로 잡고 컨베이어 벨트까지 이동"
                    - 시퀀스 예시: ["search_qr", "move_to_box", "suction_grasp", "move_to_conveyor", "release"]
                2. 농장 (Farm):
                    - 힌트: 트랙터, 식물, 작물, 밭, 흙 등
                    - 사전 정의 태스크: "성숙한 작물을 식별하고 절단 그리퍼로 수확하여 바구니에 담기"
                    - 시퀀스 예시: ["scan_crops", "move_to_plant", "cut_crop", "move_to_basket", "release"]
                3. 화성 (Mars):
                    - 힌트: 붉은 흙, 분화구, 암석, 탐사선 등
                    - 사전 정의 태스크: "지정된 암석 샘플을 채취하여 탐사선 분석기 슬롯에 삽입"
                    - 시퀀스 예시: ["scan_rock", "move_to_rock", "grasp_sample", "move_to_analyzer", "insert"]

                [절대 규칙]
                - 시각 데이터를 바탕으로 위 3가지 환경 중 하나만 선택해라.
                - 반드시 아래 포맷의 JSON 데이터만 출력해라. 
                - Format: {"environment": "물류창고", "task": "사전 정의 태스크 내용", "target": "조작할 대상", "sequence": ["배열", "형태"]}
                """
                
                response = ollama.chat(
                    model='deepseek-r1:14b', # 실재 사용하는 모델
                    # model='llama3', # 테스트용도
                    messages=[
                        {'role': 'system', 'content': system_prompt},
                        {'role': 'user', 'content': f"[시야 데이터]\n{vision_input}"}
                    ],
                    options={'temperature': 0.1} # 환경 매핑은 일관성이 중요하므로 온도를 더 낮춤
                )
                
                raw_output = response['message']['content']
                
                with st.expander("🔍 DeepSeek-R1 환경 분석 사고 과정 (<think> 로그)"):
                    st.text(raw_output)
                
                refined_data = extract_json_from_r1(raw_output)
                st.session_state['refined_json'] = refined_data
                
                # 안전하게 만들어둔 헬퍼 함수 사용
                with st.spinner("📡 웹소켓을 통해 PC 2(소뇌)로 데이터 패킷 전송 중..."):
                    success = send_to_pc2(refined_data)
                    
                if success:
                    st.balloons()
                
            except Exception as e:
                st.error(f"🚨 대뇌 기획 및 파싱 에러 발생: {e}")

if st.session_state['refined_json']:
    st.markdown("### 📥 [Hermes 필터 적용] 소뇌(PC 2)로 전송된 최종 태스크 패킷")
    st.json(st.session_state['refined_json'])
    st.success("⚡ 확정된 태스크 시나리오가 PC 2(소뇌) 계층으로 전송되었습니다.")