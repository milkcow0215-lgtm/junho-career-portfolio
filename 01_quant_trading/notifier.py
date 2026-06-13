import os
import json
import requests
import html

def load_env(env_path='.env'):
    """Loads environment variables from a .env file without external dependencies."""
    if os.path.exists(env_path):
        with open(env_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    os.environ[key.strip()] = value.strip()
        print("Loaded environment variables from .env")
    else:
        print(".env file not found. Please create it.")

def send_telegram_notification():
    load_env()
    
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")
    
    if not token or token == "YOUR_BOT_TOKEN_HERE" or not chat_id or chat_id == "YOUR_CHAT_ID_HERE":
        print("Error: Please configure valid TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID in C:\\quant\\.env file.")
        return False
        
    order_file = os.path.join('data', 'today_order.json')
    chart_file = os.path.join('plots', 'daily_chart.png')
    
    if not os.path.exists(order_file):
        print(f"Error: {order_file} not found. Run trade_signal.py first.")
        return False

    # 1. Parse order signal JSON
    with open(order_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
        
    eval_date = data.get("evaluation_date", "Unknown")
    macro_risk = "🚨 RISK ON (위험)" if data.get("macro_risk_triggered", False) else "✅ RISK OFF (안정)"
    
    # 2. Format Telegram message
    message = f"<b>📈 퀀트 자동화 일일 주문서 ({eval_date})</b>\n"
    message += f"거시 위험 지표: <b>{macro_risk}</b>\n\n"
    message += "<b>[추천 주문 목록]</b>\n"
    
    for order in data.get("orders", []):
        ticker = order.get("ticker", "UNKNOWN")
        action = order.get("action", "HOLD")
        reason = html.escape(order.get("reason", "No reason provided."))
        
        action_emoji = "🟢 BUY" if action == "BUY" else ("🔴 SELL" if action == "SELL" else "⚪ HOLD")
        message += f"• <b>{ticker}</b>: {action_emoji}\n  └ <i>{reason}</i>\n"
        
    message += "\n<i>* 매일 아침 자동 분석 결과입니다.</i>"

    # 3. Send Text Message
    send_msg_url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": message,
        "parse_mode": "HTML"
    }
    
    try:
        response = requests.post(send_msg_url, json=payload)
        if response.status_code == 200:
            print("Telegram text notification sent successfully!")
        else:
            print(f"Failed to send Telegram message: {response.text}")
            return False
    except Exception as e:
        print(f"Error sending Telegram message: {e}")
        return False

    # 4. Send Chart Image
    if os.path.exists(chart_file):
        send_photo_url = f"https://api.telegram.org/bot{token}/sendPhoto"
        try:
            with open(chart_file, 'rb') as photo:
                files = {'photo': photo}
                data_payload = {'chat_id': chat_id}
                photo_resp = requests.post(send_photo_url, files=files, data=data_payload)
                if photo_resp.status_code == 200:
                    print("Telegram chart image sent successfully!")
                else:
                    print(f"Failed to send Telegram photo: {photo_resp.text}")
        except Exception as e:
            print(f"Error sending Telegram photo: {e}")
    else:
        print("Chart image not found. Skipping photo attachment.")
        
    return True

if __name__ == '__main__':
    send_telegram_notification()
