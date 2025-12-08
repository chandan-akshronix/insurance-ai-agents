import os
import json
from datetime import datetime
from fpdf import FPDF
from app_server.agent.state import AgentState
from app_server.utils.clients import azure_client, AZURE_DEPLOYMENT_NAME
from app_server.agent.config import PATHS
from app_server.agent.models import ReportOutput
from app_server.agent.prompts import REPORT_PROMPT

def report_node(state: AgentState):
    print("--- Report Node ---")
    out_dir = "reports"
    os.makedirs(out_dir, exist_ok=True)
    app = state.get("normalized_by_llm", state.get("application", {}))
    name = app.get("personal_details", {}).get("full_name", "Applicant")
    decision = state.get("policy_decision", {})
    
    # Generate report text using LLM
    prompt = REPORT_PROMPT.format(
        app_summary=json.dumps(app, ensure_ascii=False),
        decision=json.dumps(decision, ensure_ascii=False)
    )

    try:
        resp = azure_client.beta.chat.completions.parse(
            model=AZURE_DEPLOYMENT_NAME,
            messages=[{"role": "user", "content": prompt}],
            response_format=ReportOutput,
            temperature=0.0
        )
        parsed_output = resp.choices[0].message.parsed
        report_content = parsed_output.model_dump()
        
        # Construct the text for the PDF from the structured output
        text = f"""
Executive Summary:
{report_content['summary']}

Key Findings:
{chr(10).join(['- ' + finding for finding in report_content['key_findings']])}

Risk Assessment:
{report_content['risk_assessment']}

Recommendation:
{report_content['recommendation_text']}
"""
    except Exception as e:
        print(f"❌ Error in Report LLM: {e}")
        text = f"Error generating report text: {str(e)}"

    # Build PDF with Unicode support
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = os.path.join(out_dir, f"Underwriting_Report_{name.replace(' ', '_')}_{ts}.pdf")
    
    # Create PDF with Unicode support
    pdf = FPDF()
    pdf.add_page()
    pdf.set_auto_page_break(True, 15)
    
    # Add a Unicode-compatible font (DejaVuSans supports many Unicode characters including ₹)
    font_loaded = False
    try:
        # Try to use DejaVuSans if available
        # Check common paths for DejaVuSans
        font_paths = ["DejaVuSans.ttf", "fonts/DejaVuSans.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"]
        for fp in font_paths:
            if os.path.exists(fp):
                pdf.add_font('DejaVuSans', '', fp, uni=True)
                pdf.set_font('DejaVuSans', '', 11)
                font_loaded = True
                break
    except Exception as e:
        print(f"Warning: Could not load DejaVuSans: {e}")

    if not font_loaded:
        try:
            # Fall back to Arial Unicode MS if available
            pdf.add_font('Arial', '', 'arial.ttf', uni=True)
            pdf.set_font('Arial', '', 11)
            font_loaded = True
        except:
            # Final fallback to standard font (may not support all Unicode chars)
            print("Warning: Using standard font. Unicode characters may not render correctly.")
            pdf.set_font('Arial', size=11)
    
    # Add header
    pdf.set_font('Arial', 'B', 14)
    pdf.cell(0, 8, "Underwriting Report", ln=True, align="C")
    pdf.ln(6)
    
    # Add main content with proper Unicode handling
    pdf.set_font('Arial', '', 11)
    
    # Replace Rupee symbol with 'Rs.' if the current font doesn't support it
    if '₹' in text and pdf.get_string_width('₹') == 0:
        text = text.replace('₹', 'Rs.')
    
    # Add multi-line text with proper encoding
    pdf.multi_cell(0, 6, text.encode('latin-1', 'replace').decode('latin-1') if pdf.font_family == 'Arial' else text)
    
    # Add footer
    pdf.ln(6)
    pdf.set_font('Arial', 'I', 9)
    pdf.cell(0, 6, f"Generated: {datetime.now().isoformat()}", ln=True)
    
    # Save the PDF
    pdf.output(path, 'F')
    
    out = {"report_path": path, "status": "success"}
    
    # --- Persistence: Save Full Audit Trail to MongoDB ---
    try:
        from app_server.utils.clients import db
        from bson import ObjectId
        
        app_id = state.get("application_id")
        print(f"DEBUG: Report Node - App ID: {app_id}")
        
        if app_id:
            print("DEBUG: Entering persistence block...")
            # 1. Construct Standard Audit Trail (for UI/API)
            from app_server.utils.ui_mapper import map_state_to_ui_timeline
            
            audit_trail = {
                "ui_visualization": map_state_to_ui_timeline(state),
                "ingest": {
                    "status": "Validated" if state.get("ingest_llm", {}).get("validated") else "Issues Found",
                    "validation_issues": state.get("ingest_llm", {}).get("manual_validation_issues", []),
                    "data": state.get("ingest_llm")
                },
                "document_processing": state.get("document_processing"),
                "kyc": {
                    "status": state.get("kyc_reconciliation", {}).get("kyc_status"),
                    "document_classification": state.get("kyc_reconciliation", {}).get("document_classification", {}),
                    "data": state.get("kyc_reconciliation")
                },
                "health": {
                    "risk_score": state.get("health_underwriting", {}).get("risk_score"),
                    "medical_exam_required": state.get("health_underwriting", {}).get("medical_exam_required"),
                    "rule_findings": [r for r in state.get("health_underwriting", {}).get("exam_reasons", []) if "Limit" in r],
                    "data": state.get("health_underwriting")
                },
                "financial": {
                    "risk_score": state.get("financial_eligibility", {}).get("risk_score"),
                    "rule_findings": state.get("financial_eligibility", {}).get("rule_findings", []),
                    "data": state.get("financial_eligibility")
                },
                "occupation": state.get("occupation_risk"),
                "insurance_history": state.get("insurance_history"),
                "medical_exam": state.get("medical_exam_workflow"),
                "report_path": path,
                "generated_at": datetime.now().isoformat()
            }
            
            # Update main application record
            db["life_insurance_applications"].update_one(
                {"_id": ObjectId(app_id)},
                {"$set": {"underwriting_result": audit_trail}}
            )
            print(f"✅ Saved full underwriting result to MongoDB for App ID: {app_id}")

            # 2. Construct Structured 'Result' Log (Input -> Process -> Output)
            structured_steps = []

            # Helper to add step
            def add_step(agent_name, input_data, process_data, output_data):
                structured_steps.append({
                    "agent": agent_name,
                    "input": input_data,
                    "process": process_data,
                    "output": output_data,
                    "timestamp": datetime.now().isoformat()
                })

            # Ingest Step
            ingest_data = state.get("ingest_llm", {})
            add_step("ingest", 
                {"app_id": app_id}, 
                {"validation_issues": ingest_data.get("manual_validation_issues"), "explanation": ingest_data.get("llm_explanation")},
                {"status": "Validated" if ingest_data.get("validated") else "Issues Found", "data": ingest_data}
            )

            # Document Processing Step
            doc_data = state.get("document_processing", {})
            add_step("document_processing",
                {"raw_documents": len(app.get("documents", []))},
                {"ocr_status": doc_data.get("ocr_status")},
                {"processed_count": doc_data.get("documents_processed"), "results": doc_data.get("results")}
            )

            # KYC Step
            kyc_data = state.get("kyc_reconciliation", {})
            add_step("kyc",
                {"documents_verified": kyc_data.get("documents_verified")},
                {"mismatches": kyc_data.get("mismatches"), "red_flags": kyc_data.get("red_flags"), "explanation": kyc_data.get("llm_explanation")},
                {"status": kyc_data.get("kyc_status"), "confidence": kyc_data.get("kyc_confidence")}
            )

            # Financial Step
            fin_data = state.get("financial_eligibility", {})
            add_step("financial",
                {"reported_income": app.get("personal_details", {}).get("annualIncome")},
                {"rule_findings": fin_data.get("rule_findings")},
                {"status": fin_data.get("eligibility_status"), "risk_score": fin_data.get("risk_score")}
            )

            # Health Step
            health_data = state.get("health_underwriting", {})
            add_step("health",
                {"bmi": health_data.get("bmi"), "conditions": len(health_data.get("identified_conditions", []))},
                {"exam_reasons": health_data.get("exam_reasons")},
                {"risk_score": health_data.get("risk_score"), "medical_exam_required": health_data.get("medical_exam_required")}
            )

            # Decision Step
            add_step("decision",
                {"aggregated_scores": {"health": health_data.get("risk_score"), "financial": fin_data.get("risk_score")}},
                {"reasons": decision.get("reasons")},
                {"decision": decision.get("decision"), "final_score": decision.get("final_score")}
            )

            # Save to 'result' collection
            result_doc = {
                "application_id": app_id,
                "timestamp": datetime.now().isoformat(),
                "overall_status": decision.get("decision", "Unknown"),
                "steps": structured_steps
            }
            db["result"].insert_one(result_doc)
            print(f"✅ Saved structured trace to 'result' collection for App ID: {app_id}")
            
    except Exception as e:
        print(f"⚠️ Failed to save result to MongoDB: {e}")

    return {"underwriting_report": out}
