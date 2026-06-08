import os
import pandas as pd
import backtrader as bt

class MultiAssetStrategy(bt.Strategy):
    params = (
        ('stable_exchange_limit', 1530.0),  # Raised from 1350 to 1530
        ('macro_risk_limit', 1550.0),       # Raised from 1380 to 1550
        ('sma_period', 20),
        ('fx_sma_period', 5),
        ('stop_loss_pct', 0.07),            # 7% Stop-Loss
        ('exit_on_sma', False),             # Exit when asset falls below SMA 20
        ('allocations', {}),                # Dict of data name -> target allocation pct
    )

    def log(self, txt, dt=None):
        dt = dt or self.datas[0].datetime.date(0)
        print(f'{dt.isoformat()}, {txt}')

    def __init__(self):
        # Identify the FX feed (USD_KRW) and tradeable feeds
        self.fx = self.getdatabyname('USD_KRW')
        self.trade_datas = [d for d in self.datas if d._name != 'USD_KRW']

        # Indicators
        self.fx_sma = bt.indicators.SimpleMovingAverage(self.fx.close, period=self.p.fx_sma_period)
        self.smas = {}
        for d in self.trade_datas:
            self.smas[d] = bt.indicators.SimpleMovingAverage(d.close, period=self.p.sma_period)

        # Track entry prices and orders per asset
        self.entry_prices = {}
        self.orders = {}
        for d in self.trade_datas:
            self.entry_prices[d] = None
            self.orders[d] = None

    def notify_order(self, order):
        d = order.data
        if order.status in [order.Submitted, order.Accepted]:
            return

        if order.status in [order.Completed]:
            if order.isbuy():
                self.log(f'[{d._name}] BUY EXECUTED, Price: {order.executed.price:.2f}, Cost: {order.executed.value:.2f}, Comm: {order.executed.comm:.2f}')
                self.entry_prices[d] = order.executed.price
            else:  # Sell
                self.log(f'[{d._name}] SELL EXECUTED, Price: {order.executed.price:.2f}, Cost: {order.executed.value:.2f}, Comm: {order.executed.comm:.2f}')
                # If position is closed, clear entry price
                pos = self.getposition(d)
                if pos.size == 0:
                    self.entry_prices[d] = None

        elif order.status in [order.Canceled, order.Margin, order.Rejected]:
            self.log(f'[{d._name}] Order Canceled/Margin/Rejected: Status {order.status}')

        self.orders[d] = None

    def notify_trade(self, trade):
        if not trade.isclosed:
            return
        self.log(f'[{trade.data._name}] OPERATION PROFIT, GROSS: {trade.pnl:.2f}, NET: {trade.pnlcomm:.2f}')

    def next(self):
        # 1. Macro Risk Check (FX Close > 1380)
        macro_risk = self.fx.close[0] > self.p.macro_risk_limit

        for d in self.trade_datas:
            if self.orders[d]:
                continue  # Skip if an order is pending for this asset

            pos = self.getposition(d)
            alloc = self.p.allocations.get(d._name, 0.0)

            # If macro risk is triggered, liquidate existing positions immediately
            if macro_risk:
                if pos.size > 0:
                    self.log(f'[{d._name}] Macro Risk Triggered! FX: {self.fx.close[0]:.2f}. Liquidating position.')
                    self.orders[d] = self.close(data=d)
                continue

            # If holding a position, check for exit signals
            if pos.size > 0:
                # A. Check Stop-Loss (-7% from entry price)
                entry = self.entry_prices.get(d)
                if entry:
                    loss_pct = (d.close[0] - entry) / entry
                    if loss_pct <= -self.p.stop_loss_pct:
                        self.log(f'[{d._name}] STOP-LOSS TRIGGERED! Price ({d.close[0]:.2f}) fell {loss_pct*100:.2f}% from entry ({entry:.2f}). Liquidating.')
                        self.orders[d] = self.close(data=d)
                        continue

                # B. Check SMA 20 Trend Exit (if enabled)
                if self.p.exit_on_sma:
                    d_sma = self.smas[d][0]
                    if d.close[0] < d_sma:
                        self.log(f'[{d._name}] Trend Reversal! Close ({d.close[0]:.2f}) < SMA ({d_sma:.2f}). Liquidating.')
                        self.orders[d] = self.close(data=d)
                        continue

            # If not holding a position, check for buy signals
            elif alloc > 0.0:
                stable_fx = self.fx_sma[0] <= self.p.stable_exchange_limit
                d_sma = self.smas[d][0]
                d_uptrend = d.close[0] > d_sma

                if stable_fx and d_uptrend:
                    self.log(f'[{d._name}] Buy Signal! Close: {d.close[0]:.2f} > SMA: {d_sma:.2f}, FX SMA: {self.fx_sma[0]:.2f} <= {self.p.stable_exchange_limit}')
                    self.orders[d] = self.order_target_percent(data=d, target=alloc)


