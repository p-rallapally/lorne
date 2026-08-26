import requests

LOCATION_ID = "5Q2XG9jN1CwLZLN40W03"
TOKEN = "SxbQqrTSrT4DaSgaluKp1wBpKhx4QbGh4H9yb9S7qHcdPY3LUVldDBnyRKdDWc5f"

url = f"https://events-portal-sage.vercel.app/api/events/{LOCATION_ID}"

response = requests.get(
    url,
    headers={
        "Authorization": f"Bearer {TOKEN}",
        "Accept": "application/json",
    },
    timeout=30,
)

response.raise_for_status()

payload = response.json()

print("Status:", response.status_code)
print("Events:", len(payload.get("data", {}).get("events", [])))

events = payload.get("data", {}).get("events", [])

if events:
    print("\nFIRST EVENT:")
    print(events[0])