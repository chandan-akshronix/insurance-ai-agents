from fastapi import FastAPI, Body
from fastapi.responses import StreamingResponse
from app_server.agent.insurance_graph import insurance_graph
import logging
import sys
import json
import os

os.environ['SSL_CERT_FILE'] = './ca-bundle.crt'
logging.basicConfig(level=logging.INFO, stream=sys.stderr)

from fastapi import FastAPI, Body, Request
from fastapi.responses import JSONResponse
import traceback

app = FastAPI()

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    error_msg = str(exc)
    tb = traceback.format_exc()
    logging.error(f"Global Exception: {error_msg}\n{tb}")
    return JSONResponse(
        status_code=500,
        content={"message": "Internal Server Error", "detail": error_msg, "traceback": tb}
    )


@app.get("/")
def root():
    return {"message": "Server is running"}

@app.get("/health")
def health_check():
    """ Health check endpoint """
    return {"status": "ok"}

from pydantic import BaseModel
from typing import Optional

@app.post("/underwrite")
async def underwrite_application(application_id: str = Body(..., embed=True)):
    """
    Trigger the insurance underwriting workflow for a given application ID.
    """
    logging.info(f"Received underwriting request for ID: {application_id}")
    
    # Initialize state
    initial_state = {"application_id": application_id}
    
    # Config for persistence
    config = {"configurable": {"thread_id": application_id}}
    
    # Invoke the graph
    # It will pause before 'report' node due to interrupt_before
    try:
        final_state = await insurance_graph.ainvoke(initial_state, config=config)
        logging.info(f"Graph execution finished. Keys in final_state: {list(final_state.keys())}")
    except Exception as e:
        logging.error(f"Graph execution failed: {e}")
        raise e
    
    # Check if we are paused at the decision
    decision_data = final_state.get("policy_decision", {})
    decision = decision_data.get("decision")
    
    status = "completed"
    message = "Workflow completed successfully."
    
    # Check if we are paused
    # We use get_state to see the next steps. If next is 'report', we are paused.
    current_state_snapshot = await insurance_graph.aget_state(config)
    next_steps = current_state_snapshot.next
    
    if next_steps and "report" in next_steps:
        status = "paused_for_review"
        message = "Workflow paused for manual review. Call /approve to proceed."
        logging.info("Workflow paused at 'report' node.")
    else:
        logging.info(f"Workflow did NOT pause. Next steps: {next_steps}")

    # Return relevant parts of the state
    from app_server.utils.ui_mapper import map_state_to_ui_timeline
    
    return {
        "status": status,
        "message": message,
        "thread_id": application_id,
        "decision": decision_data,
        "audit_trail": {
            "ingest": {
                "status": "Validated" if final_state.get("ingest_llm", {}).get("validated") else "Issues Found",
                "validation_issues": final_state.get("ingest_llm", {}).get("manual_validation_issues", []),
                "data": final_state.get("ingest_llm")
            },
            "document_processing": final_state.get("document_processing"),
            "kyc": {
                "status": final_state.get("kyc_reconciliation", {}).get("kyc_status"),
                "document_classification": final_state.get("kyc_reconciliation", {}).get("document_classification", {}),
                "data": final_state.get("kyc_reconciliation")
            },
            "health": {
                "risk_score": final_state.get("health_underwriting", {}).get("risk_score"),
                "medical_exam_required": final_state.get("health_underwriting", {}).get("medical_exam_required"),
                "rule_findings": [r for r in final_state.get("health_underwriting", {}).get("exam_reasons", []) if "Limit" in r],
                "data": final_state.get("health_underwriting")
            },
            "financial": {
                "risk_score": final_state.get("financial_eligibility", {}).get("risk_score"),
                "rule_findings": final_state.get("financial_eligibility", {}).get("rule_findings", []),
                "data": final_state.get("financial_eligibility")
            },
            "occupation": final_state.get("occupation_risk"),
            "insurance_history": final_state.get("insurance_history"),
            "medical_exam": final_state.get("medical_exam_workflow")
        },
        "ui_visualization": map_state_to_ui_timeline(final_state)
    }

class ReviewAction(BaseModel):
    application_id: str
    action: str # "approve" | "reject" | "override"
    override_notes: Optional[str] = None

@app.post("/approve")
async def approve_application(review: ReviewAction):
    """
    Resume the workflow after manual review.
    """
    logging.info(f"Received approval request for ID: {review.application_id}, Action: {review.action}")
    
    config = {"configurable": {"thread_id": review.application_id}}
    
    # 1. Update the state with human feedback if needed
    if review.action == "override" or review.action == "reject":
        new_decision = "Decline" if review.action == "reject" else "Manual Override"
        update = {
            "policy_decision": {
                "decision": new_decision,
                "reasons": [f"Human Reviewer Note: {review.override_notes or 'No notes provided'}"]
            }
        }
        await insurance_graph.aupdate_state(config, update)
    
    # 2. Resume the graph
    # Passing None as input resumes from the suspended state
    final_state = await insurance_graph.ainvoke(None, config=config)
    
    return {
        "status": "completed",
        "decision": final_state.get("policy_decision"),
        "report": final_state.get("underwriting_report")
    }

@app.get("/applications/pending")
async def get_pending_applications():
    """
    Get all applications waiting for manual review.
    """
    try:
        from app_server.utils.clients import db
        # Find all applications with status 'pending_review'
        cursor = db["life_insurance_applications"].find({"status": "pending_review"})
        applications = []
        for doc in cursor:
            doc["_id"] = str(doc["_id"])
            applications.append(doc)
            
        return {"count": len(applications), "applications": applications}
    except Exception as e:
        logging.error(f"Error fetching pending applications: {e}")
        return JSONResponse(status_code=500, content={"error": str(e)})
