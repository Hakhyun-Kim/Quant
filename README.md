# 📈 KOSDAQ Quant Screener & Backtester
> A Python-based web dashboard designed to screen underpriced KOSDAQ equities using custom financial parameters and simulate historical portfolio performance (backtesting) with zero look-ahead bias.

---

## 🚀 Key Features

1. **📊 Financial Screener**
   - Filter active KOSDAQ tickers using parameters such as Price-to-Sales Ratio (PSR), Debt Ratio, and Quarters of Consecutive Operating Profits.
   - Outputs an interactive list of candidate stocks with export capability (CSV download).
   - Dynamically displays candidate cards sorted by valuation order.

2. **📈 Strategy Backtester**
   - Simulates historical buy-and-hold strategies with periodic rebalancing (Monthly, Quarterly, Semi-Annually, Annually).
   - Features transaction costs simulation (0.2% tax/fees) and handles liquidity constraints.
   - Automatically maintains/holds existing portfolio if no new candidate stocks meet the criteria on a rebalancing day (prevents cash-liquidation drag).
   - Generates performance metrics: Cumulative Return, CAGR, Max Drawdown (MDD), and Sharpe Ratio.
   - Visualizes portfolio performance against the KOSDAQ Index using interactive **Plotly charts**.

3. **⚙️ Robust Local Data Manager**
   - Crawls financials (revenue, operating profits, debt, dividend yields) and daily stock prices.
   - Utilizes `ThreadPoolExecutor` with a non-blocking shutdown strategy (`executor.shutdown(wait=False)`) and strict request timeouts to prevent network hangs.
   - Caches compiled data locally in `data/` to achieve sub-second dashboard load times.

---

## 🛠️ Installation & Execution

### 1. Clone Repository
```bash
git clone https://github.com/Hakhyun-Kim/Quant.git
cd Quant
```

### 2. Install Dependencies
```bash
pip install -r requirements.txt
```

### 3. Run Streamlit Dashboard
```bash
python -m streamlit run app.py
```
This will start the local server and automatically launch the dashboard in your default browser at `http://localhost:8501`.

---

## 📅 LLM Integration & Development Log (Phase 1)
We are currently integrating Large Language Models (LLM) to transform this tool into an AI-powered financial research assistant.

### Milestone Tracker
- [x] **Task 1.1: Install `google-genai` SDK and verify local connection**
  - *Goal*: Successfully install the package and run a basic API communication script using `gemini-2.5-flash`.
  - *Status*: **Completed! (Installed `google-genai` and created `scratch/test_gemini.py` ✅)**
  - *Study Log*: 
    - **Unified SDK**: Transitioned to the modern `google-genai` package (v2.10.0+) representing the official client library, replacing the legacy `google-generativeai`.
    - **Model Rationale**: Selected `gemini-2.5-flash` for its sub-second response times, excellent analytical summarization, and cost-efficiency.
    - **Connection Test**: Implemented a connection test script (`scratch/test_gemini.py`) to verify communication and error handling (using `google.genai.errors.APIError`) using dynamic API key loading to prevent credentials leakage.
- [ ] **Task 1.2: Design `ai_evaluator.py` module and prompt engineering**
  - *Goal*: Build prompt templates that convert numeric backtest metrics (CAGR, MDD, Sharpe) into a clear Markdown evaluation.
  - *Status*: Pending ⏳
- [ ] **Task 1.3: Connect Streamlit UI and secure API key session state**
  - *Goal*: Add a secure API password field in the sidebar to prevent key leakage and handle rendering states.
  - *Status*: Pending ⏳
- [ ] **Task 1.4: End-to-end local validation and GitHub release**
  - *Goal*: Verify the Markdown output under the Plotly chart and push to the remote repository.
  - *Status*: Pending ⏳

---

## 📂 Project Directory Structure
```directory
Quant/
│
├── app.py             # Streamlit-based web dashboard UI & input panels
├── backtester.py      # Portfolio screening and historical backtest simulation logic
├── data_collector.py  # Multi-threaded web crawler and local data caching modules
├── requirements.txt   # List of external Python library dependencies
├── .gitignore         # Ignores large binary cache files (data/) and virtual environments
└── README.md          # Project guide and LLM development log (current file)
```
