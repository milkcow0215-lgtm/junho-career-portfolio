import os
import re
import json
import time
from datetime import datetime, date
import urllib.parse
import html
import requests
from bs4 import BeautifulSoup

# Files & Configurations
ENV_FILE = '.env'
SENT_JOBS_FILE = 'sent_jobs.json'

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

def load_sent_jobs():
    """Loads the cache of already sent job posting keys."""
    if os.path.exists(SENT_JOBS_FILE):
        try:
            with open(SENT_JOBS_FILE, 'r', encoding='utf-8') as f:
                return set(json.load(f))
        except Exception as e:
            print(f"Error loading sent jobs cache: {e}. Starting fresh.")
            return set()
    return set()

def save_sent_jobs(sent_jobs):
    """Saves the cache of sent job keys, keeping maximum 1000 entries to prevent file bloat."""
    try:
        list_jobs = list(sent_jobs)[-1000:]
        with open(SENT_JOBS_FILE, 'w', encoding='utf-8') as f:
            json.dump(list_jobs, f, indent=4, ensure_ascii=False)
        print("Sent jobs cache saved successfully.")
    except Exception as e:
        print(f"Failed to save sent jobs cache: {e}")

def parse_dday(deadline_text):
    """Parses human-readable deadline text and calculates D-day.
    Examples: '~ 07/11(목)', '오늘마감', '내일마감', '상시채용', '채용시'
    """
    if not deadline_text:
        return "상시", ""
        
    deadline_text = deadline_text.strip()
    
    if "오늘" in deadline_text:
        return "D-0", "오늘마감"
    if "내일" in deadline_text:
        return "D-1", "내일마감"
    if "상시" in deadline_text or "채용시" in deadline_text:
        return "상시", deadline_text

    # Extract date pattern like 07/11 or 2026-07-11
    date_match = re.search(r'(\d{4})[-/.](\d{1,2})[-/.](\d{1,2})', deadline_text)
    if not date_match:
        date_match = re.search(r'(\d{1,2})/(\d{1,2})', deadline_text)
        
    if date_match:
        today = date.today()
        try:
            if len(date_match.groups()) == 3:
                year = int(date_match.group(1))
                month = int(date_match.group(2))
                day = int(date_match.group(3))
                target_date = date(year, month, day)
            else:
                month = int(date_match.group(1))
                day = int(date_match.group(2))
                target_date = date(today.year, month, day)
                if target_date < today:
                    target_date = date(today.year + 1, month, day)
                    
            delta = (target_date - today).days
            return f"D-{delta}", target_date.strftime('%Y-%m-%d')
        except ValueError:
            pass
            
    return "대기", deadline_text

def send_telegram_report(token, chat_id, jobs):
    """Sends the formatted daily job report to the Telegram channel."""
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    today_str = datetime.today().strftime('%Y-%m-%d')
    
    # 1. Start message headers
    message = f"<b>🤖 통합 로봇 필드 엔지니어 채용 보고서 ({today_str})</b>\n"
    message += f"수집 조건: <i>3대 사이트(사람인, 잡코리아, 원티드) | 중견/대기업 | 연봉 3,200만 원 이상(협의 포함)</i>\n\n"
    
    if not jobs:
        message += "오늘 아침 조건에 맞는 추천 채용 공고가 없습니다.\n\n"
        message += "<i>* 매일 아침 자동 모니터링 시스템 작동 중</i>"
        payload = {"chat_id": chat_id, "text": message, "parse_mode": "HTML"}
        requests.post(url, json=payload, timeout=10)
        print("Sent 'no jobs' check-in message to Telegram.")
        return True

    # 2. Add job listings
    message += f"오늘 수집된 공고는 총 <b>{len(jobs)}건</b>입니다.\n\n"
    
    for idx, job in enumerate(jobs):
        dup_badge = " [🔄 어제 올라온 공고와 동일 (중복)]" if job.get('is_prev_duplicate') else " [🆕 신규 공고]"
        source_display = f"{job['source']} [타 사이트 중복 노출]" if job.get('is_portal_duplicate') else job['source']
        
        card = f"<b>{idx+1}. {html.escape(job['corp'])}</b> | 🏢 {html.escape(job['scale'])}{dup_badge}\n"
        card += f"• <b>공고명:</b> {html.escape(job['title'])}\n"
        card += f"• <b>급여/조건:</b> {html.escape(job['salary'])}\n"
        card += f"• <b>마감일:</b> {html.escape(job['deadline'])} (<b>{html.escape(job['dday'])}</b>)\n"
        card += f"• <b>출처:</b> {html.escape(source_display)}\n"
        card += f"🔗 <a href='{html.escape(job['link'])}'>공고 상세보기</a>\n\n"
        
        if len(message) + len(card) > 3900:
            payload = {"chat_id": chat_id, "text": message, "parse_mode": "HTML", "disable_web_page_preview": True}
            requests.post(url, json=payload, timeout=15)
            message = ""
            
        message += card
        
    message += "<i>* 평일 아침 자동 스케줄링 통합 수집 결과입니다.</i>"
    
    payload = {
        "chat_id": chat_id,
        "text": message,
        "parse_mode": "HTML",
        "disable_web_page_preview": True
    }
    
    try:
        response = requests.post(url, json=payload, timeout=15)
        if response.status_code == 200:
            print("Telegram job report sent successfully!")
            return True
        else:
            print(f"Failed to send Telegram report: {response.text}")
            return False
    except Exception as e:
        print(f"Connection error to Telegram: {e}")
        return False

