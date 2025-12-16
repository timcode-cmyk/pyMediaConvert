import os, requests, json
key = os.getenv("ELEVENLABS_API_KEY")
url = "https://api.elevenlabs.io/v1/sound-generation"
headers = {"xi-api-key": key, "Content-Type": "application/json"}
data = {"prompt":"test","duration_seconds":1,"model_id":"eleven_turbo_v2"}
r = requests.post(url, json=data, headers=headers, timeout=30)
print(r.status_code, r.text)