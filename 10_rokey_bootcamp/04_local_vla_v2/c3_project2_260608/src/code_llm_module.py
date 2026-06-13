import ollama
import json
import time
import subprocess
import gc
import re

import asyncio
import websockets

# 방금 만든 ROS2 Nav2 모듈을 실제로 임포트합니다!
import move_controller 

# (선택) 비전/그리퍼 제어를 위한 torch 모듈 임포트
# import torch 

# ==========================================
# 🌐 실행방법
# move_controller.py 파일을 컬컴빌드하여 ROS2 환경에서 실행.
# 이 파일을 실행
# ==========================================
model = 'qwen3-coder:30b'
# test_model = 'qwen2.5-coder:1.5b' #GTX1650 저사양 테스트용 모델 (실제 운영에서는 qwen3-coder:30b 사용 권장

# ==========================================
# 📡 PC 1(대뇌) 명령 수신용 웹소켓 서버
# ==========================================
async def pc1_command_handler(websocket):
    print("📡 [PC 2] PC 1 (대뇌 관제 센터) 연결 수립 완료!")
    try:
        async for message in websocket:
            task_data = json.loads(message)
            print(f"📥 [PC 2] 명령 수신: {task_data.get('task', '알 수 없는 명령')}")
            
            # 💡 [핵심 수정]: 동기 함수(LLM 추론, 로봇 이동 대기)로 인해 웹소켓이 멈추는 것을 방지
            # 스레드를 분리하여 로봇이 움직이는 동안에도 웹소켓 핑/퐁이 유지되도록 합니다.
            await asyncio.to_thread(run_task_pipeline, model, task_data)
            
    except websockets.exceptions.ConnectionClosed:
        print("🛑 [PC 2] PC 1 연결 종료")

async def main_server():
    print("🤖 [PC 2] 소뇌 제어 모듈 대기 중 (포트: 9999)...")
    # PC 1에서 접근할 수 있도록 0.0.0.0 개방
    async with websockets.serve(pc1_command_handler, "0.0.0.0", 9999):
        await asyncio.Future()

# ==========================================


def clear_all_caches(model_name="qwen3-coder:30b"):
    print("\n" + "="*40)
    print("🧹 [🚨 메모리 및 캐시 대청소]")
    try:
        ollama.chat(model=model_name, messages=[], keep_alive=0)
    except: pass
    gc.collect()
    print("✅ 메모리 리셋 완료!")
    print("="*40 + "\n")

def generate_plan(model_name, input_json_str):
    SYSTEM_PROMPT = """
You are a universal Robotic Task Planner.
You receive a JSON with a high-level "sequence" of actions. This sequence could be from any domain (e.g., agriculture, logistics, domestic robots).
Your task is to translate this sequence into a single, raw JSON array of executable base robot skills.

CRITICAL INSTRUCTIONS:
1. Output MUST be a valid JSON array starting with '[' and ending with ']'. No markdown, no explanations.
2. Each object in the array MUST contain EXACTLY two keys: "step" (integer, starting from 1) and "skill" (string).
3. The "skill" value MUST be exactly one of these 3 base actions: "move", "pick", "put".

LOGICAL MAPPING GUIDE:
- "move": Navigating, scanning, approaching, walking, driving, or changing physical location.
- "pick": Grasping, cutting, harvesting, lifting, taking, or holding an object.
- "put": Releasing, dropping, placing, storing, or putting down an object.

EXAMPLE 1 (Agriculture):
Input sequence: ["approach_apple", "cut_stem", "go_to_basket", "drop_apple"]
Output: [{"step": 1, "skill": "move"}, {"step": 2, "skill": "pick"}, {"step": 3, "skill": "move"}, {"step": 4, "skill": "put"}]

EXAMPLE 2 (Logistics):
Input sequence: ["find_box", "grab_box", "place_on_conveyor"]
Output: [{"step": 1, "skill": "move"}, {"step": 2, "skill": "pick"}, {"step": 3, "skill": "put"}]
"""

    print(f"🧠 [{model_name}] LLM 추론 중... (작업 계획 수립)")
    
    start_time = time.perf_counter()
    try:
        response = ollama.chat(
            model=model_name,
            messages=[
                {'role': 'system', 'content': SYSTEM_PROMPT},
                {'role': 'user', 'content': input_json_str}
            ],
            options={"temperature": 0.0, "num_predict": 512}
        )
        elapsed_time = time.perf_counter() - start_time
        
        raw_output = response['message']['content'].strip()
        match = re.search(r'\[.*\]', raw_output, re.DOTALL)
        
        if match:
            parsed_json = json.loads(match.group(0))
            print(f"✅ 계획 수립 완료 ({elapsed_time:.2f}초)")
            return parsed_json
        else:
            raise ValueError(f"JSON 배열을 찾을 수 없습니다. 원본 출력: {raw_output}")

    except Exception as e:
        print(f"❌ 추론 에러: {e}")
        return None

