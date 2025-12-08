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
    
    # --- Precision Underwriting: Document Classification ---
    # Standard Proofs: Passport, PAN, Driving License, Aadhaar
    # Non-Standard Proofs: Voter ID, Ration Card
    
    # Standard Proofs: Passport, PAN, Driving License, Aadhaar, UID
    # Non-Standard Proofs: Voter ID, Ration Card
    # We also allow generic "image" or "screenshot" if they contain valid ID keywords (handled by OCR check)
    
    standard_proofs = ["passport", "pan", "driving license", "aadhaar", "uid", "id card", "kyc"]
    non_standard_proofs = ["voter id", "ration card"]
    
    doc_classification = {}
    non_standard_flag = False
    
    for doc_key, extraction in ocr_extractions.items():
        # Look for document type in multiple places
        extracted_data = extraction.get("extracted_data", {})
        doc_type_candidates = [
            extracted_data.get("document_type", ""),
            extraction.get("specific_type", ""),
            extraction.get("document_type", "")
        ]
        
        # Use the first non-empty candidate
        doc_type_ocr = next((cand for cand in doc_type_candidates if cand), "").lower()
        
        classification = "Unknown"
        if any(sp in doc_type_ocr for sp in standard_proofs):
            classification = "Standard"
        elif any(nsp in doc_type_ocr for nsp in non_standard_proofs):
            classification = "Non-Standard"
            non_standard_flag = True
        else:
            # If unknown but filename indicates it might be valid (e.g. "WhatsApp Image..."), we can be lenient
            # or check if OCR extracted valid data despite "Unknown" type
            if extracted_data and (extracted_data.get("name") or extracted_data.get("id_number")):
                 classification = "Standard (Inferred)"
            else:
                 classification = "Unknown"
            
        doc_classification[doc_key] = {
            "type": doc_type_ocr,
            "classification": classification
        }

    prompt = f"""
You are a KYC reconciliation assistant. Compare user-supplied personal and nominee details with OCR-extracted data from submitted documents.
Analyze the extracted document data and form data to verify:
1. Name matching (exact or fuzzy match)
2. Date of Birth format and consistency
3. ID numbers (PAN, Aadhaar) if present in documents
4. Gender consistency
5. Overall document authenticity indicators

IMPORTANT:
- Check Document Classification: {json.dumps(doc_classification)}
- If "Non-Standard" proof is used, flag it as a potential risk factor.

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
- If Non-Standard proof is used -> Add to red_flags
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
        out["document_classification"] = doc_classification # Add for transparency
        
    except Exception as e:
        out = {"error": str(e)}
    
    return {"kyc_reconciliation": out}
