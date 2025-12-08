import json
from datetime import datetime
from app_server.agent.state import AgentState
from app_server.utils.clients import azure_client, AZURE_DEPLOYMENT_NAME
from app_server.agent.models import FinancialOutput
from app_server.agent.prompts import FINANCIAL_PROMPT

def financial_node(state: AgentState):
    print("--- Financial Node ---")
    # Get the MCP financial data we already fetched
    mcp_financial = state.get("financial_eligibility_mcp", {})
    
    # If we have an error from MCP, check if we have documents to fall back on
    if "error" in mcp_financial:
        print(f"⚠️ MCP Financial Data failed: {mcp_financial.get('error')}. Attempting to recover using documents...")
        mcp_financial = {} # Reset to empty
    
    # Get other necessary data
    app = state.get("normalized_by_llm", state.get("application", {}))
    fin = app.get("financial_information", {})
    policy = app.get("policy_selection", {})
    personal = app.get("personal_details", {})
    
    # Calculate age from DOB if available
    age = None
    if personal.get("dob"):
        try:
            birth_date = datetime.strptime(personal["dob"], "%Y-%m-%d")
            age = (datetime.now() - birth_date).days // 365
        except:
            pass
    
    # --- Precision Underwriting Rules ---
    
    # 1. Calculate TRSA (Total Rated Sum Assured)
    current_sa = float(policy.get("coverageAmount", 0))
    # Assuming insurance_history has previous policies sum
    history = state.get("insurance_history", {})
    # Extract previous cover from history if available (this is a simplification, ideally we parse it)
    # For now, we'll assume 0 if not explicitly found
    previous_cover = 0 
    trsa = current_sa + previous_cover
    
    # 2. Income Proof Check
    # Rule: TRSA > 25L (General) or > 40L (Preferred) requires Income Proof
    # We assume "General" business for now unless specified
    income_proof_required = False
    if trsa > 2500000:
        income_proof_required = True
        
    # --- Precision Underwriting: Document Income Verification ---
    from app_server.utils.helpers import parse_currency

    doc_processing = state.get("document_processing", {})
    ocr_results = doc_processing.get("results", {})
    
    verified_incomes = []
    income_proof_found = False
    
    financial_keywords = ["salary", "itr", "bank", "financial", "income", "payslip"]

    for doc_key, result in ocr_results.items():
        ocr = result.get("ocr_result", {})
        
        # Robust check for financial document
        is_financial = False
        if ocr.get("document_category") == "Financial":
            is_financial = True
        else:
            # Check specific type or extracted doc type
            extracted = ocr.get("extracted_data", {})
            doc_type_candidates = [
                ocr.get("specific_type", ""),
                extracted.get("document_type", ""),
                result.get("document_type", "") # From the input list
            ]
            for cand in doc_type_candidates:
                if cand and any(k in cand.lower() for k in financial_keywords):
                    is_financial = True
                    break
        
        if is_financial:
            income_proof_found = True
            extracted = ocr.get("extracted_data", {})
            # Robust parsing
            monthly = parse_currency(extracted.get("net_income"))
            if monthly > 0:
                verified_incomes.append(monthly * 12)
    
    # Calculate verified income (Average if multiple docs, e.g. 3 months payslips)
    verified_income = 0
    if verified_incomes:
        verified_income = sum(verified_incomes) / len(verified_incomes)
                
    # Check for Income Mismatch
    reported_income = float(fin.get("annualIncome") or 0)
    income_mismatch = False
    if verified_income > 0:
        # Allow 10% variance
        variance = abs(reported_income - verified_income) / verified_income
        if variance > 0.10:
            income_mismatch = True
            
    # 3. NRI Limits
    # Rule: Age < 45 -> Max 1.5 Cr
    nri_violation = False
    nationality = personal.get("nationality", "Indian")
    if nationality.lower() in ["nri", "pio", "oci"]:
        if age is not None and age <= 45 and trsa > 15000000:
            nri_violation = True
            
    # Prepare rule outputs
    rule_findings = []
    if income_proof_required:
        if not income_proof_found:
            rule_findings.append(f"TRSA ({trsa/100000}L) exceeds 25L limit. Income Proof is MISSING.")
        else:
            rule_findings.append(f"Income Proof Provided. Verified Annual Income: {verified_income}")
            
    if income_mismatch:
        rule_findings.append(f"Income Mismatch Detected! Reported: {reported_income}, Verified: {verified_income}. Variance: {variance:.0%}")

    if nri_violation:
        rule_findings.append(f"TRSA ({trsa/10000000}Cr) exceeds NRI limit of 1.5Cr for Age <= 45.")
        
    # Pass these findings to the LLM prompt
    prompt = FINANCIAL_PROMPT.format(
        financial_info=json.dumps(fin),
        mcp_data=json.dumps(mcp_financial),
        policy_details=json.dumps(policy)
    )
    
    # Append rule findings to the prompt to guide the LLM
    if rule_findings:
        prompt += "\n\nIMPORTANT UNDERWRITING RULES TRIGGERED:\n" + "\n".join(rule_findings)
        prompt += "\n\nYou MUST factor these rules into your decision. If Income Proof is mandatory and missing, flag it."

    try:
        resp = azure_client.beta.chat.completions.parse(
            model=AZURE_DEPLOYMENT_NAME,
            messages=[{"role": "user", "content": prompt}],
            response_format=FinancialOutput,
            temperature=0.0
        )
        parsed_output = resp.choices[0].message.parsed
        out = parsed_output.model_dump()
        out["source"] = "MCP Financial Data + Rules Engine"
        out["rule_findings"] = rule_findings # Add to output for transparency
        
        # Hard override if NRI violation
        if nri_violation:
            out["eligibility_status"] = "Ineligible"
            out["recommendation"] = "Decline: Exceeds NRI Coverage Limits."
            out["risk_score"] = 100
            
    except Exception as e:
        print(f"❌ Error in Financial LLM: {e}")
        out = {
            "income_coverage_ratio": 0.0, 
            "risk_score": 50, 
            "eligibility_status": "Review", 
            "recommendation": f"Manual Review (Error: {str(e)})",
            "source": "MCP",
            "rule_findings": rule_findings
        }
    
    return {"financial_eligibility": out}