def execute_robot_skill(skill_name, target_info, coordinate=None):
    if coordinate:
        print(f"\n  ▶️ [실행 중] 스킬: {skill_name.upper()} (Target: {target_info}) | 좌표: {coordinate}")
    else:
        print(f"\n  ▶️ [실행 중] 스킬: {skill_name.upper()} (Target: {target_info})")
        
    time.sleep(1) # 시각적 구분을 위한 짧은 딜레이
    
    if skill_name == "move":
        if coordinate:
            print(f"    -> 🚙 move_controller 모듈 가동! 로봇이 {coordinate}로 이동합니다.")
            # 💡 [핵심 연동] 여기서 ROS2 Nav2 모듈을 실제로 호출하고 대기합니다.
            success = move_controller.navigate_to(coordinate)
            if not success:
                print("       ⚠️ [경고] 로봇 이동에 실패했습니다. (장애물, 도달 불가 경로 등)")
        else:
            print("    -> ⚠️ [에러] 이동 스킬이 호출되었으나 매핑된 좌표가 없습니다!")
            
    elif skill_name == "pick":
        print("    -> ✂️ pick.pt 모델 인퍼런스 및 그리퍼(수확/파지) 작동 시작...")
        # model = torch.load('pick.pt')
        # result = model.predict(camera_frame)
        # gripper.close()
        
    elif skill_name == "put":
        print("    -> 🧺 put.pt 모델 인퍼런스 및 그리퍼(배치/해제) 해제 시작...")
        # model = torch.load('put.pt')
        # result = model.predict(camera_frame)
        # gripper.open()
        
    else:
        print(f"    -> ⚠️ 알 수 없는 스킬입니다: {skill_name}")

def run_task_pipeline(model_name, input_task_dict):
    print(f"\n{'='*50}\n🎯 [로봇 작업 파이프라인 시작]")
    
    input_str = json.dumps(input_task_dict, ensure_ascii=False, indent=2)
    print(f"📥 입력된 작업 지시서:\n{input_str}\n")
    
    plan = generate_plan(model_name, input_str)
    
    if not plan:
        print("❌ 파이프라인 중단: 계획 수립 실패")
        return

    print("\n📋 [도출된 실행 계획]")
    for step in plan:
        print(f"  - Step {step['step']}: {step['skill']}")
    
    raw_codes = input_task_dict.get("code", [])
    coordinates = [c.split(":")[-1] for c in raw_codes]
    
    print("\n⚙️ [물리적 로봇 제어 시작]")
    target = input_task_dict.get("target", "unknown")
    
    move_counter = 0 
    
    for action in plan:
        skill = action['skill']
        coord_to_pass = None
        
        if skill == "move":
            if move_counter < len(coordinates):
                coord_to_pass = coordinates[move_counter]
            move_counter += 1
            
        execute_robot_skill(skill, target, coordinate=coord_to_pass)
        
    print(f"\n{'='*50}\n🏁 모든 작업이 성공적으로 완료되었습니다!")


if __name__ == "__main__":
    model = 'qwen3-coder:30b'
    # test_model = 'qwen2.5-coder:1.5b' #GTX1650 저사양 테스트용 모델 (실제 운영에서는 qwen3-coder:30b 사용 권장 --- IGNORE ---
    
    incoming_task_json = {
        "environment": "농장",
        "task": "상자있는 곳으로 가서 집은 다음 container로 옮겨 놔줘",
        "target": "green vegetables",
        "code" : ['0:(-6,0,0)', '1:(0,11,3.14)'],
        "sequence": [
            "0:move_to_box",
            "1:cut_crop",
            "2:move_to_container",
            "3:release"
        ]
    }
    
    print("테스트 모드\n")
    clear_all_caches(model_name=model)
    run_task_pipeline(model, incoming_task_json)
    print("수신대기 모드로 전환\n")
    # 💡 [핵심 수정]: 1회성 테스트 실행을 지우고(또는 주석 처리), 웹소켓 서버를 무한 실행합니다.
    try:
        asyncio.run(main_server())
    except KeyboardInterrupt:
        print("\n🛑 [PC 2] 사용자에 의해 시스템이 종료되었습니다.")