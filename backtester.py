import os
import json
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import data_collector

def get_recent_quarter(date_str):
    """
    특정 날짜 기준으로 이미 공시가 완료되어 활용할 수 있는 가장 최근 분기를 반환합니다.
    - 1분기 실적(03): 5/15 공시 -> 5/15 ~ 8/14 사이 활용 가능
    - 2분기 실적(06): 8/15 공시 -> 8/15 ~ 11/14 사이 활용 가능
    - 3분기 실적(09): 11/15 공시 -> 11/15 ~ 익년 3/30 사이 활용 가능
    - 4분기 실적(12): 3/31 공시 -> 3/31 ~ 5/14 사이 활용 가능
    """
    dt = pd.to_datetime(date_str)
    year = dt.year
    month = dt.month
    day = dt.day
    
    # 공시일을 고려한 분기 판단
    if (month > 5 or (month == 5 and day >= 15)) and (month < 8 or (month == 8 and day < 15)):
        # 5/15 ~ 8/14 -> 1분기 (03)
        return f"{year}.03"
    elif (month > 8 or (month == 8 and day >= 15)) and (month < 11 or (month == 11 and day < 15)):
        # 8/15 ~ 11/14 -> 2분기 (06)
        return f"{year}.06"
    elif (month > 11 or (month == 11 and day >= 15)) or (month < 3 or (month == 3 and day < 31)):
        # 11/15 ~ 3/30 -> 3분기 (09)
        # 만약 1, 2월 혹은 3월 30일 이전이면 전년도 3분기 실적 적용
        ref_year = year if month > 11 else year - 1
        return f"{ref_year}.09"
    else:
        # 3/31 ~ 5/14 -> 4분기 (12)
        # 3월 31일 이후부터 5월 14일 이전에는 전년도 4분기 실적 적용
        return f"{year - 1}.12"

