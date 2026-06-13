import os.path
import sys
import io
import unicodedata
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# 구글 드라이브 API 접근 권한 설정 (전체 드라이브 읽기/쓰기 권한)
SCOPES = ['https://www.googleapis.com/auth/drive']

# ==============================================================================
# [설정 정보]
# 1. SHARED_FOLDER_ID: 공유받은 자료 폴더의 ID (주소창의 folders/ 뒤에 있는 문자열)
# 2. DEST_PATH: 내 드라이브에서 복사본을 저장할 목적지 폴더 경로.
#    - 예: '02_로키 폴더/01_로키 수업자료/08_협동3'
#    - 빈 값('')으로 두면 DEST_FOLDER_ID 설정을 따릅니다.
# 3. DEST_FOLDER_ID: DEST_PATH가 비어있을 때 사용되는 폴더 ID. ('root'는 내 드라이브 최상위)
# ==============================================================================
SHARED_FOLDER_ID = '1UFnMnjzQyUuaFtoOIrOPF-mBqW1hzCBb'
DEST_PATH = '02_로키 폴더/01_로키 수업자료/08_협동3'
DEST_FOLDER_ID = 'root'
# ==============================================================================

def get_gdrive_service():
    """구글 드라이브 API 인증을 처리하고 서비스 객체를 반환합니다."""
    creds = None
    # 이전에 로그인한 정보가 있으면 token.json 파일에서 로드합니다.
    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)
    
    # 저장된 자격증명이 없거나 만료된 경우 새롭게 인증을 시도합니다.
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
            except Exception:
                creds = None
        
        if not creds:
            if not os.path.exists('credentials.json'):
                print("오류: 'credentials.json' 파일이 현재 디렉토리에 존재하지 않습니다.")
                print("구글 클라우드 콘솔에서 OAuth 클라이언트 ID(데스크톱 앱)의 JSON 키를 다운로드하여")
                print("이 스크립트와 동일한 폴더에 'credentials.json' 이름으로 저장해 주세요.")
                sys.exit(1)
                
            flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)
            
        # 다음 실행을 위해 인증 정보를 token.json에 저장합니다.
        with open('token.json', 'w') as token:
            token.write(creds.to_json())
            
    return build('drive', 'v3', credentials=creds)

def find_folder_by_path(service, path_str):
    """'folder1/folder2/folder3' 형태의 경로를 해석하여 최하위 폴더의 ID를 반환합니다."""
    parts = [p.strip() for p in path_str.split('/') if p.strip()]
    current_parent_id = 'root'
    
    for part in parts:
        part_normalized = unicodedata.normalize('NFC', part)
        query = f"'{current_parent_id}' in parents and mimeType='application/vnd.google-apps.folder' and trashed=false"
        
        try:
            response = service.files().list(
                q=query,
                spaces='drive',
                fields='files(id, name)'
            ).execute()
            
            files = response.get('files', [])
            found_id = None
            for f in files:
                f_norm = unicodedata.normalize('NFC', f['name'])
                if f_norm == part_normalized:
                    found_id = f['id']
                    break
                    
            if not found_id:
                print(f"오류: 경로 중 '{part}' 폴더를 찾을 수 없습니다.")
                return None
                
            current_parent_id = found_id
        except HttpError as error:
            print(f"경로 탐색 중 오류 발생 (부모 ID: {current_parent_id}): {error}")
            return None
            
    return current_parent_id

def get_subfolders(service, parent_id):
    """지정한 부모 폴더 ID 아래에 있는 폴더 목록을 조회합니다."""
    folders = []
    page_token = None
    
    query = f"'{parent_id}' in parents and mimeType='application/vnd.google-apps.folder' and trashed=false"
    
    try:
        while True:
            response = service.files().list(
                q=query,
                spaces='drive',
                fields='nextPageToken, files(id, name)',
                pageToken=page_token
            ).execute()
            
            raw_files = response.get('files', [])
            for f in raw_files:
                # 한글 자모 자분리(NFD) 문제를 완성형(NFC)으로 표준화
                normalized_name = unicodedata.normalize('NFC', f['name'])
                folders.append({
                    'id': f['id'],
                    'name': normalized_name
                })
                
            page_token = response.get('nextPageToken', None)
            if not page_token:
                break
    except HttpError as error:
        print(f"폴더 목록 조회 중 오류 발생: {error}")
        
    return folders

def copy_file(service, file_id, file_name, dest_folder_id):
    """파일 하나를 목적지 폴더로 복사합니다."""
    # 한글 자모 정규화
    normalized_name = unicodedata.normalize('NFC', file_name)
    try:
        copied_file = service.files().copy(
            fileId=file_id,
            body={
                'name': normalized_name,
                'parents': [dest_folder_id]
            }
        ).execute()
        print(f"  └ 파일 복사 성공: {normalized_name} (새 ID: {copied_file.get('id')})")
        return copied_file.get('id')
    except HttpError as error:
        print(f"  └ 파일 복사 실패: {normalized_name}. 에러: {error}")
        return None

