import requests
import json
import sys

# Configuration
URL = "http://localhost:8001/underwrite"
APP_ID = "69268b4c942c07ffe9f96927"

def test_underwrite():
    print(f"🚀 Sending POST request to {URL}...")
    print(f"📦 Payload: {{'application_id': '{APP_ID}'}}")
    
    try:
        response = requests.post(URL, json={"application_id": APP_ID})
        
        print(f"\nStatus Code: {response.status_code}")
        
        try:
            data = response.json()
            print("\n📄 Response:")
            print(json.dumps(data, indent=2))
        except json.JSONDecodeError:
            print("\n📄 Response (Text):")
            print(response.text)
            
        if response.status_code == 200:
            print("\n✅ Test Passed!")
        else:
            print("\n❌ Test Failed!")
            
    except requests.exceptions.ConnectionError:
        print(f"\n❌ Connection Error: Could not connect to {URL}")
        print("💡 Is the server running? Run: uvicorn app_server.app:app --reload --port 8001")
    except Exception as e:
        print(f"\n❌ Error: {e}")

if __name__ == "__main__":
    test_underwrite()
