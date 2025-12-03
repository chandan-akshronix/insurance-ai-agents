import json
from app_server.agent.state import AgentState
from app_server.utils.clients import azure_client, AZURE_DEPLOYMENT_NAME
from app_server.agent.models import InsuranceHistoryOutput
from app_server.agent.prompts import INSURANCE_HISTORY_PROMPT

def insurance_history_node(state: AgentState):
    print("--- Insurance History Node ---")
    # Get the MCP insurance history data we already fetched
    mcp_history = state.get("insurance_history_mcp", {})
    
    # If we have an error from MCP, return it
    if "error" in mcp_history:
        return {"insurance_history": {
            "status": "error",
            "error": mcp_history.get("error"),
            "source": "MCP"
        }}
    
    # Get other necessary data
    app = state.get("normalized_by_llm", state.get("application", {}))
    personal = app.get("personal_details", {})
    fin = app.get("financial_information", {})
    
    prompt = INSURANCE_HISTORY_PROMPT.format(history_data=json.dumps(mcp_history))
    try:
        resp = azure_client.beta.chat.completions.parse(
            model=AZURE_DEPLOYMENT_NAME,
            messages=[{"role": "user", "content": prompt}],
            response_format=InsuranceHistoryOutput,
            temperature=0.0
        )
        parsed_output = resp.choices[0].message.parsed
        out = parsed_output.model_dump()
        out["source"] = "MCP Insurance History"
    except Exception as e:
        print(f"❌ Error in Insurance History LLM: {e}")
        out = {
            "risk_score": 50, 
            "policy_count": 0, 
            "claims_history": "Unknown", 
            "recommendation": f"Manual Review (Error: {str(e)})",
            "source": "MCP"
        }
    
    return {"insurance_history": out}
