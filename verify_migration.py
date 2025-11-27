import requests
import json


payload = {"application_id": "69268b4c942c07ffe9f96927"}

def check_endpoint(url, method="GET", payload=None):
    print(f"\nChecking {url} ({method})...")
    try:
        if method == "GET":
            response = requests.get(url)
        else:
            response = requests.post(url, json=payload)
        
        print(f"Status Code: {response.status_code}")
        print("Response:")
        print(json.dumps(response.json(), indent=2))
    except Exception as e:
        print(f"Error: {e}")

# Check Health
check_endpoint("http://localhost:8001/health")

# Check Root
check_endpoint("http://localhost:8001/")

# Check Underwrite
check_endpoint("http://localhost:8001/underwrite", method="POST", payload=payload)