def scrape_saramin():
    """Scrapes job postings from Saramin."""
    base_url = "https://www.saramin.co.kr"
    search_query = urllib.parse.quote("필드엔지니어")
    search_url = (
        f"{base_url}/zf_user/search/recruit"
        f"?search_done=y"
        f"&search_optional_item=n"
        f"&company_cd=1%2C2"
        f"&salary_higher=3200"
        f"&salary_none=y"
        f"&sort=rd"
        f"&searchword={search_query}"
    )
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    }
    
    print(f"Connecting to Saramin Search URL: {search_url}")
    try:
        response = requests.get(search_url, headers=headers, timeout=15)
        if response.status_code != 200:
            print(f"Failed to retrieve Saramin. Status: {response.status_code}")
            return []
            
        soup = BeautifulSoup(response.text, 'html.parser')
        job_elements = soup.select('.item_recruit')
        parsed_jobs = []
        
        for item in job_elements:
            rec_idx = item.get('rec_idx', '')
            if not rec_idx:
                link_tag = item.select_one('.job_tit a')
                if link_tag:
                    href = link_tag.get('href', '')
                    match = re.search(r'rec_idx=(\d+)', href)
                    if match:
                        rec_idx = match.group(1)
            
            if not rec_idx:
                continue
                
            corp_tag = item.select_one('.corp_name a')
            if not corp_tag:
                continue
            corp_name = corp_tag.text.strip()
            
            scale = "중견/대기업"
            badge_tags = item.select('.area_badge .badge, .corp_name .badge')
            for badge in badge_tags:
                badge_text = badge.text.strip()
                if "대기업" in badge_text:
                    scale = "대기업"
                    break
                elif "중견기업" in badge_text:
                    scale = "중견기업"
                    break

            title_tag = item.select_one('.job_tit a')
            if not title_tag:
                continue
            title = title_tag.text.strip()
            
            raw_href = title_tag.get('href', '')
            link = base_url + raw_href if raw_href.startswith('/') else raw_href

            conditions = item.select('.job_condition span')
            cond_texts = [c.text.strip() for c in conditions]
            
            salary = "회사내규/협의 (대기업/중견기업)"
            skip_low_salary = False
            for cond in cond_texts:
                if '만원' in cond or '연봉' in cond:
                    match_sal = re.search(r'(\d{4})', cond)
                    if match_sal:
                        val = int(match_sal.group(1))
                        if val < 3200:
                            skip_low_salary = True
                            break
                    salary = cond
                    break
            
            if skip_low_salary:
                continue

            date_tag = item.select_one('.job_date .date')
            raw_deadline = date_tag.text.strip() if date_tag else "상시채용"
            dday, clean_deadline = parse_dday(raw_deadline)
            
            parsed_jobs.append({
                "id": f"sr_{rec_idx}",
                "corp": corp_name,
                "scale": scale,
                "title": title,
                "link": link,
                "salary": salary,
                "deadline": clean_deadline if clean_deadline else raw_deadline,
                "dday": dday,
                "source": "사람인"
            })
            
        return parsed_jobs
    except Exception as e:
        print(f"Error occurred during Saramin scraping: {e}")
        return []

def scrape_jobkorea():
    """Scrapes job postings from JobKorea."""
    base_url = "https://www.jobkorea.co.kr"
    search_query = urllib.parse.quote("필드엔지니어")
    search_url = f"{base_url}/Search/?stext={search_query}&coType=1,2&salary=3200&OrdTyp=1"
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    }
    
    print(f"Connecting to JobKorea Search URL: {search_url}")
    try:
        response = requests.get(search_url, headers=headers, timeout=15)
        if response.status_code != 200:
            print(f"Failed to retrieve JobKorea. Status: {response.status_code}")
            return []
            
        soup = BeautifulSoup(response.text, 'html.parser')
        cards = soup.select('div[data-sentry-component="CardJob"]')
        
        parsed_jobs = []
        seen_ids = set()
        
        for card in cards:
            links = card.find_all('a')
            valid_links = [l for l in links if l.text.strip()]
            
            if len(valid_links) < 2:
                continue
                
            title = valid_links[0].text.strip()
            corp_name = valid_links[1].text.strip()
            href = valid_links[0].get('href', '')
            
            match = re.search(r'/GI_Read/(\d+)', href)
            if not match:
                continue
            jk_id = match.group(1)
            
            if jk_id in seen_ids:
                continue
            seen_ids.add(jk_id)
            
            full_link = base_url + href if href.startswith('/') else href
            
            scale = "중견/대기업"
            if "대기업" in card.text:
                scale = "대기업"
            elif "중견기업" in card.text:
                scale = "중견기업"
                
            salary = "회사내규/협의 (대기업/중견기업)"
            salary_match = re.search(r'(연봉\s*[\d,~\s]+[만원|억]+)|(내규|협의)', card.text)
            if salary_match:
                salary = salary_match.group(0)
                
            deadline = "상시채용"
            deadline_match = re.search(r'~(\d{1,2}/\d{1,2}(?:\([가-힣]\))?)', card.text)
            if deadline_match:
                deadline = deadline_match.group(0)
            elif "오늘마감" in card.text:
                deadline = "오늘마감"
            elif "내일마감" in card.text:
                deadline = "내일마감"
                
            dday, clean_deadline = parse_dday(deadline)
            
            parsed_jobs.append({
                "id": f"jk_{jk_id}",
                "corp": corp_name,
                "scale": scale,
                "title": title,
                "link": full_link,
                "salary": salary,
                "deadline": clean_deadline if clean_deadline else deadline,
                "dday": dday,
                "source": "잡코리아"
            })
            
        return parsed_jobs
    except Exception as e:
        print(f"Error occurred during JobKorea scraping: {e}")
        return []

