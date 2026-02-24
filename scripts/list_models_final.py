import google.generativeai as genai
import os
from dotenv import load_dotenv

load_dotenv()
api_key = os.getenv("GOOGLE_API_KEY", "").split(",")[0]
genai.configure(api_key=api_key)

with open("available_models.txt", "w") as f:
    f.write("Available models:\n")
    try:
        for m in genai.list_models():
            if "generateContent" in m.supported_generation_methods:
                f.write(f"{m.name}\n")
                print(f"Found: {m.name}")
    except Exception as e:
        f.write(f"Error listing models: {e}\n")
        print(f"Error: {e}")
