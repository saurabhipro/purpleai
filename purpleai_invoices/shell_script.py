from odoo.addons.purpleai_invoices.services.gemini_service import get_gemini_api_key
from google import genai
import os

with open('/tmp/available_models.txt', 'w') as f:
    try:
        api_key = get_gemini_api_key(env=env)
        f.write(f"API KEY FOUND: {api_key[:4]}...{api_key[-4:]}\n")
        client = genai.Client(api_key=api_key)
        models = list(client.models.list())
        f.write("AVAILABLE MODELS:\n")
        found = False
        for m in models:
            actions = getattr(m, 'supported_actions', []) or getattr(m, 'supported_generation_methods', [])
            if 'generateContent' in str(actions):
                 f.write(f"- {m.name}\n")
                 found = True
        if not found:
            f.write("No generative models found for this key.\n")
    except Exception as e:
        f.write(f"ERROR: {str(e)}\n")
