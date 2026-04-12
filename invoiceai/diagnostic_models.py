import os
import sys

# Path to Odoo source
sys.path.append('/home/odoo18/odoo-source')

# Mock Odoo environment for the service to work (or just get the key manually)
# Better: Just try to find the key in the database via psycopg2 if needed, 
# but let's try to just get the list of models if we have an API key.

def run_test():
    try:
        from google import genai
        # Try some common environment variables
        api_key = os.getenv("AI_API_KEY") or os.getenv("GEMINI_API_KEY")
        
        # If not in env, we might need to fetch it from odoo.conf
        if not api_key:
             with open('/home/odoo18/odoo-source/odoo.conf', 'r') as f:
                 for line in f:
                     if 'ai_api_key' in line.lower():
                         api_key = line.split('=')[1].strip()
        
        if not api_key:
             print("Could not find API key in environment or odoo.conf")
             return

        client = genai.Client(api_key=api_key)
        print("LISTING MODELS:")
        for m in client.models.list():
            print(f"FOUND: {m.name}")
            
    except Exception as e:
        print(f"CRITICAL ERROR: {str(e)}")

if __name__ == "__main__":
    run_test()
