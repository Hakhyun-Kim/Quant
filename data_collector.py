import os
import json
import time
import requests
import pandas as pd
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor, as_completed, wait
import FinanceDataReader as fdr

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")

def ensure_data_dir():
    if not os.path.exists(DATA_DIR):
        os.makedirs(DATA_DIR)

def get_kosdaq_listing():
    """Fetch the KOSDAQ stock listing using FinanceDataReader."""
    try:
        df = fdr.StockListing("KOSDAQ")
        # 필요한 컬럼만 추출
        df_filtered = df[['Code', 'Name', 'Marcap', 'Close', 'Stocks']]
        df_filtered.columns = ['code', 'name', 'marcap', 'close', 'stocks']
        return df_filtered
    except Exception as e:
        print(f"Error fetching KOSDAQ listing: {e}")
        return pd.DataFrame()

def crawl_financial_data(code):
    """Crawl quarterly/annual financial data for a specific stock ticker from Naver Finance."""
    url = f"https://finance.naver.com/item/main.naver?code={code}"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    }
    
    try:
        res = requests.get(url, headers=headers, timeout=5)
        soup = BeautifulSoup(res.text, "html.parser")
        
        table = soup.find("table", class_="tb_type1 tb_num tb_type1_ifrs")
        if not table:
            return None
            
        thead = table.find("thead")
        tbody = table.find("tbody")
        if not thead or not tbody:
            return None
            
        # 날짜 헤더 추출
        header_rows = thead.find_all("tr")
        dates = []
        if len(header_rows) >= 2:
            for th in header_rows[1].find_all("th"):
                dates.append(th.text.strip())
                
        if not dates:
            return None
            
        # 재무 지표 추출
        financial_data = {}
        for tr in tbody.find_all("tr"):
            th = tr.find("th")
            if not th:
                continue
            row_name = th.text.strip()
            
            # Match Korean row headers from Naver Finance to standardized English keys
            key = None
            if "매출액" in row_name:  # Revenue
                key = "revenue"
            elif "영업이익" in row_name and "영업이익률" not in row_name:  # Operating Profit
                key = "operating_profit"
            elif "부채비율" in row_name:  # Debt Ratio
                key = "debt_ratio"
            elif "시가배당률" in row_name:  # Dividend Yield
                key = "dividend_yield"
                
            if not key:
                continue
                
            values = []
            for td in tr.find_all("td"):
                val_raw = td.text.strip().replace(",", "")
                if val_raw in ("", "-", "N/A", "NaN", "nan"):
                    values.append(None)
                else:
                    try:
                        values.append(float(val_raw))
                    except ValueError:
                        values.append(None)
                        
            financial_data[key] = values
            
        return {
            "dates": dates,
            "data": financial_data
        }
        
    except Exception as e:
        # Silently handle failures
        return None

