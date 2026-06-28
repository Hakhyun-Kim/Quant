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
        Simulate historical performance and screen KOSDAQ equities using custom financial parameters
    </p>
</div>
""", unsafe_allow_html=True)

# Try to load cached data
cached_data = data_collector.load_cached_data()

# ----------------- SIDEBAR PARAMETERS -----------------
st.sidebar.header("⚙️ Strategy & Backtest Settings")

# 1. Strategy Parameters
st.sidebar.subheader("🎯 Screening Filter Criteria")
psr_threshold = st.sidebar.slider(
    "Price-to-Sales Ratio (PSR) Upper Bound",
    min_value=0.1, max_value=2.0, value=0.8, step=0.05,
    help="PSR = Market Capitalization / Sum of Revenue for recent 4 quarters. Lower values indicate underpricing."
)

debt_threshold = st.sidebar.slider(
    "Debt Ratio Upper Bound (%)",
    min_value=30.0, max_value=300.0, value=100.0, step=5.0,
    help="Debt Ratio = Total Liabilities / Total Equity * 100. Financial safety filter."
)

consecutive_profitable_quarters = st.sidebar.number_input(
    "Consecutive Profitable Quarters (Operating Profit)",
    min_value=1, max_value=6, value=3, step=1,
    help="Filters for companies achieving positive operating profits (>0) for the designated consecutive quarters."
)

# 2. Corporate Size Filter (Market Cap cut)
st.sidebar.subheader("🏢 Corporate Size (Market Cap) Filter")
min_marcap_input = st.sidebar.number_input(
    "Min Market Cap (100M KRW)",
    min_value=0, value=500, step=50,
    help="Excludes micro-cap companies with a market cap below the configured amount."
)
max_marcap_input = st.sidebar.number_input(
    "Max Market Cap (100M KRW, 0 for No Limit)",
    min_value=0, value=0, step=100,
    help="Excludes large-cap companies with a market cap above the configured amount."
)

min_marcap_won = min_marcap_input * 100000000
max_marcap_won = max_marcap_input * 100000000 if max_marcap_input > 0 else float('inf')

# 3. Dividend Filter (Dividend Yield cut)
st.sidebar.subheader("💵 Dividend Yield Filter")
min_div_input = st.sidebar.slider(
    "Min Dividend Yield (%)",
    min_value=0.0, max_value=12.0, value=1.0, step=0.1,
    help="Filters for companies with a dividend yield equal to or greater than the value based on the last fiscal year's closing."
)

# 4. Backtest Settings
st.sidebar.subheader("📈 Backtest Settings")
rebalance_freq = st.sidebar.selectbox(
    "Portfolio Rebalancing Frequency",
    options=["Q", "M", "H", "Y"],
    format_func=lambda x: {"Q": "Quarterly (Q)", "M": "Monthly (M)", "H": "Semi-Annually (H)", "Y": "Annually (Y)"}[x]
)

sort_by_input = st.sidebar.selectbox(
    "Portfolio Sorting Criterion",
    options=["psr", "marcap_asc", "marcap_desc", "div_desc"],
    format_func=lambda x: {
        "psr": "Lowest PSR (Value Stock Bias)",
        "marcap_asc": "Lowest Market Cap (Small-Cap Bias)",
        "marcap_desc": "Highest Market Cap (Large-Cap Bias)",
        "div_desc": "Highest Dividend Yield (High-Dividend Bias)"
    }[x]
)

portfolio_size = st.sidebar.slider(
    "Portfolio Size (Number of Holdings)",
    min_value=3, max_value=30, value=10, step=1,
    help="Determines the maximum number of stocks to hold in the portfolio, selected in order of the sorting criterion."
)

initial_capital = st.sidebar.number_input(
    "Initial Capital (KRW)",
    min_value=1000000, max_value=10000000000, value=100000000, step=10000000,
    format="%d"
)

# Default Backtest Dates (within 2 years roughly)
if cached_data is not None:
    safe_start, latest_end = backtester.get_available_backtest_range(cached_data)
    if safe_start is None:
        safe_start = datetime(2024, 5, 31)
        latest_end = datetime(2026, 6, 23)
else:
    safe_start = datetime(2024, 5, 31)
    latest_end = datetime(2026, 6, 23)

start_date = st.sidebar.date_input(
    "Backtest Start Date", 
    value=max(safe_start, datetime(2024, 5, 31)),
    min_value=safe_start,
    max_value=latest_end,
    help=f"The lower bound of available local financial data is {safe_start.strftime('%Y-%m-%d')}. Backtesting before this date is unavailable."
)
end_date = st.sidebar.date_input(
    "Backtest End Date", 
    value=latest_end,
    min_value=safe_start,
    max_value=latest_end
)

# Validation check for dates
if start_date >= end_date:
    st.sidebar.error("Start date must be before end date.")


# ----------------- TABS CREATION -----------------
tab1, tab2, tab3 = st.tabs(["📊 Real-time Screener", "📈 Backtest Performance", "⚙️ Local Database Cache"])

# If data is not cached, force user to download first
if cached_data is None:
    with tab1:
        st.warning("⚠️ No cached stock price or financial data found. Please run the collector in the **Local Database Cache** tab first.")
    with tab2:
        st.warning("⚠️ Caching is required before running the backtest. Please run the collector in the **Local Database Cache** tab first.")
else:
    # ----------------- TAB 1: SCREENER -----------------
    with tab1:
        st.subheader("🔍 KOSDAQ Screened Stock Candidates")
        st.write("Filtered companies based on the criteria configured in the sidebar (evaluated using the most recent public quarterly financial statements).")
        
        # Today or latest business day available in prices
        latest_date_str = cached_data["index"].index[-1].strftime("%Y-%m-%d")
        
        # Run Screening
        df_screened = backtester.screen_stocks(
            latest_date_str, cached_data,
            psr_threshold=psr_threshold,
            debt_threshold=debt_threshold,
            consecutive_profitable_quarters=consecutive_profitable_quarters,
            min_marcap=min_marcap_won,
            max_marcap=max_marcap_won,
            min_div_yield=min_div_input
        )
        
        # User dynamic sorting for display
        if not df_screened.empty:
            sort_option = st.radio(
                "List Sorting Method",
                options=["Lowest PSR", "Lowest Market Cap (Small-Cap)", "Highest Market Cap (Large-Cap)", "Highest Dividend Yield"],
                horizontal=True
            )
            if sort_option == "Lowest PSR":
                df_screened = df_screened.sort_values(by="psr")
            elif sort_option == "Lowest Market Cap (Small-Cap)":
                df_screened = df_screened.sort_values(by="marcap")
            elif sort_option == "Highest Market Cap (Large-Cap)":
                df_screened = df_screened.sort_values(by="marcap", ascending=False)
            elif sort_option == "Highest Dividend Yield":
                df_screened = df_screened.sort_values(by="div_yield", ascending=False)
        
        if df_screened.empty:
            st.info("No stocks match the selected criteria in the KOSDAQ market. Please loosen the sidebar filter parameters.")
        else:
            # Metrics Summary Row
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.markdown(f"""
                <div class="metric-card">
                    <div class="metric-title">Screened Companies</div>
                    <div class="metric-value">{len(df_screened)}</div>
                </div>
                """, unsafe_allow_html=True)
            with col2:
                st.markdown(f"""
                <div class="metric-card">
                    <div class="metric-title">Average PSR</div>
                    <div class="metric-value">{df_screened['psr'].mean():.3f}</div>
                </div>
                """, unsafe_allow_html=True)
            with col3:
                st.markdown(f"""
                <div class="metric-card">
                    <div class="metric-title">Average Debt Ratio</div>
                    <div class="metric-value">{df_screened['debt_ratio'].mean():.1f}%</div>
                </div>
                """, unsafe_allow_html=True)
            with col4:
                st.markdown(f"""
                <div class="metric-card">
                    <div class="metric-title">Reference Data Date</div>
                    <div class="metric-value">{latest_date_str}</div>
                </div>
                """, unsafe_allow_html=True)
                
            # Table visualization
            df_display = df_screened.copy()
            # Clean formats
            df_display['close'] = df_display['close'].map(lambda x: f"{int(x):,} KRW")
            df_display['marcap'] = df_display['marcap'].map(lambda x: f"{int(x/100000000):,}B KRW")
            df_display['revenue_ttm'] = df_display['revenue_ttm'].map(lambda x: f"{int(x):,}B KRW")
            df_display['psr'] = df_display['psr'].map(lambda x: f"{x:.3f}")
            df_display['debt_ratio'] = df_display['debt_ratio'].map(lambda x: f"{x:.1f}%")
            df_display['div_yield'] = df_display['div_yield'].map(lambda x: f"{x:.2f}%")
            
            df_display.columns = ['Ticker', 'Stock Name', 'Current Price', 'Market Cap', 'TTM Revenue', 'PSR', 'Debt Ratio', 'Dividend Yield']
            
            st.dataframe(df_display, use_container_width=True, hide_index=True)
            
            # Export CSV
            csv_data = df_screened.to_csv(index=False, encoding="utf-8-sig")
            st.download_button(
                label="📥 Download Screened Stocks (CSV)",
                data=csv_data,
                file_name=f"kosdaq_screener_{latest_date_str}.csv",
                mime="text/csv"
            )
            
            # Show top portfolio candidates
            sort_by_label = {
                "psr": "Lowest PSR",
                "marcap_asc": "Lowest Market Cap",
                "marcap_desc": "Highest Market Cap",
                "div_desc": "Highest Dividend Yield"
            }[sort_by_input]
            st.subheader(f"💡 Portfolio Candidates (Top {portfolio_size} by {sort_by_label})")
            
            if sort_by_input == "psr":
                df_portfolio_suggest = df_screened.sort_values(by="psr").head(portfolio_size)
            elif sort_by_input == "marcap_asc":
                df_portfolio_suggest = df_screened.sort_values(by="marcap").head(portfolio_size)
            elif sort_by_input == "marcap_desc":
                df_portfolio_suggest = df_screened.sort_values(by="marcap", ascending=False).head(portfolio_size)
            elif sort_by_input == "div_desc":
                df_portfolio_suggest = df_screened.sort_values(by="div_yield", ascending=False).head(portfolio_size)
            else:
                df_portfolio_suggest = df_screened.sort_values(by="psr").head(portfolio_size)
            cols = st.columns(min(5, len(df_portfolio_suggest)))
            for idx, row in df_portfolio_suggest.reset_index(drop=True).iterrows():
                col_idx = idx % len(cols)
                with cols[col_idx]:
                    st.markdown(f"""
                    <div style="background-color:rgba(42, 82, 152, 0.08); padding:15px; border-radius:8px; border:1px solid rgba(42,82,152,0.2); text-align:center; margin-bottom:10px;">
                        <h4 style="margin:0 0 5px 0; color:#2a5298;">{row['name']}</h4>
                        <span style="font-size:0.8rem; color:#6c757d; font-weight:bold;">{row['code']}</span>
                        <div style="font-size:1.2rem; font-weight:700; margin:6px 0;">PSR: {row['psr']:.3f}</div>
                        <div style="font-size:0.85rem; color:#495057;">Dividend: {row['div_yield']:.2f}%</div>
                        <div style="font-size:0.85rem; color:#495057;">Debt Ratio: {row['debt_ratio']:.1f}%</div>
                        <div style="font-size:0.85rem; color:#495057;">Marcap: {int(row['marcap']/100000000):,}B</div>
                    </div>
                    """, unsafe_allow_html=True)

    # ----------------- TAB 2: BACKTEST -----------------
    with tab2:
        st.subheader("📊 Strategy Backtest Simulation")
        st.write("Backtest simulation report showing the historical performance of the strategy under KOSDAQ market data.")
        
        # Trigger backtest button
        if st.button("🚀 Run Backtest", type="primary", use_container_width=True):
            with st.spinner("Simulating portfolio backtest..."):
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
                    initial_capital=initial_capital,
                    min_marcap=min_marcap_won,
                    max_marcap=max_marcap_won,
                    min_div_yield=min_div_input,
                    sort_by=sort_by_input
                )
                
                if result is None:
                    st.error("Cannot run backtest. Verify if the dates are valid trading days within the cached database range.")
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
                            <div class="metric-title">Cumulative Return (Portfolio vs Index)</div>
                            <div class="metric-value {ret_class}">{metrics['total_return']:.1f}%</div>
                            <div class="metric-delta">Outperformance vs Benchmark: <span class="{excess_class}">{excess:+.1f}%p</span></div>
                        </div>
                        """, unsafe_allow_html=True)
                        
                    with col2:
                        st.markdown(f"""
                        <div class="metric-card">
                            <div class="metric-title">Compound Annual Growth Rate (CAGR)</div>
                            <div class="metric-value">{metrics['cagr']:.1f}%</div>
                            <div class="metric-delta">Benchmark CAGR: <span>{metrics['index_cagr']:.1f}%</span></div>
                        </div>
                        """, unsafe_allow_html=True)
                        
                    with col3:
                        st.markdown(f"""
                        <div class="metric-card">
                            <div class="metric-title">Maximum Drawdown (MDD)</div>
                            <div class="metric-value" style="color:#dc3545;">{metrics['mdd']:.1f}%</div>
                            <div class="metric-delta" style="color:#6c757d;">Benchmark MDD: {metrics['index_mdd']:.1f}%</div>
                        </div>
                        """, unsafe_allow_html=True)
                        
                    with col4:
                        st.markdown(f"""
                        <div class="metric-card">
                            <div class="metric-title">Portfolio Sharpe Ratio</div>
                            <div class="metric-value">{metrics['sharpe']:.2f}</div>
                            <div class="metric-delta">Total Rebalances: <span>{metrics['rebalance_count']} times</span></div>
                        </div>
                        """, unsafe_allow_html=True)
                        
                    # 2. Cumulative Return Chart (Interactive Plotly)
                    st.subheader("📈 Cumulative Return Performance Comparison")
                    
                    fig = go.Figure()
                    fig.add_trace(go.Scatter(
                        x=df_hist.index,
                        y=df_hist["portfolio_return"],
                        mode='lines',
                        name='Quant Portfolio',
                        line=dict(color='#2a5298', width=2.5)
                    ))
                    fig.add_trace(go.Scatter(
                        x=df_hist.index,
                        y=df_hist["index_return"],
                        mode='lines',
                        name='KOSDAQ Index (Benchmark)',
                        line=dict(color='#ff7f0e', width=1.5, dash='dash')
                    ))
                    
                    fig.update_layout(
                        title="Portfolio vs KOSDAQ Index Cumulative Return (%)",
                        xaxis_title="Date",
                        yaxis_title="Return (%)",
                        hovermode="x unified",
                        legend=dict(yanchor="top", y=0.99, xanchor="left", x=0.01),
                        margin=dict(l=20, r=20, t=50, b=20),
                        height=500
                    )
                    st.plotly_chart(fig, use_container_width=True)
                    
                    # 3. Portfolio Asset Breakdown (Current status at end)
                    col_left, col_right = st.columns([2, 1])
                    
                    with col_left:
                        st.subheader("📜 Detailed Trade Log")
                        if df_trades.empty:
                            st.write("No transaction trades occurred during the backtest period.")
                        else:
                            df_trades_disp = df_trades.copy()
                            df_trades_disp['price'] = df_trades_disp['price'].map(lambda x: f"{int(x):,} KRW")
                            df_trades_disp['value'] = df_trades_disp['value'].map(lambda x: f"{int(x):,} KRW")
                            df_trades_disp.columns = ['Trade Date', 'Type', 'Ticker', 'Stock Name', 'Shares', 'Execution Price', 'Total Cost']
                            st.dataframe(df_trades_disp, use_container_width=True, height=350)
                            
                    with col_right:
                        st.subheader("💰 Final Portfolio Value Status")
                        st.markdown(f"""
                        - **Initial Principal**: {initial_capital:,} KRW
                        - **Final Portfolio Value**: {int(metrics['final_value']):,} KRW
                        - **Total Net Profits**: {int(metrics['final_value'] - initial_capital):,} KRW
                        - **Final Cash Balance**: {int(df_hist['cash'].iloc[-1]):,} KRW
                        - **Final Stock Assets Value**: {int(df_hist['stock_value'].iloc[-1]):,} KRW
                        """)


