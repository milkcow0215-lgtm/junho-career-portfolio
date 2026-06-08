import os
import json
import pandas as pd
from datetime import datetime

# Set Matplotlib backend to Agg for headless environments
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.dates as mdates

# Configuration
PORTFOLIO_FILE = 'portfolio.json'
ORDER_FILE = os.path.join('data', 'today_order.json')
PLOT_FILE = os.path.join('plots', 'daily_chart.png')

US_TICKERS = ['AAPL', 'MSFT', 'GOOGL', 'AMZN', 'NVDA', 'QQQ', 'TLT']
KR_TICKERS = ['005930', '000660', '373220', '207940', '005380']
TICKER_NAMES = {
    'AAPL': 'Apple', 'MSFT': 'Microsoft', 'GOOGL': 'Alphabet', 'AMZN': 'Amazon', 'NVDA': 'NVIDIA',
    'QQQ': 'Invesco QQQ', 'TLT': 'iShares 20+ Yr Treasury',
    '005930': '삼성전자', '000660': 'SK하이닉스', '373220': 'LG에너지솔루션', '207940': '삼성바이오로직스', '005380': '현대차'
}

STOP_LOSS_PCT = 0.07
MACRO_RISK_LIMIT = 1550.0
STABLE_FX_LIMIT = 1530.0
SMA_PERIOD = 20
FX_SMA_PERIOD = 5

def load_portfolio():
    default_portfolio = {
        "cash": 10000.0,
        "assets": {}
    }
    # Initialize all assets in portfolio
    for ticker in US_TICKERS + KR_TICKERS:
        default_portfolio["assets"][ticker] = {"shares": 0, "entry_price": 0.0}

    if os.path.exists(PORTFOLIO_FILE):
        try:
            with open(PORTFOLIO_FILE, 'r') as f:
                data = json.load(f)
            
            # Ensure assets dictionary exists and has all keys
            if 'assets' not in data:
                data['assets'] = {}
            
            for ticker in US_TICKERS + KR_TICKERS:
                if ticker not in data['assets']:
                    # Transfer old single asset data if any
                    if ticker == 'NVDA' and 'shares' in data and 'entry_price' in data:
                        data['assets']['NVDA'] = {"shares": data.get('shares', 0), "entry_price": data.get('entry_price', 0.0)}
                    else:
                        data['assets'][ticker] = {"shares": 0, "entry_price": 0.0}
            
            # Clean up old single asset keys
            for key in ['shares', 'entry_price']:
                data.pop(key, None)
                
            return data
        except Exception:
            with open(PORTFOLIO_FILE, 'w') as f:
                json.dump(default_portfolio, f, indent=4)
            return default_portfolio
    else:
        with open(PORTFOLIO_FILE, 'w') as f:
            json.dump(default_portfolio, f, indent=4)
        return default_portfolio

