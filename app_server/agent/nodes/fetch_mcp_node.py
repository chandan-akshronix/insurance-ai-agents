from datetime import datetime
from app_server.agent.state import AgentState
from app_server.utils.helpers import call_mcp_tool

def fetch_mcp_data_node(state: AgentState):
    print("--- Fetch MCP Data Node ---")
    app = state.get("normalized_by_llm", state.get("application", {}))
    pan_number = app.get("personal_details", {}).get("panNumber")
    
    if pan_number:
        # Sequential for simplicity in graph, can be parallelized
        hist = call_mcp_tool("insurance_history", pan_number)
        fin = call_mcp_tool("financial_eligibility", pan_number)
        
        return {
            "insurance_history_mcp": {"data": hist, "timestamp": datetime.now().isoformat()},
            "financial_eligibility_mcp": {"data": fin, "timestamp": datetime.now().isoformat()}
        }
    else:
        return {
            "insurance_history_mcp": {"error": "No PAN"},
            "financial_eligibility_mcp": {"error": "No PAN"}
        }
