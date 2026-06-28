# LLM Quant Development & Study Log (Phase 1)

This log tracks our progress step-by-step as we integrate LLM features into our KOSDAQ Quant Backtester. Each task lists key learning objectives and status updates.

---

## Milestones & Progress

- **Task 1.1: Install `google-genai` dependency and run local connection tests**
  - **Learning Objectives**: Understanding Gemini API connection workflows, using the official Google GenAI SDK, and managing API key configurations safely.
  - **Status**: **Completed! (Installed `google-genai` 2.10.0 & created connection script `scratch/test_gemini.py` [SUCCESS])**
- **Task 1.2: Design `ai_evaluator.py` module and write prompt templates**
  - **Learning Objectives**: Prompt engineering (System Instructions, Few-shot prompting), transforming quantitative metrics into narrative contexts.
  - **Status**: Pending...
- **Task 1.3: Connect Streamlit UI and manage secure session state (`app.py`)**
  - **Learning Objectives**: Securing API keys via user input in Streamlit, keeping keys in session memory (`st.session_state`), and displaying spinner indicators.
  - **Status**: Pending...
- **Task 1.4: End-to-end local validation and GitHub commit**
  - **Learning Objectives**: Running backtests, generating markdown reports on UI, and structuring commits.
  - **Status**: Pending...

---

## Study Notes

### Task 1.1: Google GenAI SDK & Gemini API Overview
* **New Google Client SDK**: Google supports the unified **`google-genai`** package (released in 2025) as the standard SDK, replacing the older `google-generativeai` package.
* **Gemini 2.5 Flash**: A high-speed, cost-efficient model with excellent text summary capabilities, making it ideal for real-time dashboard generation.
* **Basic API Call Structure**:
  ```python
  from google import genai
  client = genai.Client(api_key="YOUR_API_KEY")
  response = client.models.generate_content(
      model='gemini-2.5-flash',
      contents='Hello, analyse this data...'
  )
  print(response.text)
  ```
