import requests

api_key = env['ir.config_parameter'].sudo().get_param('memo_ai.gemini_api_key')
if not api_key:
    api_key = env['ir.config_parameter'].sudo().get_param('tender_ai.ai_api_key') or env['ir.config_parameter'].sudo().get_param('tender_ai.gemini_api_key')

url = f"https://generativelanguage.googleapis.com/v1beta/models?key={api_key}"
try:
    resp = requests.get(url)
    print("--- RAW MODELS ---")
    for m in resp.json().get('models', []):
        methods = m.get('supportedGenerationMethods', [])
        if 'generateContent' in methods:
            print(m['name'])
    print("--------------")
except Exception as e:
    print("ERR:", e)
