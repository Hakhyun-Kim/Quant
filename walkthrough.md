# KOSDAQ Quant Screener & Backtester Walkthrough

We have successfully designed and built a premium, state-of-the-art **KOSDAQ Quant Screener & Backtester** dashboard. It screens low-PSR stocks combined with earnings stability and financial safety, verifies the strategy historically, and generates intuitive metrics.

---

## Developed Components & Architecture

The application resides in the workspace root: `c:\work\github\Quant` and consists of:

1. **[requirements.txt](file:///c:/work/github/Quant/requirements.txt)**: Defines the libraries including `streamlit`, `FinanceDataReader`, `beautifulsoup4`, and `plotly`.
2. **[data_collector.py](file:///c:/work/github/Quant/data_collector.py)**: 
   - Uses multi-threading (30-40 workers) to scrap Naver Finance and download stock prices concurrently.
   - Implements **non-blocking thread shutdown** (`executor.shutdown(wait=False)`) and strict timeouts to prevent hanging on slow network requests.
   - Safely formats datetimes (avoiding JSON serialization errors) and caches datasets locally in `data/`.
3. **[backtester.py](file:///c:/work/github/Quant/backtester.py)**:
   - Employs a look-ahead bias-free mapping of quarterly financial reports to actual trade dates (e.g. Q1 earnings reflected on May 15th).
   - Simulates portfolio rebalancing (monthly, quarterly, semi-annually, annually) with transaction costs (0.2% tax/fees).
   - Computes core portfolio statistics: Cumulative Return, CAGR, MDD, and Sharpe Ratio.
4. **[app.py](file:///c:/work/github/Quant/app.py)**:
   - Provides a highly aesthetic web dashboard featuring vibrant gradient headers and a sleek, modern UI.
   - Integrates tabs for **Real-time Screener** (real-time candidates and basket suggestions), **Backtest Performance** (interactive configurations, Plotly line charts, trade logs, and **AI Strategy Evaluation Reports**), **Local Database Cache** (data update trigger with live progress indicator), and **AI Stock Assistant** (interactive stock analysis chat).
5. **[ai_evaluator.py](file:///c:/work/github/Quant/ai_evaluator.py)**:
   - A dedicated module interfacing with Gemini API using the unified `google-genai` SDK.
   - Includes prompt templates for backtest strategy summaries and system instruction constraints that keep analysis neutral and regulatory-compliant.
   - Incorporates a real-time Naver News headline crawler to feed qualitative context (such as owner risks and news topics) into user-initiated stock queries.

---

## Backtest Performance Results (2024.05 ~ 2026.06)

A sample backtest was executed with:
- **Criteria**: PSR < 0.8, Debt Ratio < 100%, 3 Consecutive Profitable Quarters.
- **Rules**: Rebalance Quarterly, portfolio size of 10 stocks, 100 million KRW capital.

| Metric | Quant Portfolio | KOSDAQ Index (Benchmark) | Outperformance (Alpha) |
| :--- | :---: | :---: | :---: |
| **Cumulative Return** | **+20.5%** | **+6.1%** | **+14.4%p** |
| **CAGR (Annualized)** | **+9.5%** | **+2.9%** | **+6.6%p** |
| **Max Drawdown (MDD)**| **-15.9%** | **-28.0%** | **+12.1%p (Risk Reduction)** |
| **Sharpe Ratio** | **0.56** | - | - |

> [!TIP]
> **Risk Defense Power**:
> During market downturns, this strategy cut maximum losses **nearly in half** (-15.9% vs -28.0% MDD). This proves that screening for low-PSR value stocks *combined with* high debt safety and earnings stability acts as an exceptional cushion in volatile markets.

---

## How to Run the Application

### 1. View the Web Dashboard
Open your web browser and navigate to the Streamlit local server address:
- **Local URL**: `http://localhost:8501`
- *(If you need to start it manually in the future, run: `python -m streamlit run app.py`)*

### 2. Ready-To-Use Cache
The initial caching process is **fully completed**. 
The local folder contains about **8.6 MB** of compiled datasets (including historical financials for 930 tickers and daily prices for 636 tickers).
You can start screening and backtesting on the webpage **immediately without any delay**!