def copy_folder_contents_recursive(service, src_folder_id, dest_folder_id):
    """소스 폴더 안의 모든 파일과 하위 폴더들을 목적지 폴더로 재귀 복사합니다."""
    query = f"'{src_folder_id}' in parents and trashed=false"
    page_token = None
    
    try:
        while True:
            response = service.files().list(
                q=query,
                spaces='drive',
                fields='nextPageToken, files(id, name, mimeType)',
                pageToken=page_token
            ).execute()
            
            items = response.get('files', [])
            for item in items:
                # 한글 자모 정규화
                name = unicodedata.normalize('NFC', item['name'])
                item_id = item['id']
                mime_type = item['mimeType']
                
                if mime_type == 'application/vnd.google-apps.folder':
                    # 하위 폴더인 경우: 목적지에 폴더를 생성하고 재귀적으로 내부 콘텐츠를 복사합니다.
                    print(f"  [폴더 생성 중] {name}...")
                    new_subfolder = service.files().create(
                        body={
                            'name': name,
                            'mimeType': 'application/vnd.google-apps.folder',
                            'parents': [dest_folder_id]
                        },
                        fields='id'
                    ).execute()
                    new_subfolder_id = new_subfolder.get('id')
                    copy_folder_contents_recursive(service, item_id, new_subfolder_id)
                else:
                    # 파일인 경우 복사 수행
                    copy_file(service, item_id, name, dest_folder_id)
                    
            page_token = response.get('nextPageToken', None)
            if not page_token:
                break
    except HttpError as error:
        print(f"폴더 내부 복사 중 오류 발생 (폴더 ID {src_folder_id}): {error}")

def main():
    # Windows 한글 환경에서의 이모지 및 한글 터미널 출력(print) 시 CP949 인코딩 오류 예방
    if sys.platform.startswith('win'):
        sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding='utf-8')
        sys.stderr = io.TextIOWrapper(sys.stderr.detach(), encoding='utf-8')
        
    print("구글 드라이브 단발성 파일 복사 스크립트를 기동합니다.")
    service = get_gdrive_service()
    
    # 0. 목적지 경로 자동 탐색
    global DEST_FOLDER_ID
    if DEST_PATH:
        print(f"목적지 경로 '{DEST_PATH}' 의 폴더 ID를 탐색합니다...")
        found_id = find_folder_by_path(service, DEST_PATH)
        if not found_id:
            print("목적지 폴더를 찾지 못해 스크립트를 종료합니다.")
            return
        DEST_FOLDER_ID = found_id
        print(f"목적지 폴더 ID 확인 완료: {DEST_FOLDER_ID}")
    
    # 1. 내 드라이브 목적지 경로의 기존 폴더 목록 확인
    print(f"목적지 폴더(ID: {DEST_FOLDER_ID}) 내의 기존 폴더 목록을 스캔합니다...")
    dest_folders = get_subfolders(service, DEST_FOLDER_ID)
    existing_folder_names = {folder['name'] for folder in dest_folders}
    print(f"이미 존재하는 폴더 목록: {list(existing_folder_names)}")
    
    # 2. 공유받은 자료 폴더 내의 하위 폴더 목록 스캔
    print(f"공유폴더(ID: {SHARED_FOLDER_ID}) 내의 폴더 목록을 스캔합니다...")
    shared_folders = get_subfolders(service, SHARED_FOLDER_ID)
    
    if not shared_folders:
        print("공유폴더 내에 폴더가 존재하지 않거나 접근할 수 없습니다.")
        return
        
    print(f"공유폴더 내 발견된 폴더 개수: {len(shared_folders)}개")
    
    # 3. 중복 제거 및 미복사 폴더 복사 진행 (단발성)
    copied_count = 0
    for folder in shared_folders:
        folder_name = folder['name']
        folder_id = folder['id']
        
        # 1일차, 2일차, 3일차와 같이 이미 내 드라이브 목적지에 있는 폴더는 스킵
        if folder_name in existing_folder_names:
            print(f"-> [스킵] '{folder_name}' 폴더는 이미 목적지에 존재하므로 복사하지 않고 건너뜁니다.")
            continue
            
        print(f"\n-> [복사 시작] 신규 폴더 발견: '{folder_name}' (ID: {folder_id})")
        
        # 목적지 폴더 하위에 동일한 이름의 새 폴더 생성
        try:
            new_folder = service.files().create(
                body={
                    'name': folder_name,
                    'mimeType': 'application/vnd.google-apps.folder',
                    'parents': [DEST_FOLDER_ID]
                },
                fields='id'
            ).execute()
            new_folder_id = new_folder.get('id')
            print(f"  └ 목적지 폴더에 '{folder_name}' 생성 완료 (새 폴더 ID: {new_folder_id})")
            
            # 신규 폴더 내부의 콘텐츠들을 복사
            copy_folder_contents_recursive(service, folder_id, new_folder_id)
            print(f"  └ '{folder_name}' 폴더의 모든 콘텐츠 복사 완료!")
            copied_count += 1
        except HttpError as error:
            print(f"폴더 생성 또는 복사 도중 에러가 발생했습니다: {error}")
            
    print("\n==========================================")
    print(f"단발성 복사 작업이 완료되었습니다. 총 {copied_count}개의 신규 폴더를 복사했습니다.")
    print("스크립트를 종료합니다.")
    print("==========================================")

if __name__ == '__main__':
    main()
