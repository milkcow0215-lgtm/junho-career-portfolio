import os
import FinanceDataReader as fdr
from datetime import datetime

# Define Expanded Universe
US_TICKERS = ['AAPL', 'MSFT', 'GOOGL', 'AMZN', 'NVDA']
KR_TICKERS = ['005930', '000660', '373220', '207940', '005380']  # Samsung, SK Hynix, LG Energy, Samsung Bio, Hyundai Motor
MACRO_TICKERS = {'USD/KRW': 'usd_krw_rate'}

def main():
    # 1. Create data directory
    os.makedirs('data', exist_ok=True)
    print("Created 'data' directory (if it did not exist).")

    # Define date range
    start_date = '2021-01-01'
    end_date = datetime.now().strftime('%Y-%m-%d')
    print(f"Fetching data from {start_date} to {end_date}...")

    # 2. Fetch US Stocks
    for ticker in US_TICKERS:
        try:
            print(f"Fetching US Stock: {ticker}...")
            df = fdr.DataReader(ticker, start_date, end_date)
            path = os.path.join('data', f'{ticker.lower()}_price.csv')
            df.to_csv(path)
            print(f"Successfully saved {ticker} data (rows: {len(df)}) to {path}")
        except Exception as e:
            print(f"Error fetching {ticker}: {e}")

    # 3. Fetch KR Stocks
    for ticker in KR_TICKERS:
        try:
            print(f"Fetching KR Stock: {ticker}...")
            df = fdr.DataReader(ticker, start_date, end_date)
            path = os.path.join('data', f'{ticker}_price.csv')
            df.to_csv(path)
            print(f"Successfully saved {ticker} data (rows: {len(df)}) to {path}")
        except Exception as e:
            print(f"Error fetching {ticker}: {e}")

    # 4. Fetch Macro Indicators
    for ticker, filename in MACRO_TICKERS.items():
        try:
            print(f"Fetching Macro Indicator: {ticker}...")
            df = fdr.DataReader(ticker, start_date, end_date)
            path = os.path.join('data', f'{filename}.csv')
            df.to_csv(path)
            print(f"Successfully saved {ticker} data (rows: {len(df)}) to {path}")
        except Exception as e:
            print(f"Error fetching {ticker}: {e}")

if __name__ == '__main__':
    main()
