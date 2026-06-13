import os
import requests

env_path = r"C:\Anti_workspace\01_quant_trading\.env"
token = None
chat_id = None

if os.path.exists(env_path):
    with open(env_path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                key, value = line.split('=', 1)
                if key.strip() == "TELEGRAM_BOT_TOKEN":
                    token = value.strip()
                elif key.strip() == "TELEGRAM_CHAT_ID":
                    chat_id = value.strip()

print(f"Token: {token[:10]}... Chat ID: {chat_id}")

message = "C:\\Anti_workspace 기지 리빌딩 완료 및 텔레그램 스케줄러 정상 가동 테스트 성공"
chart_file = r"C:\Anti_workspace\01_quant_trading\plots\daily_chart.png"

# 1. Send Text
send_msg_url = f"https://api.telegram.org/bot{token}/sendMessage"
payload = {
    "chat_id": chat_id,
    "text": message
}
resp1 = requests.post(send_msg_url, json=payload)
print(f"Text Response: {resp1.status_code}, {resp1.text}")

# 2. Send Chart
if os.path.exists(chart_file):
    send_photo_url = f"https://api.telegram.org/bot{token}/sendPhoto"
    with open(chart_file, 'rb') as photo:
        files = {'photo': photo}
        data_payload = {'chat_id': chat_id}
        resp2 = requests.post(send_photo_url, files=files, data=data_payload)
        print(f"Photo Response: {resp2.status_code}, {resp2.text}")
else:
    print("Chart file not found!")