def collect_all_data(progress_callback=None):
    """Collect and cache daily price and financial statement data for all KOSDAQ listings locally."""
    ensure_data_dir()
    start_time = time.time()
    
    print("1. Collecting KOSDAQ stock listing...")
    df_listing = get_kosdaq_listing()
    if df_listing.empty:
        print("Failed to fetch stock listing.")
        return False
        
    # 종목 리스트 저장
    listing_path = os.path.join(DATA_DIR, "kosdaq_listing.csv")
    df_listing.to_csv(listing_path, index=False, encoding="utf-8-sig")
    
    # 2. Collect KOSDAQ Index
    print("2. Collecting KOSDAQ index data...")
    try:
        df_index = fdr.DataReader("KQ11", "2024-01-01")
        df_index = df_index[['Close']].rename(columns={'Close': 'close'})
        index_path = os.path.join(DATA_DIR, "kosdaq_index.csv")
        df_index.to_csv(index_path, encoding="utf-8-sig")
    except Exception as e:
        print(f"Failed to collect KOSDAQ index: {e}")
        
    # 3. Crawl individual financial statements in parallel
    tickers = df_listing['code'].tolist()
    total_tickers = len(tickers)
    print(f"3. Starting financial data collection for {total_tickers} tickers...")
    
    financials_cache = {}
    
    # 스레드 30개로 병렬 수집
    executor = ThreadPoolExecutor(max_workers=30)
    try:
        future_to_ticker = {executor.submit(crawl_financial_data, t): t for t in tickers}
        # Wait up to 30 seconds for financial statements downloads
        done, not_done = wait(future_to_ticker.keys(), timeout=30)
        
        for future in done:
            try:
                data = future.result()
                if data:
                    ticker = future_to_ticker[future]
                    financials_cache[ticker] = data
            except Exception:
                pass
    finally:
        executor.shutdown(wait=False)
        
    print(f"Financial data collection complete (Success: {len(financials_cache)}/{total_tickers} tickers)")
                
    # 재무 데이터 저장
    financials_path = os.path.join(DATA_DIR, "kosdaq_financials.json")
    with open(financials_path, "w", encoding="utf-8") as f:
        json.dump(financials_cache, f, ensure_ascii=False, indent=4)
        
    # 4. Collect historical price data (building price time series for backtesting)
    # 2 years of price data
    print("4. Collecting historical price data...")
    prices_cache = {}
    completed_prices = 0
    
    def fetch_price(code):
        try:
            df = fdr.DataReader(code, "2024-01-01")
            if not df.empty:
                # Convert index to YYYY-MM-DD string format to support JSON serialization
                df.index = df.index.strftime("%Y-%m-%d")
                return code, df['Close'].to_dict()
        except Exception:
            pass
        return code, None


    executor = ThreadPoolExecutor(max_workers=40)
    try:
        future_to_price = {executor.submit(fetch_price, t): t for t in tickers}
        # Wait up to 45 seconds for all price data downloads
        done, not_done = wait(future_to_price.keys(), timeout=45)
        
        for future in done:
            try:
                code, price_dict = future.result()
                if price_dict:
                    prices_cache[code] = price_dict
            except Exception:
                pass
    finally:
        executor.shutdown(wait=False)
            
    print(f"Price data collection complete (Success: {len(prices_cache)}/{total_tickers} tickers)")
                
    # 주가 데이터 저장
    prices_path = os.path.join(DATA_DIR, "kosdaq_prices.json")
    with open(prices_path, "w", encoding="utf-8") as f:
        json.dump(prices_cache, f, ensure_ascii=False)
        
    elapsed = time.time() - start_time
    print(f"\nData collection complete! Elapsed time: {elapsed:.1f}s")
    print(f"Successfully collected: Financials {len(financials_cache)}, Prices {len(prices_cache)}")
    return True

def load_cached_data():
    """Load cached local data from the file system."""
    ensure_data_dir()
    
    listing_path = os.path.join(DATA_DIR, "kosdaq_listing.csv")
    financials_path = os.path.join(DATA_DIR, "kosdaq_financials.json")
    prices_path = os.path.join(DATA_DIR, "kosdaq_prices.json")
    index_path = os.path.join(DATA_DIR, "kosdaq_index.csv")
    
    # Verify if cache files exist
    if not (os.path.exists(listing_path) and os.path.exists(financials_path) and 
            os.path.exists(prices_path) and os.path.exists(index_path)):
        return None
        
    try:
        df_listing = pd.read_csv(listing_path, dtype={'code': str})
        
        with open(financials_path, "r", encoding="utf-8") as f:
            financials = json.load(f)
            
        with open(prices_path, "r", encoding="utf-8") as f:
            prices = json.load(f)
            
        df_index = pd.read_csv(index_path, index_col=0)
        df_index.index = pd.to_datetime(df_index.index)
        
        return {
            "listing": df_listing,
            "financials": financials,
            "prices": prices,
            "index": df_index
        }
    except Exception as e:
        print(f"Error loading cached data: {e}")
        return None

if __name__ == "__main__":
    # Execute data collection when run as a standalone script
    collect_all_data()
