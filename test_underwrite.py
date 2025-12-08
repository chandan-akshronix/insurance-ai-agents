import requests
import json
import sys

# Configuration
URL = "http://localhost:8001/underwrite"
APP_ID = "693157d9cfbfd7680ecfef91"

def test_underwrite():
    print(f"Sending POST request to {URL}...")
    print(f"Payload: {{'application_id': '{APP_ID}'}}")
    
    try:
        response = requests.post(URL, json={"application_id": APP_ID})
        
        print(f"\nStatus Code: {response.status_code}")
        
        try:
            data = response.json()
            print("\nResponse:")
            print(json.dumps(data, indent=2))
        except json.JSONDecodeError:
            print("\nResponse (Text):")
            print(response.text)
            
        if response.status_code == 200:
            print("\nTest Passed!")
        else:
            print("\nTest Failed!")
            
    except requests.exceptions.ConnectionError:
        print(f"\nConnection Error: Could not connect to {URL}")
        print("Is the server running? Run: uvicorn app_server.app:app --reload --port 8001")
    except Exception as e:
        print(f"\nError: {e}")

if __name__ == "__main__":
    test_underwrite()
