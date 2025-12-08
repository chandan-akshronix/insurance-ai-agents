import json
from app_server.agent.state import AgentState
from app_server.utils.clients import azure_client, AZURE_DEPLOYMENT_NAME
from app_server.agent.models import InsuranceHistoryOutput
from app_server.agent.prompts import INSURANCE_HISTORY_PROMPT

def insurance_history_node(state: AgentState):
    print("--- Insurance History Node ---")
    # Get the MCP insurance history data we already fetched
    mcp_history = state.get("insurance_history_mcp", {})
    
    # If we have an error from MCP, check if we have documents to fall back on
    if "error" in mcp_history:
        print(f"⚠️ MCP Insurance History failed: {mcp_history.get('error')}. Attempting to recover using documents...")
        mcp_history = {} # Reset to empty to avoid breaking downstream logic
    
    # Get other necessary data
    app = state.get("normalized_by_llm", state.get("application", {}))
    personal = app.get("personal_details", {})
    fin = app.get("financial_information", {})
    
    # --- Precision Underwriting: Document History Verification ---
    from app_server.utils.helpers import parse_currency
    
    doc_processing = state.get("document_processing", {})
    ocr_results = doc_processing.get("results", {})
    
    verified_previous_cover = 0
    policy_docs_found = 0
    
    for doc_key, result in ocr_results.items():
        ocr = result.get("ocr_result", {})
        if ocr.get("document_category") == "Insurance":
            policy_docs_found += 1
            extracted = ocr.get("extracted_data", {})
            
            # Robust parsing
            sa = parse_currency(extracted.get("sum_assured"))
            
            # Optional: Check if policy is active (based on start date)
            # For now, we just log it if found
            start_date = extracted.get("policy_start_date")
            
            if sa > 0:
                verified_previous_cover += sa
                
    prompt = INSURANCE_HISTORY_PROMPT.format(history_data=json.dumps(mcp_history))
    
    # Add document findings to prompt
    if policy_docs_found > 0:
        prompt += f"\n\nAdditional Information from Submitted Policy Documents:\nFound {policy_docs_found} policy documents. Total Verified Previous Cover: {verified_previous_cover}"
        if not mcp_history or "error" in mcp_history or len(mcp_history) == 0:
             prompt += "\nNOTE: MCP Data is unavailable. Please rely on the submitted documents to determine policy count and assume 'No Claims' unless evidence suggests otherwise."
        
    try:
        resp = azure_client.beta.chat.completions.parse(
            model=AZURE_DEPLOYMENT_NAME,
            messages=[{"role": "user", "content": prompt}],
            response_format=InsuranceHistoryOutput,
            temperature=0.0
        )
        parsed_output = resp.choices[0].message.parsed
        out = parsed_output.model_dump()
        out["source"] = "MCP Insurance History + Document Verification"
        out["verified_previous_cover"] = verified_previous_cover
        
        # Update claims history if docs show something (simplistic)
        if policy_docs_found > 0 and out.get("policy_count", 0) == 0:
             out["policy_count"] = policy_docs_found
             
    except Exception as e:
        print(f"❌ Error in Insurance History LLM: {e}")
        out = {
            "risk_score": 50, 
            "policy_count": policy_docs_found, 
            "claims_history": "Unknown", 
            "recommendation": f"Manual Review (Error: {str(e)})",
            "source": "MCP",
            "verified_previous_cover": verified_previous_cover
        }
    
    return {"insurance_history": out}
