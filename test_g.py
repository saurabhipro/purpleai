import subprocess
import psycopg2
import sys
import requests

try:
    conn = psycopg2.connect(dbname="main", user="odoo18", host="localhost")
    cur = conn.cursor()
    cur.execute("SELECT value FROM ir_config_parameter WHERE key = 'memo_ai.gemini_api_key'")
    row = cur.fetchone()
    if not row or not row[0]:
        print("NO KEY")
        sys.exit()
    api_key = row[0]
    
    headers = {"Content-Type": "application/json"}
    url = f"https://generativelanguage.googleapis.com/v1beta/models?key={api_key}"
    resp = requests.get(url, headers=headers)
    print("V1BETA MODELS:")
    for m in resp.json().get('models', []):
        if 'generateContent' in m.get('supportedGenerationMethods', []):
            print(" -", m['name'])
            
except Exception as e:
    print("ERROR:", e)
