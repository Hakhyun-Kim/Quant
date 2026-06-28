import os
import requests
from bs4 import BeautifulSoup
from google import genai
from google.genai import types
from google.genai.errors import APIError

def generate_strategy_report(metrics, holdings_desc, api_key):
    """
    Generates a structured qualitative analysis report of the backtest strategy.
    Uses gemini-2.5-flash with a strict neutral analytical system instruction.
    """
    try:
        client = genai.Client(api_key=api_key)
        
        system_instruction = (
            "You are a professional Quant Analyst and financial expert. Your task is to write a highly "
            "analytical, objective, and qualitative evaluation report of a quantitative KOSDAQ equity "
            "strategy based on its backtesting metrics.\n"
            "Maintain a neutral, purely analytical tone. Avoid any language that implies investment "
            "advice, recommendations, or guarantees of future performance. Focus strictly on analyzing "
            "historical performance, risk-adjusted returns (Sharpe ratio), drawdowns (MDD), and index "
            "outperformance. Write the entire report in English."
        )
        
        prompt = f"""
        Analyze the following quantitative strategy backtest results:
        
        - Initial Capital: {metrics['initial_capital']:,} KRW
        - Final Portfolio Value: {metrics['final_value']:,} KRW
        - Strategy Cumulative Return: {metrics['total_return']:.2f}%
        - Benchmark (KOSDAQ Index) Cumulative Return: {metrics['index_total_return']:.2f}%
        - Strategy CAGR: {metrics['cagr']:.2f}%
        - Benchmark CAGR: {metrics['index_cagr']:.2f}%
        - Strategy Max Drawdown (MDD): {metrics['mdd']:.2f}%
        - Benchmark MDD: {metrics['index_mdd']:.2f}%
        - Strategy Sharpe Ratio: {metrics['sharpe']:.2f}
        - Number of Rebalances: {metrics['rebalance_count']}
        - Backtest Duration (Days): {metrics['days']}

        Current Portfolio Stock Candidates:
        {holdings_desc}

        Please generate a structured evaluation report in Markdown containing:
        1. ## Executive Summary: A high-level overview of the strategy's overall performance.
        2. ## Performance & Return Attribution: Comparison of cumulative return and CAGR against the benchmark.
        3. ## Risk & Drawdown Profile: Analysis of Sharpe ratio, MDD, and drawdown defense capability.
        4. ## Portfolio Review: A qualitative observation of the current stock candidates (financial safety indicated by debt ratios, value characteristics).
        """
        
        config = types.GenerateContentConfig(
            system_instruction=system_instruction,
            temperature=0.2,
        )
        
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt,
            config=config
        )
        return response.text
        
    except APIError as ae:
        raise Exception(f"Gemini API Error: {ae.message} (Status: {ae.code})")
    except Exception as e:
        raise Exception(f"Error during report generation: {e}")

def crawl_news_headlines(stock_name):
    """
    Crawls the top 5 recent news headlines from Naver News search for the given stock name.
    """
    # Use stock name + "주식" (stock) to filter relevant stock news
    query = f"{stock_name}"
    url = f"https://search.naver.com/search.naver?where=news&query={query}"
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        )
    }
    
    try:
        res = requests.get(url, headers=headers, timeout=5)
        if res.status_code != 200:
            return []
            
        soup = BeautifulSoup(res.text, "html.parser")
        news_links = soup.find_all("a", class_="news_tit")
        
        headlines = []
        for link in news_links[:5]:
            title = link.text.strip()
            headlines.append(title)
        return headlines
    except Exception:
        return []

def answer_stock_query(stock_name, stock_code, financials, news_headlines, query, api_key):
    """
    Answers user questions regarding a specific stock using Gemini 2.5 Flash.
    Provides financial metrics and recent crawled news headlines as context.
    """
    try:
        client = genai.Client(api_key=api_key)
        
        system_instruction = (
            "You are a neutral financial research assistant. Your purpose is to evaluate "
            "individual equities using both quantitative financial metrics and qualitative news headlines.\n"
            "Maintain a strictly objective, analytical tone. Do NOT provide direct buy/sell recommendations, "
            "investment advice, or predictions. Focus on outlining financial stability (e.g., debt ratio, profitability), "
            "valuation, and recent news topics/potential risks.\n"
            "Response Language: Respond in the same language as the user's question. If the user asks in Korean, "
            "respond in Korean. If asked in English, respond in English."
        )
        
        news_context = "\n".join([f"- {h}" for h in news_headlines]) if news_headlines else "No recent news headlines available."
        
        prompt = f"""
        Analyze the stock candidate '{stock_name}' ({stock_code}) based on the following context and answer the user's query.
        
        [Financial Condition Context]
        - Valuation (PSR): {financials.get('psr', 'N/A')}
        - Debt Ratio: {financials.get('debt_ratio', 'N/A')}%
        - Dividend Yield: {financials.get('div_yield', 'N/A')}%
        - Recent profitable quarters: {financials.get('consecutive_profitable_quarters', 'N/A')} quarters consecutive operating profits.
        
        [Recent News Headlines Context]
        {news_context}
        
        [User Query]
        "{query}"
        
        Please provide a structured, professional response including financial health analysis, recent news takeaways, and potential risk factors.
        """
        
        config = types.GenerateContentConfig(
            system_instruction=system_instruction,
            temperature=0.3,
        )
        
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt,
            config=config
        )
        return response.text
        
    except APIError as ae:
        raise Exception(f"Gemini API Error: {ae.message} (Status: {ae.code})")
    except Exception as e:
        raise Exception(f"Error during query response: {e}")
