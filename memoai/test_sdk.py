try:
    from google import genai
    print("genai imported")
    client = genai.Client(api_key='DUMMY')
    print("client created")
except Exception as e:
    print(f"FAILED: {e}")
