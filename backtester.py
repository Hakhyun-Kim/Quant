import os
import json
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import data_collector

def get_recent_quarter(date_str):
    """
    Returns the most recent quarterly financial report available (already public) as of the given date.
    - Q1 earnings (03): Published May 15 -> Available May 15 ~ Aug 14
    - Q2 earnings (06): Published Aug 15 -> Available Aug 15 ~ Nov 14
    - Q3 earnings (09): Published Nov 15 -> Available Nov 15 ~ Mar 30 of the following year
    - Q4 earnings (12): Published Mar 31 -> Available Mar 31 ~ May 14 of the following year
    """
    dt = pd.to_datetime(date_str)
    year = dt.year
    month = dt.month
    day = dt.day
    
    # Determine the quarterly report based on publication schedules
    if (month > 5 or (month == 5 and day >= 15)) and (month < 8 or (month == 8 and day < 15)):
        # 5/15 ~ 8/14 -> 1분기 (03)
        return f"{year}.03"
    elif (month > 8 or (month == 8 and day >= 15)) and (month < 11 or (month == 11 and day < 15)):
        # 8/15 ~ 11/14 -> 2분기 (06)
        return f"{year}.06"
    elif (month > 11 or (month == 11 and day >= 15)) or (month < 3 or (month == 3 and day < 31)):
        # 11/15 ~ 3/30 -> 3분기 (09)
        # If before March 31, apply Q3 performance of the previous year
        ref_year = year if month > 11 else year - 1
        return f"{ref_year}.09"
    else:
        # March 31 ~ May 14 -> Q4 (12)
        # Apply Q4 performance of the previous year
        return f"{year - 1}.12"

def get_previous_quarters(quarter_str, n=3):
    """Returns a list of N consecutive quarters ending at the given quarter (e.g., '2024.03' -> ['2023.09', '2023.12', '2024.03'])"""
    year, q = map(int, quarter_str.split('.'))
    
    quarters = []
    for _ in range(n):
        quarters.append(f"{year}.{q:02d}")
        # Shift to the previous quarter
        if q == 3:
            q = 12
            year -= 1
        elif q == 6:
            q = 3
        elif q == 9:
            q = 6
        elif q == 12:
            q = 9
            
    return list(reversed(quarters))

