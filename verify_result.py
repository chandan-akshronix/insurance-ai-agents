import requests
import json
import time
from app_server.utils.clients import db

# Configuration
URL = "http://localhost:8001/underwrite"
APP_ID = "693157d9cfbfd7680ecfef91"

def verify_result():
    print(f"Sending request for App ID: {APP_ID}...")
    try:
        response = requests.post(URL, json={"application_id": APP_ID})
        if response.status_code == 200:
            print("API Request Successful")
        else:
            print(f"API Request Failed: {response.status_code}")
            print(response.text)
            return
    except Exception as e:
        print(f"Connection Error: {e}")
        return

    print("Waiting for async processing (2 seconds)...")
    time.sleep(2)
    
    # NEW: Call /approve to resume the workflow and run the report node
    print(f"Resuming workflow (Approve) for App ID: {APP_ID}...")
    try:
        approve_url = "http://localhost:8001/approve"
        resp = requests.post(approve_url, json={"application_id": APP_ID, "action": "approve"})
        if resp.status_code == 200:
            print("Approval Successful - Workflow Resumed")
        else:
            print(f"Approval Failed: {resp.status_code}")
            print(resp.text)
            return
    except Exception as e:
        print(f"Connection Error during approval: {e}")
        return

    print("Waiting for report generation (3 seconds)...")
    time.sleep(3)

    print(f"Checking MongoDB 'result' collection for App ID: {APP_ID}...")
    try:
        # Find the most recent result for this app_id
        doc = db.result.find_one(
            {"application_id": APP_ID},
            sort=[("timestamp", -1)]
        )
        
        if doc:
            print(f"FOUND RESULT in MongoDB!")
            print(f"   ID: {doc.get('_id')}")
            print(f"   Timestamp: {doc.get('timestamp')}")
            print(f"   Steps Recorded: {len(doc.get('steps', []))}")
            
            steps = doc.get("steps", [])
            if steps:
                print("\n   --- Agent Steps ---")
                for step in steps:
                    print(f"   - {step.get('agent')}: {step.get('output', {}).get('status')}")
        else:
            print("RESULT NOT FOUND in MongoDB.")
            print("   Possible reasons:")
            print("   1. Server code not reloaded (restart uvicorn).")
            print("   2. Exception in report_node (check server logs).")
            print("   3. app_id mismatch.")

    except Exception as e:
        print(f"Error querying MongoDB: {e}")

if __name__ == "__main__":
    verify_result()
