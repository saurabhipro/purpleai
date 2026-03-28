from google import genai
api_key = env['ir.config_parameter'].sudo().get_param('memo_ai.gemini_api_key')
print("API KEY found?", bool(api_key))
client = genai.Client(api_key=api_key)
print("Listing models:")
for m in client.models.list():
    actions = getattr(m, 'supported_actions', []) or getattr(m, 'supportedActions', [])
    if 'generateContent' in actions:
        print(" -", m.name)