def screen_stocks(date_str, data, psr_threshold=0.8, debt_threshold=100.0, consecutive_profitable_quarters=3,
                  min_marcap=0, max_marcap=float('inf'), min_div_yield=1.0, target_market="Both"):
    """
    Filters stocks based on the specified financial criteria as of a given date.
    - min_marcap, max_marcap: Market cap threshold range in KRW
    - min_div_yield: Minimum dividend yield (%)
    - target_market: Target market classification ('KOSPI', 'KOSDAQ', or 'Both')
    """
    listing = data["listing"]
    financials = data["financials"]
    prices = data["prices"]
    
    # Filter listing by target market (KOSPI, KOSDAQ, or Both)
    if target_market == "KOSPI":
        listing = listing[listing['market'] == 'KOSPI']
    elif target_market == "KOSDAQ":
        listing = listing[listing['market'] == 'KOSDAQ']
    
    # 1. Select stocks with price data on the target date (excluding suspended trading, etc.)
    date_str_formatted = pd.to_datetime(date_str).strftime("%Y-%m-%d")
    
    active_stocks = []
    for code in listing['code'].tolist():
        if code in prices and date_str_formatted in prices[code]:
            active_stocks.append(code)
            
    # Identify available financial information based on the current date
    recent_q = get_recent_quarter(date_str)
    prev_qs = get_previous_quarters(recent_q, consecutive_profitable_quarters)
    
    screened_results = []
    
    for code in active_stocks:
        if code not in financials:
            continue
            
        fin = financials[code]
        dates = fin["dates"]
        fin_data = fin["data"]
        
        # 필요한 항목들이 모두 존재하는지 검증
        if not ("revenue" in fin_data and "operating_profit" in fin_data and "debt_ratio" in fin_data):
            continue
            
        # 1. Check debt ratio (most recent quarter)
        try:
            q_idx = dates.index(recent_q)
            debt = fin_data["debt_ratio"][q_idx]
            if debt is None or debt >= debt_threshold:
                continue
        except (ValueError, IndexError):
            # Exclude if recent quarter data is not available
            continue
            
        # 2. Check for consecutive profitable quarters
        profitable = True
        for pq in prev_qs:
            try:
                pq_idx = dates.index(pq)
                op = fin_data["operating_profit"][pq_idx]
                if op is None or op <= 0:
                    profitable = False
                    break
            except (ValueError, IndexError):
                profitable = False
                break
                
        if not profitable:
            continue
            
        # 3. Calculate PSR
        # Get TTM Revenue: Sum of revenue over the last 4 quarters including the recent quarter
        ttm_revenue = 0
        revenue_ok = True
        revenue_qs = get_previous_quarters(recent_q, 4)
        
        for rq in revenue_qs:
            try:
                rq_idx = dates.index(rq)
                rev = fin_data["revenue"][rq_idx]
                if rev is not None:
                    ttm_revenue += rev
                else:
                    revenue_ok = False
                    break
            except (ValueError, IndexError):
                revenue_ok = False
                break
                
        # Fallback to annual revenue if quarterly data is missing or incomplete
        if not revenue_ok or ttm_revenue == 0:
            # Try using recent annual revenue
            recent_year = recent_q.split('.')[0]
            annual_q = f"{recent_year}.12"
            try:
                aq_idx = dates.index(annual_q)
                rev = fin_data["revenue"][aq_idx]
                if rev is not None:
                    ttm_revenue = rev
                    revenue_ok = True
            except (ValueError, IndexError):
                # Try using the previous year's annual revenue
                prev_year = str(int(recent_year) - 1)
                prev_annual_q = f"{prev_year}.12"
                try:
                    paq_idx = dates.index(prev_annual_q)
                    rev = fin_data["revenue"][paq_idx]
                    if rev is not None:
                        ttm_revenue = rev
                        revenue_ok = True
                except (ValueError, IndexError):
                    pass
                    
        if not revenue_ok or ttm_revenue <= 0:
            continue
            
        # Calculate market cap: Close price * total shares
        close_price = prices[code][date_str_formatted]
        stocks_count = listing[listing['code'] == code]['stocks'].values[0]
        market_cap = close_price * stocks_count
        
        # Filter by market cap (KRW)
        if not (min_marcap <= market_cap <= max_marcap):
            continue
            
        # Extract dividend yield: Match the most recent annual fiscal dividend yield
        div_yield = 0.0
        if "dividend_yield" in fin_data:
            recent_year = recent_q.split('.')[0]
            annual_q = f"{recent_year}.12"
            
            try:
                aq_idx = dates.index(annual_q)
                div_val = fin_data["dividend_yield"][aq_idx]
                if div_val is not None:
                    div_yield = div_val
            except (ValueError, IndexError):
                # Try using previous fiscal year's annual dividend yield
                prev_annual_q = f"{int(recent_year)-1}.12"
                try:
                    paq_idx = dates.index(prev_annual_q)
                    div_val = fin_data["dividend_yield"][paq_idx]
                    if div_val is not None:
                        div_yield = div_val
                except (ValueError, IndexError):
                    pass
                    
        # Filter by minimum dividend yield
        if div_yield < min_div_yield:
            continue
            
        # PSR = Market Cap / (Revenue * 10^8) - Naver Finance revenue is usually in 100M KRW
        # Convert revenue to KRW and calculate PSR
        revenue_won = ttm_revenue * 100000000
        psr = market_cap / revenue_won
        
        if psr < psr_threshold:
            screened_results.append({
                "code": code,
                "name": listing[listing['code'] == code]['name'].values[0],
                "close": close_price,
                "marcap": market_cap,
                "revenue_ttm": ttm_revenue,
                "psr": psr,
                "debt_ratio": debt,
                "div_yield": div_yield
            })
            
    return pd.DataFrame(screened_results)

