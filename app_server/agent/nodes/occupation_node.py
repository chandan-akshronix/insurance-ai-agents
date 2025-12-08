import json
from app_server.agent.state import AgentState
from app_server.utils.clients import azure_client, AZURE_DEPLOYMENT_NAME
from app_server.agent.models import OccupationOutput
from app_server.agent.prompts import OCCUPATION_PROMPT

def occupation_node(state: AgentState):
    print("--- Occupation Node ---")
    occ = state.get("normalized_by_llm", {}).get("occupation_details", {})
    
    # Check documents for employment details
    doc_processing = state.get("document_processing", {})
    ocr_results = doc_processing.get("results", {})
    
    employment_proofs = []
    for doc_key, result in ocr_results.items():
        ocr = result.get("ocr_result", {})
        extracted = ocr.get("extracted_data", {})
        
        # Check if it's a salary slip or employment proof
        doc_type_candidates = [
            ocr.get("specific_type", ""),
            extracted.get("document_type", ""),
            result.get("document_type", "")
        ]
        is_employment_doc = any("salary" in str(c).lower() or "employment" in str(c).lower() for c in doc_type_candidates)
        
        if is_employment_doc:
            employer = extracted.get("employer_name")
            if employer:
                employment_proofs.append(f"Document '{doc_key}' indicates Employer: {employer}")
                
                # Cross-verify with application
                app_employer = occ.get("employerName", "")
                if app_employer and employer.lower() not in app_employer.lower() and app_employer.lower() not in employer.lower():
                     employment_proofs.append(f"⚠️ Mismatch: Document employer '{employer}' does not match Application employer '{app_employer}'")

    prompt = OCCUPATION_PROMPT.format(occupation_info=json.dumps(occ))
    
    if employment_proofs:
        prompt += "\n\nVerified Employment Details from Documents:\n" + "\n".join(employment_proofs)

    try:
        resp = azure_client.beta.chat.completions.parse(
            model=AZURE_DEPLOYMENT_NAME,
            messages=[{"role": "user", "content": prompt}],
            response_format=OccupationOutput,
            temperature=0.0
        )
        parsed_output = resp.choices[0].message.parsed
        occ_result = parsed_output.model_dump()
    except Exception as e:
        print(f"❌ Error in Occupation LLM: {e}")
        occ_result = {
            "risk_score": 50, 
            "risk_category": "Medium", 
            "recommendation": f"Manual Review (Error: {str(e)})"
        }

    return {"occupation_risk": occ_result}
