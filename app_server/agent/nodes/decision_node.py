import json
from app_server.agent.state import AgentState
from app_server.utils.clients import azure_client, AZURE_DEPLOYMENT_NAME
from app_server.agent.config import UNDERWRITING_CONFIG
from app_server.agent.models import DecisionOutput
from app_server.agent.prompts import DECISION_PROMPT

def decision_node(state: AgentState):
    print("--- Decision Node ---")
    # Aggregate scores
    kyc = state.get("kyc_reconciliation", {})
    health = state.get("health_underwriting", {})
    fin = state.get("financial_eligibility", {})
    occ = state.get("occupation_risk", {})
    
    # Prepare data for the prompt
    risk_scores = {
        "kyc": kyc.get("confidence", 0), # This might need adjustment if confidence isn't a direct risk score
        "health": health.get("risk_score", 0),
        "financial": fin.get("risk_score", 0),
        "occupation": occ.get("risk_score", 0)
    }
    
    assessments = {
        "kyc": kyc,
        "health": health,
        "financial": fin,
        "occupation": occ
    }

    prompt = DECISION_PROMPT.format(
        risk_scores=json.dumps(risk_scores),
        assessments=json.dumps(assessments),
        config=json.dumps(UNDERWRITING_CONFIG)
    )

    try:
        resp = azure_client.beta.chat.completions.parse(
            model=AZURE_DEPLOYMENT_NAME,
            messages=[{"role": "user", "content": prompt}],
            response_format=DecisionOutput,
            temperature=0.0
        )
        parsed_output = resp.choices[0].message.parsed
        decision = parsed_output.model_dump()
        
        # Update MongoDB status
        from app_server.utils.clients import db
        from bson import ObjectId
        
        app_id = state.get("application_id")
        if app_id:
            status = "completed"
            if decision.get("decision") == "Manual Review":
                status = "pending_review"
            elif decision.get("decision") == "Decline":
                status = "rejected"
            elif decision.get("decision") == "Accept":
                status = "approved"
                
            try:
                db["life_insurance_applications"].update_one(
                    {"_id": ObjectId(app_id)},
                    {"$set": {"status": status, "policy_decision": decision}}
                )
                print(f"✅ Updated MongoDB status to: {status}")
            except Exception as db_err:
                print(f"⚠️ Failed to update MongoDB status: {db_err}")

    except Exception as e:
        print(f"❌ Error in Decision LLM: {e}")
        decision = {
            "decision": "Manual Review", 
            "final_score": 100.0, 
            "reasons": [f"System Error: {str(e)}"], 
            "conditions": []
        }
        
    return {"policy_decision": decision}
