import google.generativeai as genai
import os
from dotenv import load_dotenv

load_dotenv()
api_key = os.getenv("GOOGLE_API_KEY", "").split(",")[0]
genai.configure(api_key=api_key)

candidates = [
    "gemini-2.0-flash",
    "gemini-1.5-flash",
    "gemini-1.5-pro",
    "gemini-1.5-pro-latest",
    "gemini-1.5-pro-001",
    "gemini-1.0-pro"
]

print("Checking models...")
for model in candidates:
    try:
        m = genai.GenerativeModel(model)
        # Just checking if we can init, real test is generate but that costs quota
        # better to check list_models
        pass
    except Exception as e:
        print(f"Init failed for {model}: {e}")

# List actual models
try:
    print("\nListing available models from API:")
    for m in genai.list_models():
        if "generateContent" in m.supported_generation_methods:
            print(f"- {m.name}")
except Exception as e:
    print(f"List failed: {e}")
