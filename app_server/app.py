from fastapi import FastAPI, Body
from fastapi.responses import StreamingResponse
from app_server.agent.insurance_graph import insurance_graph
import logging
import sys
import json
import os

os.environ['SSL_CERT_FILE'] = './ca-bundle.crt'
logging.basicConfig(level=logging.INFO, stream=sys.stderr)

app = FastAPI()


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
        "report": final_state.get("underwriting_report")
    }