def run_backtest(data, start_date_str, end_date_str, psr_threshold=0.8, debt_threshold=100.0, 
                 consecutive_profitable_quarters=3, portfolio_size=10, rebalance_freq="Q", initial_capital=100000000,
                 min_marcap=0, max_marcap=float('inf'), min_div_yield=1.0, sort_by="psr", target_market="Both"):
    """
    Simulates a quantitative investment strategy backtest.
    - rebalance_freq: "Q" (Quarterly), "M" (Monthly), "H" (Semi-Annually), "Y" (Annually)
    - min_marcap, max_marcap: Market cap threshold range in KRW
    - min_div_yield: Minimum dividend yield (%)
    - sort_by: "psr" (PSR Ascending), "marcap_asc" (Small-Cap Ascending), "marcap_desc" (Large-Cap Descending), "div_desc" (Dividend yield Descending)
    - target_market: "Both", "KOSPI", or "KOSDAQ"
    """
    prices = data["prices"]
    
    # Choose benchmark index based on target market
    if target_market == "KOSDAQ":
        df_index = data["kosdaq_index"]
    else:
        df_index = data["kospi_index"]
    
    # Retrieve list of actual business trading days within backtest period
    # Use index dates as target days
    all_dates = df_index.loc[start_date_str:end_date_str].index.strftime("%Y-%m-%d").tolist()
    
    if not all_dates:
        return None
        
    # Define rebalancing schedule dates
    rebalance_dates = []
    
    # Force rebalancing on the initial day
    rebalance_dates.append(all_dates[0])
    
    # Identify periodic rebalancing dates
    current_dt = pd.to_datetime(all_dates[0])
    end_dt = pd.to_datetime(all_dates[-1])
    
    temp_dt = current_dt
    while temp_dt < end_dt:
        if rebalance_freq == "Q":
            temp_dt += pd.DateOffset(months=3)
        elif rebalance_freq == "M":
            temp_dt += pd.DateOffset(months=1)
        elif rebalance_freq == "H":
            temp_dt += pd.DateOffset(months=6)
        elif rebalance_freq == "Y":
            temp_dt += pd.DateOffset(years=1)
        else:
            break
            
        if temp_dt >= end_dt:
            break
            
        # Find the closest actual trading day to the target date
        target_str = temp_dt.strftime("%Y-%m-%d")
        if target_str in all_dates:
            rebalance_dates.append(target_str)
        else:
            # If not a trading day, find the next closest trading day
            future_dates = [d for d in all_dates if d >= target_str]
            if future_dates:
                rebalance_dates.append(future_dates[0])
                
    # Remove duplicates and sort
    rebalance_dates = sorted(list(set(rebalance_dates)))
    
    # Simulation parameters
    cash = initial_capital
    portfolio = {}  # {code: {"shares": n, "buy_price": p}}
    portfolio_value_history = []
    
    # Store trade logs for each rebalancing period
    trade_logs = []
    
    # Daily portfolio status simulation variables
    current_portfolio_codes = []
    
    for date_idx, today in enumerate(all_dates):
        # 1. Rebalance on scheduled rebalancing days
        if today in rebalance_dates:
            # Perform screening first to see if any stocks meet the criteria
            df_screened = screen_stocks(
                today, data, 
                psr_threshold=psr_threshold, 
                debt_threshold=debt_threshold,
                consecutive_profitable_quarters=consecutive_profitable_quarters,
                min_marcap=min_marcap,
                max_marcap=max_marcap,
                min_div_yield=min_div_yield,
                target_market=target_market
            )
            
            # Only rebalance if at least one stock satisfies the criteria.
            # If no stocks qualify, hold the existing portfolio instead of liquidating to cash.
            if not df_screened.empty:
                # Sell existing holdings
                if portfolio:
                    sell_log = []
                    for code, info in list(portfolio.items()):
                        # Check current close price
                        if today in prices[code]:
                            today_close = prices[code][today]
                        else:
                            # Use last known price if trading is inactive
                            today_close = info["buy_price"]
                            
                        sell_value = info["shares"] * today_close
                        # Deduct transaction fees and taxes (0.2%)
                        sell_value_after_tax = sell_value * 0.998
                        cash += sell_value_after_tax
                        
                        sell_log.append({
                            "date": today,
                            "type": "SELL",
                            "code": code,
                            "name": data["listing"][data["listing"]['code'] == code]['name'].values[0],
                            "shares": info["shares"],
                            "price": today_close,
                            "value": sell_value_after_tax
                        })
                    trade_logs.extend(sell_log)
                    portfolio.clear()
                
                # Select top K stocks based on sort selection
                if sort_by == "psr":
                    df_selected = df_screened.sort_values(by="psr").head(portfolio_size)
                elif sort_by == "marcap_asc":
                    df_selected = df_screened.sort_values(by="marcap").head(portfolio_size)
                elif sort_by == "marcap_desc":
                    df_selected = df_screened.sort_values(by="marcap", ascending=False).head(portfolio_size)
                elif sort_by == "div_desc":
                    df_selected = df_screened.sort_values(by="div_yield", ascending=False).head(portfolio_size)
                else:
                    df_selected = df_screened.sort_values(by="psr").head(portfolio_size)
                    
                selected_codes = df_selected['code'].tolist()
                
                # Allocate available cash equally to purchase new candidates
                if selected_codes:
                    allocation = cash / len(selected_codes)
                    buy_log = []
                    for code in selected_codes:
                        row = df_selected[df_selected['code'] == code].iloc[0]
                        price = row['close']
                        # Deduct buying commission (0.015%)
                        allocation_net = allocation / 1.00015
                        shares = int(allocation_net / price)
                        
                        if shares > 0:
                            actual_cost = shares * price * 1.00015
                            cash -= actual_cost
                            portfolio[code] = {
                                "shares": shares,
                                "buy_price": price,
                                "name": row['name']
                            }
                            
                            buy_log.append({
                                "date": today,
                                "type": "BUY",
                                "code": code,
                                "name": row['name'],
                                "shares": shares,
                                "price": price,
                                "value": actual_cost
                            })
                    trade_logs.extend(buy_log)
                    
            current_portfolio_codes = list(portfolio.keys())
            
        # 2. Calculate daily portfolio valuation
        portfolio_stock_value = 0
        for code, info in portfolio.items():
            if today in prices[code]:
                current_price = prices[code][today]
            else:
                current_price = info["buy_price"]
            portfolio_stock_value += info["shares"] * current_price
            
        total_value = cash + portfolio_stock_value
        portfolio_value_history.append({
            "date": today,
            "portfolio_value": total_value,
            "cash": cash,
            "stock_value": portfolio_stock_value,
            "holdings": ", ".join([info["name"] for info in portfolio.values()])
        })
        
    df_history = pd.DataFrame(portfolio_value_history)
    df_history["date"] = pd.to_datetime(df_history["date"])
    df_history.set_index("date", inplace=True)
    
    # Merge Benchmark (KOSDAQ Index) returns
    df_index_subset = df_index.loc[start_date_str:end_date_str].copy()
    
    # Calculate cumulative returns
    df_history["portfolio_return"] = (df_history["portfolio_value"] / initial_capital - 1) * 100
    
    first_index_val = df_index_subset.iloc[0]['close']
    df_index_subset["index_return"] = (df_index_subset["close"] / first_index_val - 1) * 100
    
    df_merged = df_history.join(df_index_subset[['close', 'index_return']], how="left")
    df_merged.rename(columns={'close': 'index_close'}, inplace=True)
    
    # Calculate performance metrics
    total_days = (df_merged.index[-1] - df_merged.index[0]).days
    final_value = df_merged["portfolio_value"].iloc[-1]
    
    # CAGR
    cagr = ((final_value / initial_capital) ** (365.0 / max(1, total_days)) - 1) * 100
    
    # MDD
    roll_max = df_merged["portfolio_value"].cummax()
    drawdown = (df_merged["portfolio_value"] - roll_max) / roll_max
    mdd = drawdown.min() * 100
    
    # Sharpe Ratio
    df_merged["portfolio_daily_ret"] = df_merged["portfolio_value"].pct_change()
    daily_vol = df_merged["portfolio_daily_ret"].std()
    # Annualized return and volatility
    mean_daily_ret = df_merged["portfolio_daily_ret"].mean()
    sharpe = (mean_daily_ret / daily_vol * np.sqrt(252)) if daily_vol > 0 else 0
    
    # Benchmark CAGR & MDD
    index_final = df_index_subset["close"].iloc[-1]
    index_initial = df_index_subset["close"].iloc[0]
    index_cagr = ((index_final / index_initial) ** (365.0 / max(1, total_days)) - 1) * 100
    
    index_roll_max = df_index_subset["close"].cummax()
    index_drawdown = (df_index_subset["close"] - index_roll_max) / index_roll_max
    index_mdd = index_drawdown.min() * 100
    
    metrics = {
        "initial_capital": initial_capital,
        "final_value": final_value,
        "total_return": df_merged["portfolio_return"].iloc[-1],
        "cagr": cagr,
        "mdd": mdd,
        "sharpe": sharpe,
        "index_total_return": df_index_subset["index_return"].iloc[-1],
        "index_cagr": index_cagr,
        "index_mdd": index_mdd,
        "rebalance_count": len(rebalance_dates),
        "days": total_days
    }
    
    return df_merged, metrics, pd.DataFrame(trade_logs)