def run_backtest(strategy_name, allocations, exit_on_sma=False):
    # Load raw data
    nvda_path = os.path.join('data', 'nvda_price.csv')
    qqq_path = os.path.join('data', 'qqq_price.csv')
    tlt_path = os.path.join('data', 'tlt_price.csv')
    usd_krw_path = os.path.join('data', 'usd_krw_rate.csv')

    for p in [nvda_path, qqq_path, tlt_path, usd_krw_path]:
        if not os.path.exists(p):
            print(f"Data file {p} not found. Please run fetch_data.py first.")
            return None

    # Load and clean DataFrames
    df_nvda = pd.read_csv(nvda_path, parse_dates=True, index_col=0)
    df_qqq = pd.read_csv(qqq_path, parse_dates=True, index_col=0)
    df_tlt = pd.read_csv(tlt_path, parse_dates=True, index_col=0)
    df_fx = pd.read_csv(usd_krw_path, parse_dates=True, index_col=0)

    df_nvda.dropna(subset=['Close'], inplace=True)
    df_qqq.dropna(subset=['Close'], inplace=True)
    df_tlt.dropna(subset=['Close'], inplace=True)
    df_fx.dropna(subset=['Close'], inplace=True)

    # Rename columns to prevent conflicts
    df_nvda = df_nvda[['Open', 'High', 'Low', 'Close', 'Volume']].copy()
    df_nvda.columns = [c + '_nvda' for c in df_nvda.columns]

    df_qqq = df_qqq[['Open', 'High', 'Low', 'Close', 'Volume']].copy()
    df_qqq.columns = [c + '_qqq' for c in df_qqq.columns]

    df_tlt = df_tlt[['Open', 'High', 'Low', 'Close', 'Volume']].copy()
    df_tlt.columns = [c + '_tlt' for c in df_tlt.columns]

    df_fx = df_fx[['Open', 'High', 'Low', 'Close', 'Volume']].copy()
    df_fx.columns = [c + '_fx' for c in df_fx.columns]

    # Align indexes
    df_merged = df_nvda.join(df_qqq, how='outer')
    df_merged = df_merged.join(df_tlt, how='outer')
    df_merged = df_merged.join(df_fx, how='outer')
    
    df_merged.sort_index(inplace=True)
    df_merged.ffill(inplace=True)
    df_merged.bfill(inplace=True)

    def get_aligned_df(suffix):
        df = df_merged[[f'Open_{suffix}', f'High_{suffix}', f'Low_{suffix}', f'Close_{suffix}', f'Volume_{suffix}']].copy()
        df.columns = ['open', 'high', 'low', 'close', 'volume']
        return df

    df_nvda_aligned = get_aligned_df('nvda')
    df_qqq_aligned = get_aligned_df('qqq')
    df_tlt_aligned = get_aligned_df('tlt')
    df_fx_aligned = get_aligned_df('fx')

    # Initialize cerebro
    cerebro = bt.Cerebro()

    # Add data feeds
    cerebro.adddata(bt.feeds.PandasData(dataname=df_nvda_aligned), name='NVDA')
    cerebro.adddata(bt.feeds.PandasData(dataname=df_qqq_aligned), name='QQQ')
    cerebro.adddata(bt.feeds.PandasData(dataname=df_tlt_aligned), name='TLT')
    cerebro.adddata(bt.feeds.PandasData(dataname=df_fx_aligned), name='USD_KRW')

    # Add strategy
    cerebro.addstrategy(
        MultiAssetStrategy, 
        allocations=allocations, 
        exit_on_sma=exit_on_sma
    )

    # Set broker parameters
    initial_cash = 10000.0
    cerebro.broker.setcash(initial_cash)
    cerebro.broker.setcommission(commission=0.001)

    # Add analyzers
    cerebro.addanalyzer(bt.analyzers.DrawDown, _name='drawdown')

    # Run backtest
    results = cerebro.run()
    strat = results[0]

    final_value = cerebro.broker.getvalue()
    total_return = ((final_value - initial_cash) / initial_cash) * 100
    mdd = strat.analyzers.drawdown.get_analysis().max.drawdown

    return {
        'initial': initial_cash,
        'final': final_value,
        'return': total_return,
        'mdd': mdd
    }

