import os
import sys
from google import genai
from google.genai.errors import APIError

def test_gemini_connection(api_key):
    """
    Test connection to Gemini 2.5 Flash API with dummy quant metrics.
    """
    print("Initializing Google GenAI client...")
    try:
        # Initialize client with specified API key
        client = genai.Client(api_key=api_key)
        
        test_prompt = (
            "You are a professional Quant Analyst. Summarize this strategy performance "
            "in 2 short bullet points (in English):\n"
            "- Strategy Return: +15.5%\n"
            "- Benchmark Return: +5.0%\n"
            "- Max Drawdown: -12.0%\n"
        )
        
        print("Sending generation request to 'gemini-2.5-flash'...")
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=test_prompt,
        )
        
        print("\n[SUCCESS] Connection Successful! Gemini Response:")
        print("------------------------------------------")
        print(response.text)
        print("------------------------------------------")
        return True
        
    except APIError as ae:
        print(f"\n[ERROR] API Error occurred: {ae.message} (Status Code: {ae.code})")
        print("Please verify if your Gemini API key is valid and active.")
        return False
    except Exception as e:
        print(f"\n[ERROR] Unexpected error: {e}")
        return False

if __name__ == "__main__":
    # Allow passing API key via command line argument or environment variable
    api_key = os.environ.get("GEMINI_API_KEY")
    
    if not api_key and len(sys.argv) > 1:
        api_key = sys.argv[1]
        
    if not api_key:
        print("[ERROR] Error: No Gemini API Key provided.")
        print("Usage: python test_gemini.py <YOUR_API_KEY> or set GEMINI_API_KEY env var.")
        sys.exit(1)
        
    test_gemini_connection(api_key)
