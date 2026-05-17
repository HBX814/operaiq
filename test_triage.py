import requests
import json

url = "https://operaiq-agents-349176795620.us-central1.run.app/triage"
payload = {"incident_id": "INC-12345", "session_id": "test-123"}
headers = {"Content-Type": "application/json"}

print("Testing Triage Agent endpoint...")
try:
    with requests.post(url, json=payload, headers=headers, stream=True) as r:
        r.raise_for_status()
        for line in r.iter_lines():
            if line:
                print(line.decode('utf-8'))
except Exception as e:
    print(f"Error: {e}")