if __name__ == '__main__':
    print("==================================================")
    print("Running Baseline Scenario: Single NVDA Portfolio")
    print("Allocation: 15% NVDA, 85% Cash. Exit: FX > 1380 OR NVDA < SMA 20")
    print("Stop-Loss: -7% from entry")
    print("==================================================")
    res_nvda = run_backtest("NVDA Only", allocations={'NVDA': 0.15}, exit_on_sma=True)

    print("\n==================================================")
    print("Running Scenario A: Diversified Portfolio (QQQ + TLT)")
    print("Allocation: 10% QQQ, 5% TLT, 85% Cash. Exit: FX > 1380 Only")
    print("Stop-Loss: -7% from entry")
    print("==================================================")
    res_div_fx = run_backtest("QQQ+TLT (FX Exit)", allocations={'QQQ': 0.10, 'TLT': 0.05}, exit_on_sma=False)

    print("\n==================================================")
    print("Running Scenario B: Diversified Portfolio (QQQ + TLT)")
    print("Allocation: 10% QQQ, 5% TLT, 85% Cash. Exit: FX > 1380 OR SMA 20")
    print("Stop-Loss: -7% from entry")
    print("==================================================")
    res_div_sma = run_backtest("QQQ+TLT (FX+SMA Exit)", allocations={'QQQ': 0.10, 'TLT': 0.05}, exit_on_sma=True)

    if res_nvda and res_div_fx and res_div_sma:
        print('\n==================== Performance Comparison Report ====================')
        print(f'Metric                  | NVDA (15% alloc) | QQQ+TLT (FX Exit) | QQQ+TLT (FX+SMA)')
        print(f'-----------------------------------------------------------------------')
        print(f'Initial Capital         | {res_nvda["initial"]:,.2f} USD      | {res_div_fx["initial"]:,.2f} USD      | {res_div_sma["initial"]:,.2f} USD')
        print(f'Final Portfolio Value   | {res_nvda["final"]:,.2f} USD     | {res_div_fx["final"]:,.2f} USD     | {res_div_sma["final"]:,.2f} USD')
        print(f'Total Return (%)        | {res_nvda["return"]:.2f}%            | {res_div_fx["return"]:.2f}%            | {res_div_sma["return"]:.2f}%')
        print(f'Max Drawdown (MDD) (%)  | {res_nvda["mdd"]:.2f}%             | {res_div_fx["mdd"]:.2f}%             | {res_div_sma["mdd"]:.2f}%')
        print('=======================================================================')