def scrape_wanted():
    """Scrapes job postings from Wanted API."""
    search_query = urllib.parse.quote("필드엔지니어")
    url = f"https://www.wanted.co.kr/api/v4/jobs?country=kr&locations=all&years=-1&query={search_query}&limit=20&sort=created"
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'application/json, text/plain, */*',
        'Referer': f'https://www.wanted.co.kr/search?query={search_query}'
    }
    
    print(f"Connecting to Wanted API: {url}")
    try:
        response = requests.get(url, headers=headers, timeout=15)
        if response.status_code != 200:
            print(f"Failed to retrieve Wanted API. Status: {response.status_code}")
            return []
            
        data = response.json()
        job_list = data.get('data', [])
        
        parsed_jobs = []
        for job in job_list:
            job_id = job.get('id')
            if not job_id:
                continue
                
            title = job.get('position', 'N/A')
            corp_name = job.get('company', {}).get('name', 'N/A')
            link = f"https://www.wanted.co.kr/wd/{job_id}"
            
            scale = "중견/대기업"
            salary = "회사내규/협의 (원티드 채용)"
            
            raw_due = job.get('due_time')
            if raw_due:
                dday, clean_deadline = parse_dday(raw_due)
            else:
                dday, clean_deadline = "상시", "상시채용"
                
            parsed_jobs.append({
                "id": f"wd_{job_id}",
                "corp": corp_name,
                "scale": scale,
                "title": title,
                "link": link,
                "salary": salary,
                "deadline": clean_deadline,
                "dday": dday,
                "source": "원티드"
            })
            
        return parsed_jobs
    except Exception as e:
        print(f"Error occurred during Wanted API scraping: {e}")
        return []

def main():
    # Load settings
    load_env()
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")
    
    if not token or not chat_id:
        print("Error: TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID must be set in .env.")
        return
        
    sent_jobs = load_sent_jobs()
    
    # 1. Scrape all 3 sites
    saramin_jobs = scrape_saramin()
    time.sleep(2)
    
    jobkorea_jobs = scrape_jobkorea()
    time.sleep(2)
    
    wanted_jobs = scrape_wanted()
    
    all_jobs = saramin_jobs + jobkorea_jobs + wanted_jobs
    print(f"Total crawled postings: {len(all_jobs)} (Saramin: {len(saramin_jobs)}, JobKorea: {len(jobkorea_jobs)}, Wanted: {len(wanted_jobs)})")
    
    # 2. Today's Cross-Site Deduplication
    merged_jobs = {}
    
    for job in all_jobs:
        norm_corp = re.sub(r'[^a-zA-Z0-9가-힣]', '', job['corp']).strip()
        norm_title = re.sub(r'[^a-zA-Z0-9가-힣]', '', job['title']).strip()
        key = f"{norm_corp}_{norm_title[:15]}"
        
        if key not in merged_jobs:
            job['is_portal_duplicate'] = False
            merged_jobs[key] = job
        else:
            existing = merged_jobs[key]
            if job['source'] not in existing['source']:
                existing['source'] = f"{existing['source']}, {job['source']}"
                existing['is_portal_duplicate'] = True
                
    final_list = list(merged_jobs.values())
    print(f"Total jobs after cross-portal deduplication: {len(final_list)}")
    
    # 3. Check for previous day duplicates against sent_jobs.json
    new_jobs_keys = set()
    for job in final_list:
        norm_corp = re.sub(r'[^a-zA-Z0-9가-힣]', '', job['corp']).strip()
        norm_title = re.sub(r'[^a-zA-Z0-9가-힣]', '', job['title']).strip()
        cache_key = f"{norm_corp}_{norm_title[:15]}"
        
        if cache_key in sent_jobs:
            job['is_prev_duplicate'] = True
        else:
            job['is_prev_duplicate'] = False
            new_jobs_keys.add(cache_key)
            
    # 4. Send the integrated report
    success = send_telegram_report(token, chat_id, final_list)
    
    if success:
        if new_jobs_keys:
            sent_jobs.update(new_jobs_keys)
            save_sent_jobs(sent_jobs)

if __name__ == '__main__':
    main()
