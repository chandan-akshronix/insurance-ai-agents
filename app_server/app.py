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

@app.post("/underwrite")
async def underwrite_application(application_id: str = Body(..., embed=True)):
    """
    Trigger the insurance underwriting workflow for a given application ID.
    """
    logging.info(f"Received underwriting request for ID: {application_id}")
    
    # Initialize state
    initial_state = {"application_id": application_id}
    
    # Invoke the graph
    final_state = await insurance_graph.ainvoke(initial_state)
    
    # Return relevant parts of the state
    return {
        "status": "completed",
        "decision": final_state.get("policy_decision"),
        "report": final_state.get("underwriting_report"),
        "details": {
            "ingest": final_state.get("ingest_llm"),
            "document_processing": final_state.get("document_processing"),
            "kyc": final_state.get("kyc_reconciliation"),
            "health": final_state.get("health_underwriting"),
            "occupation": final_state.get("occupation_risk"),
            "financial": final_state.get("financial_eligibility"),
            "insurance_history": final_state.get("insurance_history"),
            "medical_exam": final_state.get("medical_exam_workflow")
        }
    }
