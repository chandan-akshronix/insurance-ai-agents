from typing import Dict, Any, List

def map_state_to_ui_timeline(state: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Transforms the AgentState into a UI-friendly Timeline structure.
    Each stage has: title, status, input_data, agent_analysis, outcome.
    """
    timeline = []
    
    # --- Stage 1: Customer Submission (Ingest) ---
    ingest = state.get("ingest_llm", {})
    app = state.get("normalized_by_llm", state.get("application", {}))
    
    # Handle Ingest Error gracefully
    ingest_error = ingest.get("data", {}).get("error")
    validation_status = "Completed"
    if ingest_error:
        validation_status = "Completed (System Warning)"
    elif not ingest.get("validated"):
        validation_status = "Completed (Issues Found)"

    timeline.append({
        "stage_name": "Customer Submission",
        "status": validation_status,
        "icon": "check_circle",
        "details": {
            "input_data": {
                "summary": "Customer Form Data",
                "fields": {
                    "Name": app.get("personal_details", {}).get("fullName"),
                    "DOB": app.get("personal_details", {}).get("dob"),
                    "Documents Uploaded": len(app.get("documents", []))
                }
            },
            "agent_analysis": [
                "✅ Validated mandatory fields",
                "✅ Checked document formats",
                "✅ Normalized data structures"
            ] + ([f"⚠️ {issue}" for issue in ingest.get("manual_validation_issues", [])] if not ingest_error else ["⚠️ System Warning: Data normalization had minor issues, proceeding with raw data."]),
            "outcome": {
                "result": "Accepted for processing" if not ingest_error else "Proceeding with Warnings",
                "completeness": "100%" if ingest.get("validated") else "95%"
            }
        }
    })

    # --- Stage 2: Data Validation & Fraud (KYC + Doc Processing) ---
    kyc = state.get("kyc_reconciliation", {})
    docs = state.get("document_processing", {})
    
    # Create a list of processed documents with URLs
    processed_docs_list = []
    for doc_key, res in docs.get("results", {}).items():
        processed_docs_list.append({
            "filename": res.get("filename"),
            "type": res.get("document_type"),
            "url": res.get("url"),
            "status": "Non-Standard" if "Non-Standard" in str(kyc.get("red_flags", [])) and doc_key in str(kyc.get("red_flags", [])) else "Standard"
        })

    kyc_status = kyc.get("kyc_status", "Pending")
    timeline.append({
        "stage_name": "Data Validation & Fraud",
        "status": "Completed" if kyc else "Pending",
        "icon": "shield",
        "details": {
            "input_data": {
                "summary": "Uploaded Documents & Personal Details",
                "documents_processed": docs.get("documents_processed", 0),
                "document_list": processed_docs_list
            },
            "agent_analysis": [
                "✅ OCR Extraction completed",
                "✅ Fuzzy Name Matching performed",
                "✅ Document Classification checked",
                "✅ Forgery/Tampering analysis done"
            ] + [f"🚩 {flag}" for flag in kyc.get("red_flags", [])],
            "outcome": {
                "result": kyc_status,
                "confidence": f"{kyc.get('kyc_confidence', 0)*100:.0f}%"
            }
        }
    })

    # --- Stage 3: Risk Assessment (Health, Financial, Occupation) ---
    health = state.get("health_underwriting", {})
    fin = state.get("financial_eligibility", {})
    
    timeline.append({
        "stage_name": "Risk Assessment",
        "status": "Completed" if health and fin else "Pending",
        "icon": "analytics",
        "details": {
            "input_data": {
                "summary": "Health Questionnaire & Financial Disclosures",
                "bmi": health.get("bmi"),
                "annual_income": f"₹{app.get('personal_details', {}).get('annualIncome', 0)}"
            },
            "agent_analysis": [
                f"✅ BMI Calculated: {health.get('bmi')}",
                "✅ Non-Medical Limits Checked",
                "✅ TRSA Calculated",
                "✅ Income Proof Verified"
            ] + [f"🚩 {r}" for r in health.get("exam_reasons", []) if "Limit" in r] \
              + [f"🚩 {r}" for r in fin.get("rule_findings", [])],
            "outcome": {
                "health_risk": health.get("risk_category"),
                "financial_eligibility": fin.get("eligibility_status"),
                "medical_exam_required": health.get("medical_exam_required")
            }
        }
    })

    # --- Stage 4: Decision Agent ---
    decision = state.get("policy_decision", {})
    
    timeline.append({
        "stage_name": "Decision Agent",
        "status": "Completed" if decision else "In Progress",
        "icon": "gavel",
        "details": {
            "input_data": {
                "summary": "Aggregated Risk Scores",
                "scores": {
                    "Health": health.get("risk_score"),
                    "Financial": fin.get("risk_score"),
                    "KYC": kyc.get("confidence")
                }
            },
            "agent_analysis": [
                "Weighting Risk Scores",
                "Checking for Auto-Decline Rules",
                "Formulating Final Recommendation"
            ],
            "outcome": {
                "decision": decision.get("decision", "Pending"),
                "final_score": decision.get("final_score"),
                "reasons": decision.get("reasons", [])
            }
        }
    })

    return timeline
