
import httpx
from datetime import datetime, timedelta, timezone

url = "http://127.0.0.1:8000/api/analysis"
params = {"from": "2026-01-06", "to": "2026-01-07"}

response = httpx.get(url, params=params, timeout=60)
response.raise_for_status()
data = response.json()

records = data.get("records", [])
timestamps = [
    datetime.fromisoformat(r["timestamp"].replace("Z", "+00:00"))
    for r in records
]

expected = {
    datetime(2026, 1, 6, tzinfo=timezone.utc) + timedelta(hours=i)
    for i in range(48)
}
actual = set(timestamps)

print("Record count:", len(records))
print("Unique timestamps:", len(actual))
print("First timestamp:", min(actual).isoformat() if actual else "NONE")
print("Last timestamp:", max(actual).isoformat() if actual else "NONE")
print("Missing hours:", sorted(t.isoformat() for t in expected - actual))
print("Unexpected timestamps:", sorted(t.isoformat() for t in actual - expected))
print("Duplicate timestamps:", len(timestamps) - len(actual))
print("Full 48-hour coverage:", actual == expected and len(timestamps) == 48)
