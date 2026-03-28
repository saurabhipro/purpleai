import sys
import psycopg2
from google import genai

try:
    conn = psycopg2.connect(dbname="main", user="odoo18", host="localhost")
    cur = conn.cursor()
    cur.execute("SELECT value FROM ir_config_parameter WHERE key = 'memo_ai.gemini_api_key'")
    row = cur.fetchone()
    if not row or not row[0]:
        print("No API key in DB")
        sys.exit(1)
    
    api_key = row[0]
    client = genai.Client(api_key=api_key)
    print("Listing models:")
    models = list(client.models.list())
    for m in models:
        actions = getattr(m, 'supported_actions', []) or getattr(m, 'supportedActions', [])
        if 'generateContent' in actions:
            print(" -", m.name)

except Exception as e:
    print("Error:", e)
