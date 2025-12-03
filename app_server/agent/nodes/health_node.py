import os
import json
from app_server.agent.state import AgentState
from app_server.utils.clients import azure_client, AZURE_DEPLOYMENT_NAME
from app_server.agent.models import HealthOutput
from app_server.agent.prompts import HEALTH_PROMPT

def health_node(state: AgentState):
    print("--- Health Node ---")
    app = state.get("normalized_by_llm", state.get("application", {}))
    health = app.get("health_info", app.get("health_information", {})) or {}
    
    # compute BMI locally if possible
    bmi = None
    try:
        weight = float(health.get("weight") or health.get("weight_kg") or 0)
        height_cm = float(health.get("height") or health.get("height_cm") or 0)
        if weight > 0 and height_cm > 0:
            bmi = round(weight / ((height_cm / 100.0) ** 2), 1)
    except Exception:
        bmi = None

    # Load underwriting guidelines
    guidelines_text = ""
    
    # Try to find the guidelines file relative to the project root
    # Assuming this file is in app_server/agent/nodes/
    project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
    possible_paths = [
        os.path.join(project_root, "insurance mcp", "underwriting_guidelines.txt"),
        os.path.join(project_root, "underwriting_guidelines.txt"),
        "underwriting_guidelines.txt"
    ]
    
    for p in possible_paths:
        try:
            if os.path.exists(p):
                with open(p, "r", encoding="utf-8", errors="ignore") as gf:
                    guidelines_text = gf.read()
                print(f"Loaded guidelines from: {p}")
                break
        except Exception as e:
            print(f"Error reading guidelines from {p}: {e}")
            continue

    if not guidelines_text:
        print("⚠️ Warning: underwriting_guidelines.txt not found. Using default guidelines.")
        guidelines_excerpt = "Standard underwriting guidelines apply. Check BMI, tobacco use, and medical history."
    else:
        guidelines_excerpt = (guidelines_text.replace("\n", " ")[:3000])

    prompt = HEALTH_PROMPT.format(
        health_info=json.dumps(health),
        bmi=bmi,
        guidelines=guidelines_excerpt
    )

    try:
        resp = azure_client.beta.chat.completions.parse(
            model=AZURE_DEPLOYMENT_NAME,
            messages=[{"role": "user", "content": prompt}],
            response_format=HealthOutput,
            temperature=0.0
        )
        parsed_output = resp.choices[0].message.parsed
        out = parsed_output.model_dump()
    except Exception as e:
        print(f"❌ Error in Health LLM: {e}")
        out = {
            "bmi": bmi, 
            "risk_score": 0.5, 
            "recommendation": f"Manual Review (Error: {str(e)})",
            "risk_factors": [],
            "medical_exam_required": True,
            "exam_type": "General Checkup",
            "exam_reasons": ["System Error during assessment"],
            "llm_explanation": str(e)
        }
        
    # ensure bmi present in output
    if isinstance(out, dict) and out.get("bmi") is None and bmi is not None:
        out["bmi"] = bmi
        
    return {"health_underwriting": out}
