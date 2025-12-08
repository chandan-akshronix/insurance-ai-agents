import requests
import json
import time

# Configuration
BASE_URL = "http://localhost:8001"
APP_ID = f"APP-{int(time.time())}"

def print_section(title):
    print(f"\n{'='*60}")
    print(f" {title}")
    print(f"{'='*60}")

def run_test():
    print_section("🚀 Starting Frontend Integration Test")
    print(f"Target Application ID: {APP_ID}")

    # 1. Trigger Underwriting
    print("\n1️⃣  Simulating 'Start Underwriting' (POST /underwrite)...")
    try:
        response = requests.post(f"{BASE_URL}/underwrite", json={"application_id": APP_ID})
        response.raise_for_status()
        data = response.json()
    except Exception as e:
        print(f"❌ Failed to connect to backend: {e}")
        return

    # 2. Extract Audit Trail
    audit_trail = data.get("audit_trail", {})
    decision = data.get("decision", {})
    
    # 3. Generate Mapping Report
    print_section("🎨 Frontend Data Mapping Verification")
    
    # UI Section: Header & Timeline
    print("\n[UI Section: Header & Timeline]")
    print(f"🔹 Application ID: {data.get('thread_id')}")
    print(f"🔹 Status: {data.get('status')} (Map to: 'In Progress' or 'Waiting for Decision')")
    print(f"🔹 Customer Submission: ✅ Completed")
    print(f"🔹 Data Validation: {'✅ Completed' if audit_trail.get('ingest', {}).get('status') == 'Validated' else '⚠️ Issues Found'}")
    
    # UI Section: Customer Submission (Input Data)
    print("\n[UI Section: Customer Submission]")
    ingest_data = audit_trail.get("ingest", {}).get("data", {}).get("normalized_application", {})
    personal = ingest_data.get("personal_details", {})
    print(f"🔹 Name: {personal.get('fullName')}")
    print(f"🔹 DOB: {personal.get('dob')}")
    print(f"🔹 Documents: {len(ingest_data.get('documents', []))} files uploaded")
    
    # UI Section: Agent Analysis (Streaming View)
    print("\n[UI Section: Agent Analysis]")
    
    # KYC
    kyc = audit_trail.get("kyc", {})
    print(f"🔸 KYC Status: {kyc.get('status')}")
    if kyc.get("data", {}).get("mismatches"):
        print(f"   - Mismatches: {len(kyc.get('data', {}).get('mismatches'))} found (Show in Red)")
        
    # Document Verification
    docs = audit_trail.get("document_processing", {}).get("results", {})
    print(f"🔸 Documents Processed: {len(docs)}")
    for doc_name, res in docs.items():
        doc_type = res.get("ocr_result", {}).get("document_type", "Unknown")
        print(f"   - {doc_name}: Identified as {doc_type}")

    # Health
    health = audit_trail.get("health", {})
    print(f"🔸 Health Risk Score: {health.get('risk_score')}")
    for rule in health.get("rule_findings", []):
        print(f"   - 🚩 Rule Triggered: {rule}")

    # Financial
    fin = audit_trail.get("financial", {})
    print(f"🔸 Financial Risk Score: {fin.get('risk_score')}")
    for rule in fin.get("rule_findings", []):
        print(f"   - 🚩 Rule Triggered: {rule}")

    # UI Section: Decision & Output
    print("\n[UI Section: Decision & Output]")
    print(f"🔹 Outcome: {decision.get('decision')}")
    print(f"🔹 Confidence Score: {decision.get('final_score')}%")
    print(f"🔹 Key Reasons:")
    for reason in decision.get('reasons', []):
        print(f"   - {reason}")

    # 4. Verify UI Visualization Field
    print_section("✨ UI Visualization Data (New)")
    ui_viz = data.get("ui_visualization", [])
    print(f"Found {len(ui_viz)} timeline stages.")
    for stage in ui_viz:
        print(f"🔹 {stage['stage_name']} ({stage['status']})")
        print(f"   - Input: {stage['details']['input_data'].get('summary')}")
        print(f"   - Outcome: {stage['details']['outcome']}")

    # 5. Save JSON for Frontend Dev
    filename = "frontend_response_sample.json"
    with open(filename, "w") as f:
        json.dump(data, f, indent=2)
    
    print_section(f"✅ Test Complete! Full JSON saved to '{filename}'")
    print("👉 Hand this JSON file to your Frontend Developer to build the UI.")

if __name__ == "__main__":
    run_test()
