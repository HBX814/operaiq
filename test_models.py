import os
from google import genai

client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))
print("Available Models:")
for m in client.models.list():
    if "generateContent" in m.supported_generation_methods:
        print(m.name)
