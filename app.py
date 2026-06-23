import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from datetime import datetime, timedelta
import os
import sys

# Import local modules
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
import data_collector
import backtester

# Page Setting (Wide layout and title)
st.set_page_config(
    page_title="KOSDAQ Quant Screener & Backtester",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for rich aesthetics and modern dark/light themes
st.markdown("""
<style>
    /* Premium visual styling */
    .main-header {
        font-family: 'Inter', sans-serif;
        background: linear-gradient(135deg, #1e3c72 0%, #2a5298 100%);
        padding: 24px;
        border-radius: 12px;
        color: white;
        margin-bottom: 25px;
        box-shadow: 0 4px 15px rgba(0,0,0,0.1);
    }
    .metric-card {
        background-color: #f8f9fa;
        padding: 20px;
        border-radius: 10px;
        border-left: 5px solid #2a5298;
        box-shadow: 0 2px 8px rgba(0,0,0,0.05);
        margin-bottom: 15px;
    }
    html[data-theme="dark"] .metric-card {
        background-color: #1e1e1e;
        border-left: 5px solid #4a90e2;
        color: #ffffff;
    }
    .metric-title {
        font-size: 0.9rem;
        color: #6c757d;
        margin-bottom: 5px;
        font-weight: 600;
    }
    .metric-value {
        font-size: 1.8rem;
        font-weight: 700;
        color: #212529;
    }
    html[data-theme="dark"] .metric-value {
        color: #f8f9fa;
    }
    .metric-delta {
        font-size: 0.85rem;
        font-weight: 600;
        margin-top: 5px;
    }
    .delta-plus { color: #28a745; }
    .delta-minus { color: #dc3545; }
</style>
""", unsafe_allow_html=True)

# Main Title Header
st.markdown("""
<div class="main-header">
    <h1 style="margin:0; font-size:2.2rem; font-weight:700;">KOSDAQ Quant Backtester & Screener</h1>
    <p style="margin:5px 0 0 0; opacity:0.85; font-size:1.0rem;">
        사용자 정의 재무 필터 기반 코스닥 종목 스크리닝 및 과거 성과 시뮬레이터
    </p>
</div>
""", unsafe_allow_html=True)

# Try to load cached data
cached_data = data_collector.load_cached_data()

# ----------------- SIDEBAR PARAMETERS -----------------
st.sidebar.header("⚙️ 전략 및 백테스트 설정")

# 1. Strategy Parameters
st.sidebar.subheader("🎯 스크리닝 필터 조건")
psr_threshold = st.sidebar.slider(
    "주가매출비율 (PSR) 상한선",
    min_value=0.1, max_value=2.0, value=0.8, step=0.05,
    help="PSR = 시가총액 / 최근 4분기 매출액 합계. 낮을수록 저평가 상태입니다."
)

debt_threshold = st.sidebar.slider(
    "부채비율 상한선 (%)",
    min_value=30.0, max_value=300.0, value=100.0, step=5.0,
    help="부채비율 = 부채총계 / 자본총계 * 100. 재무 안전성 필터입니다."
)

consecutive_profitable_quarters = st.sidebar.number_input(
    "영업이익 연속 흑자 분기 수",
    min_value=1, max_value=6, value=3, step=1,
    help="지정된 분기 연속으로 영업이익이 흑자(>0)를 달성한 기업만 선별합니다."
)

# 2. Backtest Settings
st.sidebar.subheader("📈 백테스트 조건")
rebalance_freq = st.sidebar.selectbox(
    "포트폴리오 리밸런싱 주기",
    options=["Q", "M", "H", "Y"],
    format_func=lambda x: {"Q": "매 분기별 (Quarterly)", "M": "매 월별 (Monthly)", "H": "매 반기별 (Semi-Annually)", "Y": "매 년별 (Annually)"}[x]
)

portfolio_size = st.sidebar.slider(
    "포트폴리오 편입 종목 수",
    min_value=3, max_value=30, value=10, step=1,
    help="필터 조건에 부합하는 종목 중 PSR이 가장 낮은 순으로 몇 개 종목을 매수할지 결정합니다."
)

initial_capital = st.sidebar.number_input(
    "초기 투자 원금 (원)",
    min_value=1000000, max_value=10000000000, value=100000000, step=10000000,
    format="%d"
)

# Default Backtest Dates (within 2 years roughly)
default_start = datetime(2024, 5, 31)
default_end = datetime(2026, 6, 23)

start_date = st.sidebar.date_input("백테스트 시작일", default_start)
end_date = st.sidebar.date_input("백테스트 종료일", default_end)

# Validation check for dates
if start_date >= end_date:
    st.sidebar.error("시작일은 종료일보다 이전이어야 합니다.")


# ----------------- TABS CREATION -----------------
tab1, tab2, tab3 = st.tabs(["📊 실시간 스크리너", "📈 백테스트 성과분석", "⚙️ 데이터 캐시 관리"])

# If data is not cached, force user to download first
if cached_data is None:
    with tab1:
        st.warning("⚠️ 로컬 캐시에 저장된 주가 및 재무제표 데이터가 없습니다. 먼저 **데이터 캐시 관리** 탭에서 데이터를 수집해 주세요.")
    with tab2:
        st.warning("⚠️ 백테스트를 실행하려면 먼저 **데이터 캐시 관리** 탭에서 데이터를 수집해 주세요.")
else:
    # ----------------- TAB 1: SCREENER -----------------
    with tab1:
        st.subheader("🔍 현재 조건 만족 코스닥 종목 리스트")
        st.write("사이드바에 정의된 필터를 적용하여 현재 가장 최근 분기 실적 기준으로 선별된 기업들입니다.")
        
        # Today or latest business day available in prices
        latest_date_str = cached_data["index"].index[-1].strftime("%Y-%m-%d")
        
        # Run Screening
        df_screened = backtester.screen_stocks(
            latest_date_str, cached_data,
            psr_threshold=psr_threshold,
            debt_threshold=debt_threshold,
            consecutive_profitable_quarters=consecutive_profitable_quarters
        )
        
        if df_screened.empty:
            st.info("설정한 필터 조건에 부합하는 종목이 코스닥 시장에 없습니다. 조건을 완화해 보세요.")
        else:
            # Metrics Summary Row
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.markdown(f"""
                <div class="metric-card">
                    <div class="metric-title">선별 종목 수</div>
                    <div class="metric-value">{len(df_screened)}개</div>
                </div>
                """, unsafe_allow_html=True)
            with col2:
                st.markdown(f"""
                <div class="metric-card">
                    <div class="metric-title">선별 종목 평균 PSR</div>
                    <div class="metric-value">{df_screened['psr'].mean():.3f}</div>
                </div>
                """, unsafe_allow_html=True)
            with col3:
                st.markdown(f"""
                <div class="metric-card">
                    <div class="metric-title">선별 종목 평균 부채비율</div>
                    <div class="metric-value">{df_screened['debt_ratio'].mean():.1f}%</div>
                </div>
                """, unsafe_allow_html=True)
            with col4:
                st.markdown(f"""
                <div class="metric-card">
                    <div class="metric-title">기준 데이터 일시</div>
                    <div class="metric-value">{latest_date_str}</div>
                </div>
                """, unsafe_allow_html=True)
                
            # Table visualization
            df_display = df_screened.copy()
            # Clean formats
            df_display['close'] = df_display['close'].map(lambda x: f"{int(x):,}원")
            df_display['marcap'] = df_display['marcap'].map(lambda x: f"{int(x/100000000):,}억원")
            df_display['revenue_ttm'] = df_display['revenue_ttm'].map(lambda x: f"{int(x):,}억원")
            df_display['psr'] = df_display['psr'].map(lambda x: f"{x:.3f}")
            df_display['debt_ratio'] = df_display['debt_ratio'].map(lambda x: f"{x:.1f}%")
            
            df_display.columns = ['종목코드', '종목명', '현재 주가', '시가총액', '최근 4분기 매출합계', '주가매출비율 (PSR)', '부채비율']
            
            st.dataframe(df_display, use_container_width=True, hide_index=True)
            
            # Export CSV
            csv_data = df_screened.to_csv(index=False, encoding="utf-8-sig")
            st.download_button(
                label="📥 선별 종목 리스트 다운로드 (CSV)",
                data=csv_data,
                file_name=f"kosdaq_screener_{latest_date_str}.csv",
                mime="text/csv"
            )
            
            # Show top portfolio candidates
            st.subheader(f"💡 조건 부합 종목 (PSR 오름차순 상위 {portfolio_size}선)")
            df_portfolio_suggest = df_screened.sort_values(by="psr").head(portfolio_size)
            cols = st.columns(min(5, len(df_portfolio_suggest)))
            for idx, row in df_portfolio_suggest.iterrows():
                col_idx = idx % len(cols)
                with cols[col_idx]:
                    st.markdown(f"""
                    <div style="background-color:rgba(42, 82, 152, 0.08); padding:15px; border-radius:8px; border:1px solid rgba(42,82,152,0.2); text-align:center; margin-bottom:10px;">
                        <h4 style="margin:0 0 5px 0; color:#2a5298;">{row['name']}</h4>
                        <span style="font-size:0.8rem; color:#6c757d; font-weight:bold;">{row['code']}</span>
                        <div style="font-size:1.2rem; font-weight:700; margin:8px 0;">PSR: {row['psr']:.3f}</div>
                        <div style="font-size:0.85rem; color:#495057;">부채비율: {row['debt_ratio']:.1f}%</div>
                        <div style="font-size:0.85rem; color:#495057;">시총: {int(row['marcap']/100000000):,}억</div>
                    </div>
                    """, unsafe_allow_html=True)

    # ----------------- TAB 2: BACKTEST -----------------
    with tab2:
        st.subheader("📊 지정 기간 전략 백테스트 시뮬레이션")
        st.write("설정된 필터 조건과 리밸런싱 주기에 맞춰 코스닥 시장에서 과거에 이 전략을 취했을 때의 상세 가상 성과 보고서입니다.")
        
        # Trigger backtest button
        if st.button("🚀 백테스트 실행", type="primary", use_container_width=True):
            with st.spinner("백테스트 시뮬레이션 계산 중..."):
                start_str = start_date.strftime("%Y-%m-%d")
                end_str = end_date.strftime("%Y-%m-%d")
                
                result = backtester.run_backtest(
                    cached_data,
                    start_date_str=start_str,
                    end_date_str=end_str,
                    psr_threshold=psr_threshold,
                    debt_threshold=debt_threshold,
                    consecutive_profitable_quarters=consecutive_profitable_quarters,
                    portfolio_size=portfolio_size,
                    rebalance_freq=rebalance_freq,
                    initial_capital=initial_capital
                )
                
                if result is None:
                    st.error("백테스트를 실행할 수 없습니다. 날짜가 올바른 영업일인지, 캐시 데이터 범위 내에 있는지 확인하세요.")
                else:
                    df_hist, metrics, df_trades = result
                    
                    # 1. Metrics summary cards comparison
                    col1, col2, col3, col4 = st.columns(4)
                    
                    # Asset return delta color style
                    ret_class = "delta-plus" if metrics["total_return"] >= 0 else "delta-minus"
                    bench_ret_class = "delta-plus" if metrics["index_total_return"] >= 0 else "delta-minus"
                    
                    with col1:
                        excess = metrics["total_return"] - metrics["index_total_return"]
                        excess_class = "delta-plus" if excess >= 0 else "delta-minus"
                        st.markdown(f"""
                        <div class="metric-card">
                            <div class="metric-title">누적 수익률 (포트폴리오 vs 벤치마크)</div>
                            <div class="metric-value {ret_class}">{metrics['total_return']:.1f}%</div>
                            <div class="metric-delta">코스닥 대비 초과수익: <span class="{excess_class}">{excess:+.1f}%p</span></div>
                        </div>
                        """, unsafe_allow_html=True)
                        
                    with col2:
                        st.markdown(f"""
                        <div class="metric-card">
                            <div class="metric-title">연평균 복리수익률 (CAGR)</div>
                            <div class="metric-value">{metrics['cagr']:.1f}%</div>
                            <div class="metric-delta">벤치마크 CAGR: <span>{metrics['index_cagr']:.1f}%</span></div>
                        </div>
                        """, unsafe_allow_html=True)
                        
                    with col3:
                        st.markdown(f"""
                        <div class="metric-card">
                            <div class="metric-title">최대 낙폭 (MDD)</div>
                            <div class="metric-value" style="color:#dc3545;">{metrics['mdd']:.1f}%</div>
                            <div class="metric-delta" style="color:#6c757d;">벤치마크 MDD: {metrics['index_mdd']:.1f}%</div>
                        </div>
                        """, unsafe_allow_html=True)
                        
                    with col4:
                        st.markdown(f"""
                        <div class="metric-card">
                            <div class="metric-title">포트폴리오 샤프 지수</div>
                            <div class="metric-value">{metrics['sharpe']:.2f}</div>
                            <div class="metric-delta">총 리밸런싱 횟수: <span>{metrics['rebalance_count']}회</span></div>
                        </div>
                        """, unsafe_allow_html=True)
                        
                    # 2. Cumulative Return Chart (Interactive Plotly)
                    st.subheader("📈 누적 수익률 추이 비교")
                    
                    fig = go.Figure()
                    fig.add_trace(go.Scatter(
                        x=df_hist.index,
                        y=df_hist["portfolio_return"],
                        mode='lines',
                        name='퀀트 포트폴리오',
                        line=dict(color='#2a5298', width=2.5)
                    ))
                    fig.add_trace(go.Scatter(
                        x=df_hist.index,
                        y=df_hist["index_return"],
                        mode='lines',
                        name='코스닥 지수 (Benchmark)',
                        line=dict(color='#ff7f0e', width=1.5, dash='dash')
                    ))
                    
                    fig.update_layout(
                        title="포트폴리오 vs 코스닥 지수 누적 수익률 (%)",
                        xaxis_title="날짜",
                        yaxis_title="수익률 (%)",
                        hovermode="x unified",
                        legend=dict(yanchor="top", y=0.99, xanchor="left", x=0.01),
                        margin=dict(l=20, r=20, t=50, b=20),
                        height=500
                    )
                    st.plotly_chart(fig, use_container_width=True)
                    
                    # 3. Portfolio Asset Breakdown (Current status at end)
                    col_left, col_right = st.columns([2, 1])
                    
                    with col_left:
                        st.subheader("📜 상세 매매 내역 로그")
                        if df_trades.empty:
                            st.write("백테스트 기간 동안 매매 거래 내역이 존재하지 않습니다.")
                        else:
                            df_trades_disp = df_trades.copy()
                            df_trades_disp['price'] = df_trades_disp['price'].map(lambda x: f"{int(x):,}원")
                            df_trades_disp['value'] = df_trades_disp['value'].map(lambda x: f"{int(x):,}원")
                            df_trades_disp.columns = ['거래일자', '구분', '종목코드', '종목명', '수량', '체결단가', '총 체결금액']
                            st.dataframe(df_trades_disp, use_container_width=True, height=350)
                            
                    with col_right:
                        st.subheader("💰 최종 포트폴리오 가치 현황")
                        st.markdown(f"""
                        - **초기 투자금**: {initial_capital:,}원
                        - **최종 자산 평가액**: {int(metrics['final_value']):,}원
                        - **총 수익 금액**: {int(metrics['final_value'] - initial_capital):,}원
                        - **최종 보유 현금**: {int(df_hist['cash'].iloc[-1]):,}원
                        - **최종 보유 주식 가치**: {int(df_hist['stock_value'].iloc[-1]):,}원
                        """)


# ----------------- TAB 3: DATA MANAGEMENT -----------------
with tab3:
    st.subheader("⚙️ 로컬 금융 데이터베이스 관리")
    st.write("한국 주식 시장(코스닥)의 시가총액 정보와 네이버 금융에서 재무제표를 다운로드하여 로컬 파일 시스템에 저장합니다.")
    
    # Metadata status card
    listing_path = os.path.join(data_collector.DATA_DIR, "kosdaq_listing.csv")
    financials_path = os.path.join(data_collector.DATA_DIR, "kosdaq_financials.json")
    prices_path = os.path.join(data_collector.DATA_DIR, "kosdaq_prices.json")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        if os.path.exists(listing_path):
            size = os.path.getsize(listing_path) / 1024
            mtime = datetime.fromtimestamp(os.path.getmtime(listing_path)).strftime('%Y-%m-%d %H:%M:%S')
            st.success(f"종목 목록 데이터: 존재함\n- 크기: {size:.1f} KB\n- 최종 갱신: {mtime}")
        else:
            st.error("종목 목록 데이터: 없음")
            
    with col2:
        if os.path.exists(financials_path):
            size = os.path.getsize(financials_path) / (1024 * 1024)
            mtime = datetime.fromtimestamp(os.path.getmtime(financials_path)).strftime('%Y-%m-%d %H:%M:%S')
            st.success(f"재무제표 데이터 캐시: 존재함\n- 크기: {size:.2f} MB\n- 최종 갱신: {mtime}")
        else:
            st.error("재무제표 데이터 캐시: 없음")
            
    with col3:
        if os.path.exists(prices_path):
            size = os.path.getsize(prices_path) / (1024 * 1024)
            mtime = datetime.fromtimestamp(os.path.getmtime(prices_path)).strftime('%Y-%m-%d %H:%M:%S')
            st.success(f"일별 주가 데이터 캐시: 존재함\n- 크기: {size:.2f} MB\n- 최종 갱신: {mtime}")
        else:
            st.error("일별 주가 데이터 캐시: 없음")
            
    st.markdown("---")
    st.subheader("🔄 데이터 캐시 수집 및 업데이트 수행")
    st.markdown("""
    > [!IMPORTANT]
    > **수집 소요시간 안내**:
    > 최초 데이터 수집 시 코스닥 1,600개 이상 기업의 주가 데이터(최근 2년치)와 분기별 매출액, 영업이익, 부채비율을 네이버 금융에서 가져오기 때문에 약 **1~2분 정도** 소요됩니다. 
    > 안정적인 멀티스레드 병렬 처리가 진행되며 완료되면 로컬 디렉토리에 캐싱되어 다음부턴 0.1초 만에 화면이 로딩됩니다.
    """)
    
    if st.button("🔄 코스닥 전 종목 데이터 다운로드/업데이트 시작", type="primary"):
        # UI controls for updating
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        def update_progress(current, total):
            pct = int(current / total * 100)
            progress_bar.progress(pct / 100.0)
            status_text.text(f"금융 데이터 수집 진행 중... {current}/{total} 종목 ({pct}%)")
            
        try:
            with st.spinner("전 종목 크롤링 및 금융 분석 시뮬레이션 구축 중..."):
                # Run crawler
                success = data_collector.collect_all_data(progress_callback=update_progress)
                if success:
                    st.success("🎉 성공적으로 모든 코스닥 데이터 갱신이 완료되었습니다! 탭을 이동하여 분석해 보세요.")
                    st.balloons()
                    # Force page rerun to reload updated data
                    st.rerun()
                else:
                    st.error("데이터 수집 중 오류가 발생했습니다. 네트워크 상태를 확인하세요.")
        except Exception as e:
            st.error(f"예외 발생: {e}")