def get_previous_quarters(quarter_str, n=3):
    """특정 분기 기준으로 이전 N개의 분기 리스트를 구합니다 (예: '2024.03' -> ['2023.09', '2023.12', '2024.03'])"""
    year, q = map(int, quarter_str.split('.'))
    
    quarters = []
    for _ in range(n):
        quarters.append(f"{year}.{q:02d}")
        # 이전 분기로 이동
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
                  min_marcap=0, max_marcap=float('inf'), min_div_yield=1.0):
    """
    특정 날짜 기준으로 조건에 맞는 종목들을 필터링합니다.
    - min_marcap, max_marcap: 원 단위 시가총액 필터 범위
    - min_div_yield: 최소 배당수익률 (%)
    """
    listing = data["listing"]
    financials = data["financials"]
    prices = data["prices"]
    
    # 1. 대상 날짜에 가격 데이터가 존재하는 종목들만 선별 (거래정지 등 제외)
    date_str_formatted = pd.to_datetime(date_str).strftime("%Y-%m-%d")
    
    active_stocks = []
    for code in listing['code'].tolist():
        if code in prices and date_str_formatted in prices[code]:
            active_stocks.append(code)
            
    # 현재 날짜 기준으로 이용 가능한 재무 정보 식별
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
            
        # 1. 부채비율 검사 (최근 분기)
        try:
            q_idx = dates.index(recent_q)
            debt = fin_data["debt_ratio"][q_idx]
            if debt is None or debt >= debt_threshold:
                continue
        except (ValueError, IndexError):
            # 최근 분기 데이터가 존재하지 않는 경우 제외
            continue
            
        # 2. 최근 N개 분기 영업이익 연속 흑자 여부 검사
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
            
        # 3. PSR 계산
        # 매출액 구하기: 최근 분기를 포함해 직전 4분기 매출액의 합산 (TTM)
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
                
        # 만약 분기 매출 데이터가 누락되었을 시, 연간 매출 데이터를 보조로 사용
        if not revenue_ok or ttm_revenue == 0:
            # 최근 연간 매출액 사용 시도
            recent_year = recent_q.split('.')[0]
            annual_q = f"{recent_year}.12"
            try:
                aq_idx = dates.index(annual_q)
                rev = fin_data["revenue"][aq_idx]
                if rev is not None:
                    ttm_revenue = rev
                    revenue_ok = True
            except (ValueError, IndexError):
                # 전년도 연간 매출 사용 시도
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
            
        # 시가총액 계산: 해당 날짜의 종가 * 상장주식수
        close_price = prices[code][date_str_formatted]
        stocks_count = listing[listing['code'] == code]['stocks'].values[0]
        market_cap = close_price * stocks_count
        
        # 시가총액 필터링 (원 단위 비교)
        if not (min_marcap <= market_cap <= max_marcap):
            continue
            
        # 배당수익률 추출: 결산(연간) 기준 가장 최근 배당수익률(dividend_yield)을 매칭합니다.
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
                # 전년도 결산 데이터 사용 시도
                prev_annual_q = f"{int(recent_year)-1}.12"
                try:
                    paq_idx = dates.index(prev_annual_q)
                    div_val = fin_data["dividend_yield"][paq_idx]
                    if div_val is not None:
                        div_yield = div_val
                except (ValueError, IndexError):
                    pass
                    
        # 최소 배당수익률 필터링
        if div_yield < min_div_yield:
            continue
            
        # PSR = 시가총액 / (매출액 * 1억 - 네이버 재무제표 단위는 대개 억 원이므로 보정)
        # 네이버 금융의 매출액 표는 기본이 억 원 단위입니다.
        # 시가총액(원) / (매출액(억원) * 10^8)
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
                 min_marcap=0, max_marcap=float('inf'), min_div_yield=1.0, sort_by="psr"):
    """
    퀀트 투자 전략 백테스트를 수행합니다.
    - rebalance_freq: "Q" (분기별), "M" (월별), "H" (반기별), "Y" (연별)
    - min_marcap, max_marcap: 원 단위 시가총액 필터 범위
    - min_div_yield: 최소 배당수익률 (%)
    - sort_by: "psr" (PSR 오름차순), "marcap_asc" (시총 오름차순), "marcap_desc" (시총 내림차순), "div_desc" (배당률 내림차순)
    """
    prices = data["prices"]
    df_index = data["index"]
    
    # 백테스트 기간 내에 존재하는 모든 실제 영업일 날짜 목록 구하기
    # 코스닥 지수의 인덱스 날짜를 사용합니다.
    all_dates = df_index.loc[start_date_str:end_date_str].index.strftime("%Y-%m-%d").tolist()
    
    if not all_dates:
        return None
        
    # 리밸런싱 날짜 리스트 결정
    rebalance_dates = []
    
    # 시작 날짜는 무조건 리밸런싱 수행
    rebalance_dates.append(all_dates[0])
    
    # 주기별 리밸런싱 날짜 식별
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
            
        # 해당 날짜에 가장 가까운 실제 영업일 찾기
        target_str = temp_dt.strftime("%Y-%m-%d")
        if target_str in all_dates:
            rebalance_dates.append(target_str)
        else:
            # 영업일이 아니면 이후 날짜 중 가장 가까운 영업일 선택
            future_dates = [d for d in all_dates if d >= target_str]
            if future_dates:
                rebalance_dates.append(future_dates[0])
                
    # 중복 제거 및 정렬
    rebalance_dates = sorted(list(set(rebalance_dates)))
    
    # 시뮬레이션 변수
    cash = initial_capital
    portfolio = {}  # {code: {"shares": n, "buy_price": p}}
    portfolio_value_history = []
    
    # 리밸런싱 주기별 매매 기록 저장
    trade_logs = []
    
    # 일별 시뮬레이션
    current_portfolio_codes = []
    
    for date_idx, today in enumerate(all_dates):
        # 1. 리밸런싱 데이인 경우 리밸런싱 수행
        if today in rebalance_dates:
            # 신규 종목 스크리닝을 먼저 시도하여 살 수 있는 우량 저평가주가 있는지 파악합니다.
            df_screened = screen_stocks(
                today, data, 
                psr_threshold=psr_threshold, 
                debt_threshold=debt_threshold,
                consecutive_profitable_quarters=consecutive_profitable_quarters,
                min_marcap=min_marcap,
                max_marcap=max_marcap,
                min_div_yield=min_div_yield
            )
            
            # 조건 만족하는 신규 종목이 1개라도 존재하는 경우에만 포트폴리오 리밸런싱(교체)을 진행합니다.
            # 만약 조건에 맞는 종목이 0개라면 기존 포트폴리오를 매도하지 않고 그대로 유지(Hold)합니다.
            if not df_screened.empty:
                # 기존 포트폴리오 전량 매도
                if portfolio:
                    sell_log = []
                    for code, info in list(portfolio.items()):
                        # 오늘 종가 확인
                        if today in prices[code]:
                            today_close = prices[code][today]
                        else:
                            # 오늘 가격이 없으면 직전 가치 유지
                            today_close = info["buy_price"]
                            
                        sell_value = info["shares"] * today_close
                        # 수수료 및 거래세 적용 (매도 시 0.2% 가정)
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
                
                # 지정 정렬 기준에 맞춰 상위 K개 선택
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
                
                # 가용 현금을 균등 배분하여 매수
                if selected_codes:
                    allocation = cash / len(selected_codes)
                    buy_log = []
                    for code in selected_codes:
                        row = df_selected[df_selected['code'] == code].iloc[0]
                        price = row['close']
                        # 매수 수수료 반영 (0.015% 가정)
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
            
        # 2. 일별 포트폴리오 가치 계산
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
    
    # 벤치마크 (코스닥 지수) 수익률 병합
    df_index_subset = df_index.loc[start_date_str:end_date_str].copy()
    
    # 누적 수익률 계산
    df_history["portfolio_return"] = (df_history["portfolio_value"] / initial_capital - 1) * 100
    
    first_index_val = df_index_subset.iloc[0]['close']
    df_index_subset["index_return"] = (df_index_subset["close"] / first_index_val - 1) * 100
    
    df_merged = df_history.join(df_index_subset[['close', 'index_return']], how="left")
    df_merged.rename(columns={'close': 'index_close'}, inplace=True)
    
    # 성과 지표 산출
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
    # 일별 평균 수익률 연율화 / 변동성 연율화
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
    # 백테스터 단독 작동 확인용
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

def get_available_backtest_range(data):
    """
    캐시된 재무 데이터를 분석하여 백테스트가 가능한 안전한 최초 시작일과 최신 종료일을 구합니다.
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
        
    # 가용한 가장 과거 분기를 기준으로 공시일 산정
    first_q = valid_qs[0]
    year_str, q_str = first_q.split('.')
    year = int(year_str)
    q = int(q_str)
    
    # 1분기(3): 5/15 공시, 2분기(6): 8/15 공시, 3분기(9): 11/15 공시, 4분기(12): 익년 3/31 공시
    if q == 3:
        safe_start_date = datetime(year, 5, 16)
    elif q == 6:
        safe_start_date = datetime(year, 8, 16)
    elif q == 9:
        safe_start_date = datetime(year, 11, 16)
    else:
        safe_start_date = datetime(year + 1, 4, 1)
        
    index_dates = data["index"].index
    latest_date = index_dates[-1].to_pydatetime()
    
    return safe_start_date, latest_date
