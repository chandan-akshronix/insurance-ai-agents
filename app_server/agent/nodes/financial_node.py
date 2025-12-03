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
    
    # If we have an error from MCP, return it
    if "error" in mcp_financial:
        return {"financial_eligibility": {
            "status": "error",
            "error": mcp_financial.get("error"),
            "source": "MCP"
        }}
    
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
    
    prompt = FINANCIAL_PROMPT.format(
        financial_info=json.dumps(fin),
        mcp_data=json.dumps(mcp_financial),
        policy_details=json.dumps(policy)
    )
    try:
        resp = azure_client.beta.chat.completions.parse(
            model=AZURE_DEPLOYMENT_NAME,
            messages=[{"role": "user", "content": prompt}],
            response_format=FinancialOutput,
            temperature=0.0
        )
        parsed_output = resp.choices[0].message.parsed
        out = parsed_output.model_dump()
        out["source"] = "MCP Financial Data"
    except Exception as e:
        print(f"❌ Error in Financial LLM: {e}")
        out = {
            "income_coverage_ratio": 0.0, 
            "risk_score": 50, 
            "eligibility_status": "Review", 
            "recommendation": f"Manual Review (Error: {str(e)})",
            "source": "MCP"
        }
    
    return {"financial_eligibility": out}
