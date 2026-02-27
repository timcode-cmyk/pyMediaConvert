import requests
import json

url = "https://api.elevenlabs.io/v1/models"
headers = {
    "xi-api-key": "a4d2617793e30be3eb0337930fa6d9a45a15a2cf0a46270b13d5ab94530030b5",
    "Accept": "application/json"
}
response = requests.get(url, headers=headers, timeout=15)
if response.status_code == 200:
    data = response.json()
    models_list = []
with open("models.json", "w", encoding="utf-8") as f:
    json.dump(data, f, ensure_ascii=False, indent=4)


    