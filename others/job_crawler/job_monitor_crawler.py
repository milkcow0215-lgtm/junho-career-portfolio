import os
import re
import json
import base64
import requests
import html
from google.auth.transport.requests import Request
# Google OAuth and Gmail API libraries
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# If modifying these scopes, delete the file token.json.
SCOPES = ['https://www.googleapis.com/auth/gmail.modify']

TOKEN_FILE = 'token.json'
CREDENTIALS_FILE = 'credentials.json'
SENT_JOBS_FILE = 'sent_jobs.json'
ENV_FILE = '.env'

def load_env(env_path=ENV_FILE):
    """Loads environment variables from a .env file."""
    if os.path.exists(env_path):
        with open(env_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    os.environ[key.strip()] = value.strip()
        print("Loaded environment variables from .env")
    else:
        print(".env file not found. Make sure environment variables are set.")

def get_gmail_service():
    """Authenticates with Gmail API and returns the service instance."""
    creds = None
    # The file token.json stores the user's access and refresh tokens, and is
    # created automatically when the authorization flow completes for the first time.
    if os.path.exists(TOKEN_FILE):
        creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)
    
    # If there are no (valid) credentials available, let the user log in.
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
            except Exception as e:
                print(f"Failed to refresh token: {e}. Re-authenticating...")
                creds = None
        
        if not creds:
            if not os.path.exists(CREDENTIALS_FILE):
                raise FileNotFoundError(
                    f"Required '{CREDENTIALS_FILE}' not found. "
                    "Please download OAuth client credentials JSON from Google Cloud Console."
                )
            flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_FILE, SCOPES)
            creds = flow.run_local_server(port=0)
            
        # Save the credentials for the next run
        with open(TOKEN_FILE, 'w') as token:
            token.write(creds.to_json())

    return build('gmail', 'v1', credentials=creds)

def load_sent_jobs():
    """Loads the cache of already sent job message IDs."""
    if os.path.exists(SENT_JOBS_FILE):
        try:
            with open(SENT_JOBS_FILE, 'r', encoding='utf-8') as f:
                return set(json.load(f))
        except Exception as e:
            print(f"Error loading sent jobs cache: {e}. Starting fresh.")
            return set()
    return set()

def save_sent_jobs(sent_jobs):
    """Saves the cache of sent job message IDs."""
    try:
        with open(SENT_JOBS_FILE, 'w', encoding='utf-8') as f:
            json.dump(list(sent_jobs), f, indent=4, ensure_ascii=False)
    except Exception as e:
        print(f"Failed to save sent jobs cache: {e}")

def get_email_body(payload):
    """Recursively parses email body parts to extract plain text or html."""
    if 'parts' in payload:
        for part in payload['parts']:
            body = get_email_body(part)
            if body:
                return body
    else:
        mime_type = payload.get('mimeType', '')
        if mime_type in ['text/plain', 'text/html']:
            data = payload.get('body', {}).get('data', '')
            if data:
                # Decode the URL-safe base64 data
                return base64.urlsafe_b64decode(data.encode('UTF-8')).decode('UTF-8', errors='ignore')
    return ""

def clean_html(raw_html):
    """Removes HTML tags and cleans up whitespaces."""
    clean_re = re.compile('<.*?>')
    text = re.sub(clean_re, '', raw_html)
    # Unescape HTML entities
    text = html.unescape(text)
    # Normalize multiple newlines and spaces
    text = re.sub(r'\n\s*\n', '\n', text)
    return text.strip()

def send_telegram_alert(token, chat_id, subject, snippet, msg_id):
    """Sends a formatted job alert to Telegram channel."""
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    
    # Format message with HTML tags
    message = f"<b>🔍 [실시간 채용 공고 감지]</b>\n\n"
    message += f"<b>제목</b>: {html.escape(subject)}\n"
    message += f"<b>내용 요약</b>:\n<i>{html.escape(snippet[:300])}...</i>\n\n"
    message += f"<b>Message-ID</b>:\n<code>{html.escape(msg_id)}</code>\n\n"
    message += f"<i>* Google Gmail API OAuth2 & Telegram 연동 자동화 시스템</i>"

    payload = {
        "chat_id": chat_id,
        "text": message,
        "parse_mode": "HTML"
    }
    
    try:
        response = requests.post(url, json=payload, timeout=10)
        if response.status_code == 200:
            print(f"Successfully sent Telegram alert for: {subject}")
            return True
        else:
            print(f"Failed to send Telegram alert: {response.text}")
            return False
    except Exception as e:
        print(f"Connection error to Telegram: {e}")
        return False

def main():
    # Load env configurations
    load_env()
    telegram_token = os.getenv("TELEGRAM_BOT_TOKEN")
    # Supports both CHAT_ID and TELEGRAM_CHAT_ID
    chat_id = os.getenv("TELEGRAM_CHAT_ID") or os.getenv("CHAT_ID")

    if not telegram_token or not chat_id:
        print("Error: TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID must be set in .env file.")
        return

    # Initialize Gmail API service
    try:
        service = get_gmail_service()
    except Exception as e:
        print(f"Gmail Authentication failed: {e}")
        return

    # Load cache of sent message IDs
    sent_jobs = load_sent_jobs()

    # Search for unread job-related emails
    # Query: unread emails containing recruitment, hiring, job alert, or wanted in the subject
    query = 'is:unread (subject:"채용" OR subject:"공고" OR subject:"job alert" OR subject:"wanted")'
    print(f"Searching Gmail with query: '{query}'")

    try:
        results = service.users().messages().list(userId='me', q=query).execute()
        messages = results.get('messages', [])

        if not messages:
            print("No new unread recruitment emails found.")
            return

        print(f"Found {len(messages)} potential unread email(s). Processing...")

        new_alerts_sent = False

        for msg in messages:
            msg_id = msg['id']
            
            # Fetch detailed message metadata and body
            message_details = service.users().messages().get(userId='me', id=msg_id).execute()
            
            # Extract headers
            headers = message_details.get('payload', {}).get('headers', [])
            subject = "No Subject"
            internet_message_id = msg_id  # fallback message ID
            
            for header in headers:
                name = header.get('name', '')
                if name.lower() == 'subject':
                    subject = header.get('value', 'No Subject')
                elif name.lower() == 'message-id':
                    internet_message_id = header.get('value', msg_id)

            # Skip if already processed based on unique Message-ID header
            if internet_message_id in sent_jobs:
                print(f"Skipping duplicate message: '{subject}' (ID: {internet_message_id})")
                continue

            # Extract and clean content body
            raw_body = get_email_body(message_details.get('payload', {}))
            body_text = clean_html(raw_body) if raw_body else message_details.get('snippet', '')
            
            if not body_text:
                body_text = "No content body available."

            # Send Alert to Telegram
            success = send_telegram_alert(telegram_token, chat_id, subject, body_text, internet_message_id)
            
            if success:
                # Add to cache to prevent duplicates
                sent_jobs.add(internet_message_id)
                new_alerts_sent = True
                
                # Optional: Mark the message as read to clean up inbox
                try:
                    service.users().messages().batchModify(
                        userId='me',
                        body={
                            'ids': [msg_id],
                            'removeLabelIds': ['UNREAD']
                        }
                    ).execute()
                    print(f"Marked email '{subject}' as read.")
                except Exception as ex:
                    print(f"Failed to mark email as read: {ex}")

        # Save Cache if updated
        if new_alerts_sent:
            save_sent_jobs(sent_jobs)

    except HttpError as error:
        print(f"An API error occurred: {error}")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")

if __name__ == '__main__':
    main()