def generate_visualization(df_merged):
    # Slice the latest 1 year of data for visualization (approx 252 trading days)
    df_1y = df_merged.tail(252).copy()
    
    # Run chronological simulation over the 1-year data to identify signal dates for AAPL and Samsung (005930)
    plot_tickers = ['AAPL', '005930']
    signals = {t: {'buys': [], 'sells': []} for t in plot_tickers}
    
    for ticker in plot_tickers:
        suffix = ticker.lower()
        holding = False
        entry_price = 0.0
        
        for idx, row in df_1y.iterrows():
            close_price = row[f'Close_{suffix}']
            sma20 = row[f'{suffix}_sma20']
            fx_close = row['Close_fx']
            fx_sma5 = row['fx_sma5']
            
            if pd.isna(close_price) or pd.isna(sma20) or pd.isna(fx_close) or pd.isna(fx_sma5):
                continue
                
            macro_risk = fx_close > MACRO_RISK_LIMIT
            stable_fx = fx_sma5 <= STABLE_FX_LIMIT
            uptrend = close_price > sma20
            
            if holding:
                loss_pct = (close_price - entry_price) / entry_price
                if loss_pct <= -STOP_LOSS_PCT or macro_risk or not uptrend:
                    signals[ticker]['sells'].append((idx, close_price))
                    holding = False
            else:
                if not macro_risk and stable_fx and uptrend:
                    signals[ticker]['buys'].append((idx, close_price))
                    holding = True
                    entry_price = close_price

    # Setup plotting style (sleek dark mode)
    plt.style.use('dark_background')
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(14, 10), sharex=True)
    fig.suptitle('Quantitative Screening Dashboard (AAPL & 삼성전자)', fontsize=16, fontweight='bold', color='#ffffff', y=0.95)
    
    # Plot AAPL (Top Plot)
    ax1.plot(df_1y.index, df_1y['Close_aapl'], color='#00f0ff', label='AAPL Close', linewidth=1.5)
    ax1.plot(df_1y.index, df_1y['aapl_sma20'], color='#ff9900', label='AAPL SMA 20', linestyle='--', linewidth=1.2)
    ax1.set_ylabel('AAPL Price (USD)', color='#ffffff', fontsize=12)
    ax1.grid(True, color='#2a2a2a', linestyle=':', linewidth=0.5)
    
    # Plot AAPL BUY/SELL markers
    if signals['AAPL']['buys']:
        buy_dates, buy_prices = zip(*signals['AAPL']['buys'])
        ax1.scatter(buy_dates, buy_prices, color='#00ff00', marker='^', s=120, label='BUY Signal', zorder=5)
    if signals['AAPL']['sells']:
        sell_dates, sell_prices = zip(*signals['AAPL']['sells'])
        ax1.scatter(sell_dates, sell_prices, color='#ff3333', marker='v', s=120, label='SELL Signal', zorder=5)
    ax1.legend(loc='upper left', frameon=True, facecolor='#121212', edgecolor='#2a2a2a')

    # Plot Samsung (Bottom Plot)
    ax2.plot(df_1y.index, df_1y['Close_005930'], color='#ff00ff', label='삼성전자 Close', linewidth=1.5)
    ax2.plot(df_1y.index, df_1y['005930_sma20'], color='#ffcc00', label='삼성전자 SMA 20', linestyle='--', linewidth=1.2)
    ax2.set_ylabel('Samsung Price (KRW)', color='#ffffff', fontsize=12)
    ax2.set_xlabel('Date', color='#ffffff', fontsize=12)
    ax2.grid(True, color='#2a2a2a', linestyle=':', linewidth=0.5)
    
    # Plot Samsung BUY/SELL markers
    if signals['005930']['buys']:
        buy_dates, buy_prices = zip(*signals['005930']['buys'])
        ax2.scatter(buy_dates, buy_prices, color='#00ff00', marker='^', s=120, label='BUY Signal', zorder=5)
    if signals['005930']['sells']:
        sell_dates, sell_prices = zip(*signals['005930']['sells'])
        ax2.scatter(sell_dates, sell_prices, color='#ff3333', marker='v', s=120, label='SELL Signal', zorder=5)
    ax2.legend(loc='upper left', frameon=True, facecolor='#121212', edgecolor='#2a2a2a')

    # Highlight Exchange Rate Risk Areas (FX > 1380 KRW) in both plots
    fx_risk_mask = df_1y['Close_fx'] > MACRO_RISK_LIMIT
    
    ax1.fill_between(df_1y.index, 0, 1, where=fx_risk_mask, color='#ff3333', alpha=0.15, transform=ax1.get_xaxis_transform(), label='Macro Risk (FX > 1380)')
    ax2.fill_between(df_1y.index, 0, 1, where=fx_risk_mask, color='#ff3333', alpha=0.15, transform=ax2.get_xaxis_transform(), label='Macro Risk (FX > 1380)')
    
    ax1.legend(loc='upper left', frameon=True, facecolor='#121212', edgecolor='#2a2a2a')
    ax2.legend(loc='upper left', frameon=True, facecolor='#121212', edgecolor='#2a2a2a')

    # Format Date Axis
    plt.gca().xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m'))
    plt.gca().xaxis.set_major_locator(mdates.MonthLocator(interval=2))
    plt.gcf().autofmt_xdate()
    
    os.makedirs(os.path.dirname(PLOT_FILE), exist_ok=True)
    plt.tight_layout()
    plt.savefig(PLOT_FILE, dpi=150)
    plt.close()
    print(f"Daily chart saved successfully to {PLOT_FILE}.")

