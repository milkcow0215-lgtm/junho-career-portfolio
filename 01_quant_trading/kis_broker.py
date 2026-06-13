import os
import json
import requests
import pandas as pd

# API Domain Configuration for KIS Mock Trading
BASE_URL = "https://openapivts.koreainvestment.com:29443"
PORTFOLIO_FILE = 'portfolio.json'
ORDER_FILE = os.path.join('data', 'today_order.json')

# Allocations for the 5 US stocks (3% each, total 15%)
# Keep KR stocks at 0% for now in automatic mock broker, as domestic order APIs have different schemas
ALLOCATIONS = {
    'AAPL': 0.03,
    'MSFT': 0.03,
    'GOOGL': 0.03,
    'AMZN': 0.03,
    'NVDA': 0.03
}

US_TICKERS = ['AAPL', 'MSFT', 'GOOGL', 'AMZN', 'NVDA', 'QQQ', 'TLT']
KR_TICKERS = ['005930', '000660', '373220', '207940', '005380']

def load_env(env_path='.env'):
    if os.path.exists(env_path):
        with open(env_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    os.environ[key.strip()] = value.strip()

def get_access_token(app_key, app_secret):
    url = f"{BASE_URL}/oauth2/tokenP"
    payload = {
        "grant_type": "client_credentials",
        "appkey": app_key,
        "secretkey": app_secret
    }
    headers = {"content-type": "application/json"}
    try:
        response = requests.post(url, json=payload, headers=headers, timeout=10)
        if response.status_code == 200:
            return response.json().get("access_token")
        else:
            print(f"[KIS Token] Failed to get token: {response.text}")
            return None
    except Exception as e:
        print(f"[KIS Token] Connection error: {e}")
        return None

def query_kis_balance(access_token, app_key, app_secret, cano, acnt_prdt_cd):
    url = f"{BASE_URL}/uapi/overseas-stock/v1/trading/inquire-balance"
    headers = {
        "content-type": "application/json",
        "authorization": f"Bearer {access_token}",
        "appkey": app_key,
        "appsecret": app_secret,
        "tr_id": "VTTP6504R"  # Mock Trading Balance Query TR ID
    }
    params = {
        "CANO": cano,
        "ACNT_PRDT_CD": acnt_prdt_cd,
        "OVRS_EXCG_CD": "NASD",
        "TR_CRCY_CD": "USD",
        "CTX_AREA_FK200": "",
        "CTX_AREA_NK200": ""
    }
    try:
        response = requests.get(url, headers=headers, params=params, timeout=10)
        if response.status_code == 200:
            res_data = response.json()
            output2 = res_data.get("output2", {})
            cash_usd = float(output2.get("frcr_dncl_amt_2", 0.0))
            print(f"[KIS API] Successfully queried account balance: {cash_usd:.2f} USD")
            return cash_usd
        else:
            print(f"[KIS API] Balance query rejected: {response.json().get('rt_msg', response.text)}")
            return None
    except Exception as e:
        print(f"[KIS API] Balance query connection error: {e}")
        return None

def submit_kis_order(access_token, app_key, app_secret, cano, acnt_prdt_cd, ticker, action, qty, price):
    url = f"{BASE_URL}/uapi/overseas-stock/v1/trading/order"
    
    tr_id = "VTTT1002U" if action == "BUY" else "VTTT1006U"
    
    headers = {
        "content-type": "application/json; charset=utf-8",
        "authorization": f"Bearer {access_token}",
        "appkey": app_key,
        "appsecret": app_secret,
        "tr_id": tr_id,
        "custtype": "P"
    }
    
    payload = {
        "CANO": cano,
        "ACNT_PRDT_CD": acnt_prdt_cd,
        "OVRS_EXCG_CD": "NASD",
        "PDNO": ticker,
        "ORD_QTY": str(qty),
        "ORD_UNPR": f"{price:.2f}",
        "ORD_DVSN": "00"  # Limit order
    }
    
    try:
        # Pre-order safety log (Required)
        print(f"[MOCK TRADE] 주문 전송 - 종목: {ticker}, 수량: {qty}주, 예상가: ${price:.2f}")
        
        response = requests.post(url, json=payload, headers=headers, timeout=10)
        if response.status_code == 200:
            res_data = response.json()
            rt_msg = res_data.get("rt_msg", "Success")
            print(f"[KIS API] Order Response: {rt_msg} (rt_cd: {res_data.get('rt_cd')})")
            return True
        else:
            print(f"[KIS API] Order failed: {response.text}")
            return False
    except Exception as e:
        print(f"[KIS API] Order connection error: {e}")
        return False

def get_latest_price(ticker):
    csv_path = os.path.join('data', f'{ticker.lower()}_price.csv')
    if os.path.exists(csv_path):
        df = pd.read_csv(csv_path, index_col=0)
        df.dropna(subset=['Close'], inplace=True)
        if not df.empty:
            return float(df['Close'].iloc[-1])
    return 100.0  # Fallback price

def run_kis_broker():
    load_env()
    
    app_key = os.getenv("KIS_APP_KEY")
    app_secret = os.getenv("KIS_APP_SECRET")
    acc_num = os.getenv("KIS_ACCOUNT_NUMBER", "1234567801").replace("-", "")
    
    cano = acc_num[:8]
    acnt_prdt_cd = acc_num[8:10] if len(acc_num) >= 10 else "01"
    
    # 1. Load Local Portfolio (Fallback & State Tracking)
    if os.path.exists(PORTFOLIO_FILE):
        with open(PORTFOLIO_FILE, 'r', encoding='utf-8') as f:
            portfolio = json.load(f)
    else:
        portfolio = {
            "cash": 10000.0,
            "assets": {}
        }
        for t in US_TICKERS + KR_TICKERS:
            portfolio["assets"][t] = {"shares": 0, "entry_price": 0.0}

    # 2. Get Access Token
    access_token = None
    if app_key and app_key != "YOUR_KIS_APP_KEY_HERE" and app_secret and app_secret != "YOUR_KIS_APP_SECRET_HERE":
        print("Authenticating with KIS OpenAPI...")
        access_token = get_access_token(app_key, app_secret)
        
    # 3. Query Account Balance (If authenticated)
    cash_balance = None
    if access_token:
        cash_balance = query_kis_balance(access_token, app_key, app_secret, cano, acnt_prdt_cd)
        
    if cash_balance is not None:
        portfolio['cash'] = cash_balance
    else:
        print(f"[KIS Broker] Using local fallback cash balance: {portfolio['cash']:.2f} USD")
        
    total_val = portfolio['cash']
    # Add stock values to total portfolio value
    for ticker in portfolio.get('assets', {}).keys():
        shares = portfolio['assets'][ticker]['shares']
        if shares > 0:
            price = get_latest_price(ticker)
            # Handle KRW to USD conversion for KR stocks if we want exact calculation, 
            # but for simplicity we assume price units match
            if ticker in KR_TICKERS:
                # Roughly convert KRW to USD for portfolio valuation
                total_val += (shares * price) / 1350.0
            else:
                total_val += shares * price

    # 4. Process Today's Orders
    if not os.path.exists(ORDER_FILE):
        print(f"[KIS Broker] Order file {ORDER_FILE} not found. Run trade_signal.py first.")
        return

    with open(ORDER_FILE, 'r', encoding='utf-8') as f:
        today_order = json.load(f)

    order_executed = False
    
    for order in today_order.get("orders", []):
        ticker = order.get("ticker")
        action = order.get("action")
        
        if not ticker or action == "HOLD":
            continue
            
        price = get_latest_price(ticker)
        
        if action == "BUY":
            # For domestic stocks, skip automated execution to prevent API schema errors (requires KR order format)
            if ticker in KR_TICKERS:
                print(f"[KIS Broker] Domestic stock {ticker} BUY order skipped. (Domestic OpenAPI order format requires separate implementation)")
                continue
                
            # Target allocation percentage (3% each for US stocks)
            alloc = ALLOCATIONS.get(ticker, 0.0)
            target_usd = total_val * alloc
            qty = int(target_usd // price)
            
            if qty > 0:
                cost = qty * price
                if portfolio['cash'] >= cost:
                    order_executed = True
                    success = False
                    if access_token:
                        success = submit_kis_order(access_token, app_key, app_secret, cano, acnt_prdt_cd, ticker, action, qty, price)
                    
                    if not access_token or not success:
                        if not access_token:
                            print(f"[MOCK TRADE] 주문 전송 - 종목: {ticker}, 수량: {qty}주, 예상가: ${price:.2f} (인증 실패로 로컬 가상 체결)")
                        portfolio['cash'] -= cost
                        portfolio['assets'][ticker]['shares'] += qty
                        portfolio['assets'][ticker]['entry_price'] = price
                else:
                    print(f"[KIS Broker] Insufficient cash for {ticker}. Required: {cost:.2f} USD, Available: {portfolio['cash']:.2f} USD")
                    
        elif action == "SELL":
            if ticker in KR_TICKERS:
                print(f"[KIS Broker] Domestic stock {ticker} SELL order skipped. (Domestic OpenAPI order format requires separate implementation)")
                continue
                
            qty = portfolio['assets'][ticker]['shares']
            if qty > 0:
                order_executed = True
                success = False
                if access_token:
                    success = submit_kis_order(access_token, app_key, app_secret, cano, acnt_prdt_cd, ticker, action, qty, price)
                
                if not access_token or not success:
                    if not access_token:
                        print(f"[MOCK TRADE] 주문 전송 - 종목: {ticker}, 수량: {qty}주, 예상가: ${price:.2f} (인증 실패로 로컬 가상 체결)")
                    portfolio['cash'] += qty * price
                    portfolio['assets'][ticker]['shares'] = 0
                    portfolio['assets'][ticker]['entry_price'] = 0.0
            else:
                print(f"[KIS Broker] No shares of {ticker} holding. Skipping SELL order.")

    # 5. Save updated portfolio locally
    if order_executed:
        with open(PORTFOLIO_FILE, 'w', encoding='utf-8') as f:
            json.dump(portfolio, f, indent=4)
        print("[KIS Broker] Local portfolio state updated successfully.")
    else:
        print("[KIS Broker] No trades executed today.")

if __name__ == '__main__':
    run_kis_broker()