if __name__ == "__main__":
    # Self-diagnostic test execution
    print("Loading cache to test backtester...")
    data = data_collector.load_cached_data()
    if data:
        print("Data loaded. Running a test screener...")
        df_screen = screen_stocks("2025-05-30", data, psr_threshold=0.8, debt_threshold=100.0)
        print(f"Screened {len(df_screen)} stocks. Sample:")
        print(df_screen.head(5))
        
        print("\nRunning a sample backtest...")
        result = run_backtest(data, "2024-05-31", "2026-06-23")
        if result:
            df_hist, metrics, trades = result
            print("\nBacktest metrics:")
            for k, v in metrics.items():
                print(f"  {k}: {v}")
    else:
        print("No cache data found. Please run data_collector.py first.")

def get_available_backtest_range(data, target_market="Both"):
    """
    Analyzes cached financial data to calculate the safe start and end dates for the backtest.
    """
    financials = data.get("financials", {})
    if not financials:
        return None, None
        
    all_quarters = set()
    for code, fin in financials.items():
        dates = fin.get("dates", [])
        for d in dates:
            if d and not d.endswith("(E)") and "." in d:
                all_quarters.add(d)
                
    valid_qs = sorted(list(all_quarters))
    if not valid_qs:
        return None, None
        
    # Determine publication date of the earliest available quarter
    first_q = valid_qs[0]
    year_str, q_str = first_q.split('.')
    year = int(year_str)
    q = int(q_str)
    
    # Q1(3): May 15, Q2(6): Aug 15, Q3(9): Nov 15, Q4(12): Mar 31 of next year
    if q == 3:
        safe_start_date = datetime(year, 5, 16)
    elif q == 6:
        safe_start_date = datetime(year, 8, 16)
    elif q == 9:
        safe_start_date = datetime(year, 11, 16)
    else:
        safe_start_date = datetime(year + 1, 4, 1)
        
    # Choose benchmark index based on target market
    if target_market == "KOSDAQ":
        index_dates = data["kosdaq_index"].index
    else:
        index_dates = data["kospi_index"].index
        
    latest_date = index_dates[-1].to_pydatetime()
    
    return safe_start_date, latest_date
