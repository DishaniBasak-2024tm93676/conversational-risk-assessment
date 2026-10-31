"""
check_models.py

Lists the Gemini models actually available to your API key right now.
Run this once to find the exact, current name of a Flash-Lite model
(higher free daily quota than Flash) before we hardcode it anywhere.

Usage:
    python3 evaluation/check_models.py
"""

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), "..", "framework"))

from dotenv import load_dotenv
load_dotenv()
import os as _os
from google import genai

client = genai.Client(api_key=_os.environ.get("GEMINI_API_KEY"))

print("Models available to your API key:\n")
for model in client.models.list():
    name = model.name
    if "flash" in name.lower() or "lite" in name.lower():
        print(f"- {name}")