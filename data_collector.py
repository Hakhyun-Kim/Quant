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
    """FinanceDataReader를 통해 코스닥 상장 종목 리스트를 가져옵니다."""
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
    """네이버 금융에서 특정 종목의 분기/연간 재무 데이터를 크롤링합니다."""
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
            
            # 한글 인코딩 변형 방지를 위한 강건한 매칭
            key = None
            if "매출액" in row_name:
                key = "revenue"
            elif "영업이익" in row_name and "영업이익률" not in row_name:
                key = "operating_profit"
            elif "부채비율" in row_name:
                key = "debt_ratio"
            elif "시가배당률" in row_name:
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
        # 조용히 실패 처리
        return None

def collect_all_data(progress_callback=None):
    """코스닥 모든 주가 및 재무제표 데이터를 수집하고 로컬에 캐싱합니다."""
    ensure_data_dir()
    start_time = time.time()
    
    print("1. 코스닥 상장 종목 리스트 수집 중...")
    df_listing = get_kosdaq_listing()
    if df_listing.empty:
        print("상장 종목 리스트를 가져오는데 실패했습니다.")
        return False
        
    # 종목 리스트 저장
    listing_path = os.path.join(DATA_DIR, "kosdaq_listing.csv")
    df_listing.to_csv(listing_path, index=False, encoding="utf-8-sig")
    
    # 2. 코스닥 지수 수집
    print("2. 코스닥 지수 데이터 수집 중...")
    try:
        df_index = fdr.DataReader("KQ11", "2024-01-01")
        df_index = df_index[['Close']].rename(columns={'Close': 'close'})
        index_path = os.path.join(DATA_DIR, "kosdaq_index.csv")
        df_index.to_csv(index_path, encoding="utf-8-sig")
    except Exception as e:
        print(f"코스닥 지수 수집 실패: {e}")
        
    # 3. 개별 종목 재무제표 크롤링 (병렬)
    tickers = df_listing['code'].tolist()
    total_tickers = len(tickers)
    print(f"3. {total_tickers}개 종목 재무 데이터 수집 시작...")
    
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
        
    print(f"재무 데이터 수집 완료 (성공: {len(financials_cache)}/{total_tickers} 종목)")
                
    # 재무 데이터 저장
    financials_path = os.path.join(DATA_DIR, "kosdaq_financials.json")
    with open(financials_path, "w", encoding="utf-8") as f:
        json.dump(financials_cache, f, ensure_ascii=False, indent=4)
        
    # 4. 과거 주가 데이터 수집 (백테스트 가격 시계열 구축)
    # 2년치 가격 데이터
    print("4. 과거 주가 데이터 수집 중...")
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
            
    print(f"주가 수집 완료 (성공: {len(prices_cache)}/{total_tickers} 종목)")
                
    # 주가 데이터 저장
    prices_path = os.path.join(DATA_DIR, "kosdaq_prices.json")
    with open(prices_path, "w", encoding="utf-8") as f:
        json.dump(prices_cache, f, ensure_ascii=False)
        
    elapsed = time.time() - start_time
    print(f"\n데이터 수집 완료! 총 소요시간: {elapsed:.1f}초")
    print(f"수집 성공 종목 수: 재무데이터 {len(financials_cache)}개, 주가데이터 {len(prices_cache)}개")
    return True

def load_cached_data():
    """캐시된 로컬 데이터를 불러옵니다."""
    ensure_data_dir()
    
    listing_path = os.path.join(DATA_DIR, "kosdaq_listing.csv")
    financials_path = os.path.join(DATA_DIR, "kosdaq_financials.json")
    prices_path = os.path.join(DATA_DIR, "kosdaq_prices.json")
    index_path = os.path.join(DATA_DIR, "kosdaq_index.csv")
    
    # 캐시 파일이 존재하는지 검증
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
    # 스크립트 단독 실행 시 데이터 수집 수행
    collect_all_data()
