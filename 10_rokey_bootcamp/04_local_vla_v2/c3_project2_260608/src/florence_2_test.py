import os
import torch
from PIL import Image
from transformers import AutoProcessor, AutoModelForCausalLM

import json
import asyncio
import websockets

# ==========================================
# 🌐 네트워크 설정
# ==========================================
# 💡 [핵심] PC 1 (대뇌)의 실제 IP 주소와 포트(8888)로 변경하세요.
# 만약 PC 1과 같은 컴퓨터에서 실행한다면 "ws://127.0.0.1:8888"로 설정하세요.
PC1_WS_URL = "ws://127.0.0.1:8887"


# ==========================================
# 1. Florence-2 모델 로드
# ==========================================
print("▶ Florence-2 모델 로드 중...")
MODEL_ID = "microsoft/Florence-2-base"

processor = AutoProcessor.from_pretrained(MODEL_ID, trust_remote_code=True)
model = AutoModelForCausalLM.from_pretrained(
    MODEL_ID,
    trust_remote_code=True,
    attn_implementation="eager",
    # torch_dtype=torch.float16, #gtx1650 저사양용
    torch_dtype=torch.float32, #rtx5080 고사양용
)

device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
model.to(device)
model.eval()
print(f"➔ 연산 디바이스: {device}\n")

# ==========================================
# 2. 이미지 목록 수집 (old/ 제외)
# ==========================================
IMAGE_DIR = "/home/rokey/yolo-world/test_image"
# IMAGE_DIR = "yolo-world/test_image"
SUPPORTED_EXTS = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}

image_files = sorted([
    os.path.join(IMAGE_DIR, f)
    for f in os.listdir(IMAGE_DIR)
    if os.path.isfile(os.path.join(IMAGE_DIR, f))
    and os.path.splitext(f)[1].lower() in SUPPORTED_EXTS
])

if not image_files:
    print(f"❌ '{IMAGE_DIR}' 에 이미지 파일이 없습니다.")
    exit()

print(f"➔ 처리할 이미지 {len(image_files)}개\n")


# ==========================================
# GTX2080용  3. Florence-2 추론 함수
# ==========================================
def run_florence2(image: Image.Image, task: str) -> str:
    image = image.resize((768, 768))
    inputs = processor(text=task, images=image, return_tensors="pt").to(device)
    with torch.no_grad():
        generated_ids = model.generate(
            input_ids=inputs["input_ids"],
            pixel_values=inputs["pixel_values"],
            max_new_tokens=256,
            num_beams=3,
            use_cache=False,
        )
    result = processor.batch_decode(generated_ids, skip_special_tokens=False)[0]
    parsed = processor.post_process_generation(result, task=task, image_size=image.size)
    return parsed

# # ==========================================
# # GTX1650용  3. Florence-2 추론 함수
# # ==========================================
# def run_florence2(image: Image.Image, task: str) -> str:
#     image = image.resize((768, 768))
#     inputs = processor(text=task, images=image, return_tensors="pt").to(device)
    
#     # 💡 [핵심 추가 코드] 모델과 동일하게 이미지 텐서를 float16으로 강제 변환합니다.
#     inputs["pixel_values"] = inputs["pixel_values"].to(torch.float16)

#     with torch.no_grad():
#         generated_ids = model.generate(
#             input_ids=inputs["input_ids"],
#             pixel_values=inputs["pixel_values"],
#             max_new_tokens=256,
#             num_beams=3,
#             use_cache=False,
#         )
#     result = processor.batch_decode(generated_ids, skip_special_tokens=False)[0]
#     parsed = processor.post_process_generation(result, task=task, image_size=image.size)
#     return parsed



# ==========================================
# 4. 실시간 웹소켓 송신 파이프라인
# ==========================================
async def stream_vision_data():
    try:
        # PC 1과 웹소켓 연결 시도
        async with websockets.connect(PC1_WS_URL, ping_interval=None) as websocket:
            print(f"📡 [PC 3] PC 1 (대뇌 관제 센터) 서버와 연결 성공: {PC1_WS_URL}\n")
            print(f"{'='*50}")

            for idx, image_path in enumerate(image_files, start=1):
                filename = os.path.basename(image_path)
                print(f"[{idx}/{len(image_files)}] 👁️ 이미지 분석 중: {filename}")

                try:
                    image = Image.open(image_path).convert("RGB")
                except Exception as e:
                    print(f"  ❌ 이미지 로드 실패: {e}\n")
                    continue

                # 1. Object Detection (물체 탐지)
                od_result = run_florence2(image, "<OD>")
                labels = od_result.get("<OD>", {}).get("labels", [])
                
                if labels:
                    unique_labels = sorted(set(labels))
                    print(f"  🔍 탐지된 물체 ({len(labels)}개):")
                    for label in unique_labels:
                        count = labels.count(label)
                        print(f"      - {label} x{count}")
                else:
                    print("  ⚠️  탐지된 물체 없음")

                
                # 2. Dense Caption (상황 요약)
                caption_result = run_florence2(image, "<MORE_DETAILED_CAPTION>")
                caption_text = caption_result.get("<MORE_DETAILED_CAPTION>", "")
                if caption_text:
                    print(f"  📝 이미지 설명: {caption_text}") 
                

                # 3. 데이터 패키징 (PC 1이 파싱하기 좋은 구조)
                payload = {
                    "objects": od_result.get("<OD>", {}),
                    "caption": caption_result.get("<MORE_DETAILED_CAPTION>", "")
                }
                

                # 4. PC 1로 JSON 데이터 쏘기
                await websocket.send(json.dumps(payload, ensure_ascii=False))
                print(f"  📤 [전송 완료] PC 1으로 시각 데이터 송신 성공")
                print(f"{'='*50}")

                # Isaac Sim의 실시간 스트리밍 환경을 모사하기 위해 프레임 간 딜레이 부여
                ack = await websocket.recv()
                await asyncio.sleep(10) 

            print("🏁 [PC 3] 준비된 모든 비전 데이터 스트리밍 완료")
            await asyncio.sleep(10) # 10초간 연결을 유지하며 전송 확인
            
            
    except websockets.exceptions.ConnectionRefusedError:
        print(f"🚨 [에러] 연결 거부됨. PC 1({PC1_WS_URL})의 백그라운드 서버(포트 8888)가 켜져 있는지 확인하세요.")
    except Exception as e:
        print(f"🚨 [에러] 통신 중 문제 발생: {e}")

if __name__ == "__main__":
    asyncio.run(stream_vision_data())