def main():
    # 1. Load Portfolio Status
    portfolio = load_portfolio()
    assets = portfolio['assets']

    # 2. Load latest market data for all 10 stocks + FX
    data_files = {}
    for ticker in US_TICKERS:
        data_files[ticker.lower()] = os.path.join('data', f'{ticker.lower()}_price.csv')
    for ticker in KR_TICKERS:
        data_files[ticker] = os.path.join('data', f'{ticker}_price.csv')
    data_files['fx'] = os.path.join('data', 'usd_krw_rate.csv')

    for name, path in data_files.items():
        if not os.path.exists(path):
            print(f"Market data file {path} not found. Please run fetch_data.py first.")
            return

    # Load DataFrames
    dfs = {}
    for name, path in data_files.items():
        df = pd.read_csv(path, parse_dates=True, index_col=0)
        df.dropna(subset=['Close'], inplace=True)
        df = df[['Open', 'High', 'Low', 'Close', 'Volume']].copy()
        df.columns = [f'{c}_{name}' for c in df.columns]
        dfs[name] = df

    # Merge all DataFrames sequentially
    tickers_keys = list(data_files.keys())
    df_merged = dfs[tickers_keys[0]]
    for key in tickers_keys[1:]:
        df_merged = df_merged.join(dfs[key], how='outer')
        
    df_merged.sort_index(inplace=True)
    df_merged.ffill(inplace=True)
    
    # Drop rows that are completely empty or missing required data
    df_merged.dropna(subset=[f'Close_{k}' for k in tickers_keys], inplace=True)

    # Calculate Indicators on full dataset
    for key in tickers_keys:
        if key != 'fx':
            df_merged[f'{key}_sma20'] = df_merged[f'Close_{key}'].rolling(window=SMA_PERIOD).mean()
    df_merged['fx_sma5'] = df_merged['Close_fx'].rolling(window=FX_SMA_PERIOD).mean()

    # Get the latest data
    latest_data = df_merged.iloc[-1]
    latest_date = df_merged.index[-1].strftime('%Y-%m-%d')
    
    fx_close = float(latest_data['Close_fx'])
    fx_sma5 = float(latest_data['fx_sma5'])

    macro_risk_triggered = fx_close > MACRO_RISK_LIMIT
    stable_fx = fx_sma5 <= STABLE_FX_LIMIT

    # 3. Generate Chart (AAPL & Samsung)
    generate_visualization(df_merged)

    # 4. Evaluate Trading Signal for all 10 stocks
    orders = []

    for ticker in US_TICKERS + KR_TICKERS:
        key = ticker.lower()
        name_kr = TICKER_NAMES.get(ticker, ticker)
        
        close_price = float(latest_data[f'Close_{key}'])
        sma20 = float(latest_data[f'{key}_sma20'])
        
        shares = assets[ticker]['shares']
        entry_price = assets[ticker]['entry_price']
        
        action = "HOLD"
        reason = ""

        # Flags
        uptrend = close_price > sma20
        is_us = ticker in US_TICKERS
        price_unit = "USD" if is_us else "KRW"

        if shares > 0:
            # We are holding the asset. Check exits:
            loss_pct = (close_price - entry_price) / entry_price
            
            # A. Stop-Loss
            if loss_pct <= -STOP_LOSS_PCT:
                action = "SELL"
                reason = f"STOP-LOSS TRIGGERED! {name_kr} fell {loss_pct*100:.2f}% from entry price {entry_price:.2f} {price_unit}."
            # B. Macro Risk
            elif macro_risk_triggered:
                action = "SELL"
                reason = f"MACRO RISK TRIGGERED! Exchange rate ({fx_close:.2f} KRW) exceeds limit of {MACRO_RISK_LIMIT} KRW."
            # C. Trend Exit
            elif not uptrend:
                action = "SELL"
                reason = f"TREND REVERSAL! {name_kr} Close ({close_price:.2f} {price_unit}) fell below 20-day SMA ({sma20:.2f} {price_unit})."
            else:
                action = "HOLD"
                reason = f"Holding {name_kr}. Current return: {loss_pct*100:.2f}%. Close stays above SMA 20."
        else:
            # We do not hold the asset. Check entries:
            if macro_risk_triggered:
                action = "HOLD"
                reason = f"환율 리스크 발생으로 인한 관망 (USD/KRW: {fx_close:.2f} KRW)"
            elif not stable_fx:
                action = "HOLD"
                reason = f"환율 불안정으로 인한 관망 (5-day SMA: {fx_sma5:.2f} KRW)"
            elif not uptrend:
                action = "HOLD"
                reason = f"{name_kr} SMA 20 하회로 인한 관망 (Close: {close_price:,.2f} {price_unit} <= SMA20: {sma20:,.2f})"
            else:
                action = "BUY"
                reason = f"환율 안정 및 {name_kr} SMA 20 상회로 인한 매수"

        orders.append({
            "ticker": ticker,
            "action": action,
            "reason": reason
        })

    # 5. Save Signal Output
    today_order = {
        "evaluation_date": latest_date,
        "macro_risk_triggered": macro_risk_triggered,
        "orders": orders
    }

    # Ensure output directory exists
    os.makedirs(os.path.dirname(ORDER_FILE), exist_ok=True)
    with open(ORDER_FILE, 'w', encoding='utf-8') as f:
        json.dump(today_order, f, indent=2, ensure_ascii=False)
        
    print(f"Multi-asset screening complete. Output saved to {ORDER_FILE}.")
    print("\n================ Today's Screening Order Signal ================")
    print(json.dumps(today_order, indent=2, ensure_ascii=False))
    print("================================================================")

    # 6. Trigger Telegram Notification
    try:
        from notifier import send_telegram_notification
        send_telegram_notification()
    except Exception as e:
        print(f"Failed to trigger Telegram notification: {e}")

    # 7. Execute KIS Broker Order Execution
    try:
        from kis_broker import run_kis_broker
        run_kis_broker()
    except Exception as e:
        print(f"Failed to run KIS broker: {e}")

if __name__ == '__main__':
    main()
