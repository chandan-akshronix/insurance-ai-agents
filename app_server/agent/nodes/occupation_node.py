import json
from app_server.agent.state import AgentState
from app_server.utils.clients import azure_client, AZURE_DEPLOYMENT_NAME
from app_server.agent.models import OccupationOutput
from app_server.agent.prompts import OCCUPATION_PROMPT

def occupation_node(state: AgentState):
    print("--- Occupation Node ---")
    occ = state.get("normalized_by_llm", {}).get("occupation_details", {})
    prompt = OCCUPATION_PROMPT.format(occupation_info=json.dumps(occ))

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
