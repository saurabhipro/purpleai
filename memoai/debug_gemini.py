import xmlrpc.client
import requests
import json
import os

def check_models(api_key):
    # Try both v1 and v1beta
    for ver in ['v1', 'v1beta']:
        url = f"https://generativelanguage.googleapis.com/{ver}/models?key={api_key}"
        res = requests.get(url)
        print(f"--- CHECKING {ver} ---")
        print(f"Status: {res.status_code}")
        if res.status_code == 200:
            models = res.json().get('models', [])
            for m in models:
                name = m.get('name', '???')
                methods = m.get('supportedGenerationMethods', [])
                if 'embedContent' in methods:
                    print(f"SUCCESS: {name} SUPPORTS embedContent")
                elif 'batchEmbedContents' in methods:
                    print(f"SUCCESS: {name} SUPPORTS batchEmbedContents")
        else:
            print(f"Error {ver}: {res.text}")

# Get API Key directly from Odoo
try:
    # Just read the odoo.conf to find the DB details
    # Actually, simpler: search for the key in the DB via sudo
    pass
except:
    pass

# FALLBACK manually provided in command if needed
if len(os.sys.argv) > 1:
    check_models(os.sys.argv[1])
else:
    print("Please provide API Key as argument.")
