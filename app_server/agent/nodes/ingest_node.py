import json
from app_server.agent.state import AgentState
from app_server.utils.clients import azure_client, AZURE_DEPLOYMENT_NAME, db
from app_server.utils.helpers import fetch_application_from_mongodb
from app_server.agent.models import IngestOutput
from app_server.agent.prompts import INGEST_PROMPT

def ingest_node(state: AgentState):
    print("--- Ingest Node ---")
    if "application" not in state or not state.get("application"):
        application_id = state.get("application_id")
        if not application_id:
             # Fallback if no ID provided
             pass 
        else:
            try:
                app = fetch_application_from_mongodb(application_id=application_id)
                if not app:
                    print(f"❌ Error: Application {application_id} not found in MongoDB.")
                    # We could raise an error here or handle it gracefully. 
                    # For now, we'll set an error flag in the state.
                    state["error"] = f"Application {application_id} not found"
                    state["application"] = {}
                else:
                    state["application"] = app
            except Exception as e:
                print(f"❌ Error fetching application from MongoDB: {e}")
                state["error"] = f"MongoDB fetch error: {str(e)}"
                state["application"] = {}

    app = state.get("application", {})
    
    # Define required fields for insurance application
    required_fields = {
        "personal_details": ["fullName", "dob", "address", "panNumber", "occupation", "annualIncome"],
        "contact_info": ["phone", "email"],
        "health_info": ["weight", "height", "tobacco_consumption"],
        "coverage_selection": ["coverageAmount", "term", "selectedPlan"],
        "nominee_details": ["name", "relation", "dob"],
        "payment": ["method", "status"]
    }

    # Validate presence of required fields
    validation_issues = []
    for section, fields in required_fields.items():
        if section not in app:
            validation_issues.append(f"Missing section: {section}")
        else:
            for field in fields:
                if field not in app[section]:
                    validation_issues.append(f"Missing field: {section}.{field}")

    prompt = INGEST_PROMPT.format(application_json=json.dumps(app))

    try:
        resp = azure_client.beta.chat.completions.parse(
            model=AZURE_DEPLOYMENT_NAME,
            messages=[{"role": "user", "content": prompt}],
            response_format=IngestOutput,
            temperature=0.0
        )
        parsed_output = resp.choices[0].message.parsed
        # Convert Pydantic model to dict for state storage
        out = parsed_output.model_dump()
    except Exception as e:
        print(f"❌ Error in Ingest LLM: {e}")
        out = {"error": str(e), "normalized_application": app}

    # Include manual validation issues
    if isinstance(out, dict) and validation_issues:
        out["manual_validation_issues"] = validation_issues
        # Ensure validated is False if there are manual issues
        if validation_issues:
             out["validated"] = False

    state["normalized_by_llm"] = out.get("normalized_application", out)
    state["ingest_llm"] = out
    return state
