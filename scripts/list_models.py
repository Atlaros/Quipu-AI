
import asyncio
import sys
import os
# Adjust path to include app
sys.path.append(".")
from app.core.config import settings
from google import genai

def list_models():
    print("Listing models...")
    try:
        client = genai.Client(api_key=settings.google_api_keys[0])
        # The new SDK might have a different way to list models.
        # Checking common patterns: client.models.list()
        
        for m in client.models.list():
            if "gemini" in m.name:
                print(f"- {m.name}")
            
    except Exception as e:
        print(f"Error listing models: {e}")

if __name__ == "__main__":
    list_models()
