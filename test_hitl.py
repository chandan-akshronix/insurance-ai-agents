import requests
import json
import time

# Configuration
BASE_URL = "http://localhost:8001"
APP_ID = "69268b4c942c07ffe9f96927"

def print_response_details(data):
    """Helper to print response details nicely"""
    print("\n📄 Response Details:")
    print(json.dumps(data, indent=2))

def test_hitl_workflow():
    print("🚀 Starting HITL Workflow Test...")
    
    # Step 1: Start Underwriting
    print(f"\n1️⃣  Sending POST request to {BASE_URL}/underwrite...")
    try:
        response = requests.post(f"{BASE_URL}/underwrite", json={"application_id": APP_ID})
        response.raise_for_status()
        data = response.json()
        
        print(f"   Status: {data.get('status')}")
        print(f"   Message: {data.get('message')}")
        
        # Print full details for the paused state
        print_response_details(data)
        
        if data.get("status") == "paused_for_review":
            print("   ✅ Workflow successfully PAUSED as expected.")
        else:
            print("   ❌ Workflow did NOT pause. Check graph configuration.")
            return

    except Exception as e:
        print(f"   ❌ Error starting workflow: {e}")
        return

    # Simulate Human Review Time
    print("\n⏳ Workflow is PAUSED. The system is waiting for human approval.")
    print(f"   You can check the status via GET {BASE_URL}/applications/pending")
    
    input("\n👉 Press Enter to simulate the Human clicking 'Approve'...")

    # Step 2: Approve Application
    print(f"\n2️⃣  Sending POST request to {BASE_URL}/approve...")
    payload = {
        "application_id": APP_ID,
        "action": "approve",
        "override_notes": "Looks good to me."
    }
    
    try:
        response = requests.post(f"{BASE_URL}/approve", json=payload)
        response.raise_for_status()
        data = response.json()
        
        print(f"   Status: {data.get('status')}")
        
        # Print full details for the completed state
        print_response_details(data)
        
        if data.get("status") == "completed" and data.get("report"):
            print("   ✅ Workflow RESUMED and COMPLETED successfully.")
            print(f"   📄 Report Generated: {data['report'].get('report_path')}")
        else:
            print("   ❌ Workflow failed to complete after approval.")

    except Exception as e:
        print(f"   ❌ Error approving workflow: {e}")

if __name__ == "__main__":
    test_hitl_workflow()
