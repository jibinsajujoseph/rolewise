import requests

base_url = "http://localhost:8000/api"

resume_payload = {
    "contact": {"name": "Test", "links": []},
    "skills": [],
    "experience": [],
    "education": [],
    "projects": [],
    "certifications": []
}

payload = {"resume": resume_payload, "jd_text": "Software Engineer"}

print("Calling /api/suggest (1)...")
res1 = requests.post(f"{base_url}/suggest", json=payload)
data1 = res1.json()
print(f"Suggest 1 successful. limit: {data1.get('limit')}, remaining_calls: {data1.get('remaining_calls')}")
if 'error' in data1: print(data1)

print("Calling /api/suggest (2)...")
res2 = requests.post(f"{base_url}/suggest", json=payload)
data2 = res2.json()
print(f"Suggest 2 successful. limit: {data2.get('limit')}, remaining_calls: {data2.get('remaining_calls')}")
if 'error' in data2: print(data2)

print("Calling /api/suggest (3)...")
res3 = requests.post(f"{base_url}/suggest", json=payload)
data3 = res3.json()
print(f"Suggest 3 successful. limit: {data3.get('limit')}, remaining_calls: {data3.get('remaining_calls')}")
if 'error' in data3: print(data3)

print("Calling /api/suggest (4) - Should hit rate limit...")
res4 = requests.post(f"{base_url}/suggest", json=payload)
data4 = res4.json()
print(f"Suggest 4 successful. limit: {data4.get('limit')}, remaining_calls: {data4.get('remaining_calls')}")
if 'error' in data4: print(data4)