# ----------------- TAB 3: DATA MANAGEMENT -----------------
with tab3:
    st.subheader("⚙️ Local Financial Database Management")
    st.write("Download KOSDAQ equity listings, daily stock price history, and quarterly financial reports from Naver Finance to save locally.")
    
    # Metadata status card
    listing_path = os.path.join(data_collector.DATA_DIR, "kosdaq_listing.csv")
    financials_path = os.path.join(data_collector.DATA_DIR, "kosdaq_financials.json")
    prices_path = os.path.join(data_collector.DATA_DIR, "kosdaq_prices.json")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        if os.path.exists(listing_path):
            size = os.path.getsize(listing_path) / 1024
            mtime = datetime.fromtimestamp(os.path.getmtime(listing_path)).strftime('%Y-%m-%d %H:%M:%S')
            st.success(f"Stock Tickers listing: Active\n- Size: {size:.1f} KB\n- Last Modified: {mtime}")
        else:
            st.error("Stock Tickers listing: Missing")
            
    with col2:
        if os.path.exists(financials_path):
            size = os.path.getsize(financials_path) / (1024 * 1024)
            mtime = datetime.fromtimestamp(os.path.getmtime(financials_path)).strftime('%Y-%m-%d %H:%M:%S')
            st.success(f"Financials Cache: Active\n- Size: {size:.2f} MB\n- Last Modified: {mtime}")
        else:
            st.error("Financials Cache: Missing")
            
    with col3:
        if os.path.exists(prices_path):
            size = os.path.getsize(prices_path) / (1024 * 1024)
            mtime = datetime.fromtimestamp(os.path.getmtime(prices_path)).strftime('%Y-%m-%d %H:%M:%S')
            st.success(f"Daily Prices Cache: Active\n- Size: {size:.2f} MB\n- Last Modified: {mtime}")
        else:
            st.error("Daily Prices Cache: Missing")
            
    st.markdown("---")
    st.subheader("🔄 Update/Rebuild Local Database")
    st.markdown("""
    > [!IMPORTANT]
    > **Information on Crawling Time**:
    > Rebuilding the cache requests daily prices (last 2 years) and financial histories (revenue, operating profits, debt ratio, dividend yield) for 900+ KOSDAQ tickers.
    > The process runs in parallel (30-40 threads) and takes about **1-2 minutes** to complete. Once saved, subsequent dashboard loads are sub-second.
    """)
    
    if st.button("🔄 Start Download/Update of all KOSDAQ stock data", type="primary"):
        # UI controls for updating
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        def update_progress(current, total):
            pct = int(current / total * 100)
            progress_bar.progress(pct / 100.0)
            status_text.text(f"Collecting financial data... {current}/{total} tickers ({pct}%)")
            
        try:
            with st.spinner("Downloading tickers and rebuilding historical quant database..."):
                # Run crawler
                success = data_collector.collect_all_data(progress_callback=update_progress)
                if success:
                    st.success("🎉 Local database successfully cached! Navigate to other tabs to start screening.")
                    st.balloons()
                    # Force page rerun to reload updated data
                    st.rerun()
                else:
                    st.error("An error occurred during data collection. Please check your network connection.")
        except Exception as e:
            st.error(f"Error occurred: {e}")
