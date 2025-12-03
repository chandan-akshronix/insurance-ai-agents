import json
from app_server.agent.state import AgentState
from app_server.utils.clients import azure_client, AZURE_DEPLOYMENT_NAME
from app_server.agent.models import KYCOutput
from app_server.agent.prompts import KYC_PROMPT
from app_server.utils.helpers import safe_parse_json

def kyc_node(state: AgentState):
    print("--- KYC Node ---")
    normalized_app = state.get("normalized_by_llm", state.get("application", {}))
    doc_processing = state.get("document_processing", {})
    ocr_results = doc_processing.get("results", {})
    
    # Extract personal and nominee details from normalized application
    personal_details = normalized_app.get("personal_details", {})
    nominee_details = normalized_app.get("nominee_details", {})
    
    # Extract OCR data from all processed documents
    ocr_extractions = {}
    for doc_key, doc_result in ocr_results.items():
        if "ocr_result" in doc_result:
            ocr_extractions[doc_key] = doc_result["ocr_result"]
    
    prompt = f"""
You are a KYC reconciliation assistant. Compare user-supplied personal and nominee details with OCR-extracted data from submitted documents.
Analyze the extracted document data and form data to verify:
1. Name matching (exact or fuzzy match)
2. Date of Birth format and consistency
3. ID numbers (PAN, Aadhaar) if present in documents
4. Gender consistency
5. Overall document authenticity indicators

Return JSON only with keys:
{{
  "kyc_status": "Verified|Manual Review|Rejected",
  "kyc_confidence": 0.0-1.0,
  "personal_verification": {{
    "name_match": true/false,
    "dob_match": true/false,
    "id_match": true/false,
    "overall": "verified/needs_review/rejected"
  }},
  "nominee_verification": {{
    "name_match": true/false,
    "dob_match": true/false,
    "overall": "verified/needs_review/rejected"
  }},
  "mismatches": [{{"field":"", "form_value":"", "ocr_value":"", "severity":"high/medium/low"}}],
  "red_flags": [],
  "llm_explanation": "2-3 sentence summary of verification result"
}}

Application Personal Details:
{json.dumps(personal_details)}

Application Nominee Details:
{json.dumps(nominee_details)}

OCR Extracted Data from Documents:
{json.dumps(ocr_extractions)}

Decision rules:
- If names exactly match with documents -> high confidence (0.8-1.0)
- If fuzzy match on names -> medium confidence (0.6-0.8)
- If major mismatches found -> low confidence or Rejected
- If documents not readable -> Manual Review
- If no critical mismatches -> Verified
"""
    try:
        resp = azure_client.chat.completions.create(
            model=AZURE_DEPLOYMENT_NAME,
            messages=[{"role":"user","content":prompt}],
            max_tokens=600,
            temperature=0.0,
            response_format={"type":"json_object"}
        )
        out = safe_parse_json(resp.choices[0].message.content)
        
        # Add source information
        out["documents_verified"] = len(ocr_extractions)
        out["source"] = "Document OCR + Form Data Reconciliation"
    except Exception as e:
        out = {"error": str(e)}
    
    return {"kyc_reconciliation": out}
