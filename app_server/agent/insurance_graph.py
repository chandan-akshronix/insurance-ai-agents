from langgraph.graph import StateGraph, END
from app_server.agent.state import AgentState

# Import nodes
from app_server.agent.nodes.ingest_node import ingest_node
from app_server.agent.nodes.document_processing_node import document_processing_node
from app_server.agent.nodes.kyc_node import kyc_node
from app_server.agent.nodes.health_node import health_node
from app_server.agent.nodes.medical_exam_node import medical_exam_node
from app_server.agent.nodes.fetch_mcp_node import fetch_mcp_data_node
from app_server.agent.nodes.financial_node import financial_node
from app_server.agent.nodes.insurance_history_node import insurance_history_node
from app_server.agent.nodes.occupation_node import occupation_node
from app_server.agent.nodes.decision_node import decision_node
from app_server.agent.nodes.report_node import report_node

# --- Graph Construction ---

workflow = StateGraph(AgentState)

workflow.add_node("ingest", ingest_node)
workflow.add_node("document_processing", document_processing_node)
workflow.add_node("kyc", kyc_node)
workflow.add_node("health", health_node)
workflow.add_node("medical_exam", medical_exam_node)
workflow.add_node("fetch_mcp", fetch_mcp_data_node)
workflow.add_node("financial", financial_node)
workflow.add_node("insurance_history", insurance_history_node)
workflow.add_node("occupation", occupation_node)
workflow.add_node("decision", decision_node)
workflow.add_node("report", report_node)

workflow.set_entry_point("ingest")

# 1. Ingest -> Document Processing (Conditional)
# Check if ingest was successful before proceeding
def check_ingest_success(state: AgentState):
    if state.get("error"):
        print(f"⛔ Ingest failed with error: {state.get('error')}. Stopping workflow.")
        return "report"
    return "document_processing"

workflow.add_conditional_edges(
    "ingest",
    check_ingest_success,
    {
        "document_processing": "document_processing",
        "report": "report"
    }
)

# 2. Document Processing -> KYC (Sequential First)
# We run KYC first to fail fast if identity is not verified
workflow.add_edge("document_processing", "kyc")

# 3. KYC -> Parallel Branches (Conditional)
# If KYC fails, we stop. If passes, we fan out.
def check_kyc_outcome(state: AgentState):
    kyc_data = state.get("kyc_reconciliation", {})
    status = kyc_data.get("kyc_status", "").lower()
    
    # Fail fast on Rejected or High Risk
    if status == "rejected":
        print("⛔ KYC Rejected. Stopping workflow early.")
        return "report"
        
    # Otherwise proceed to parallel branches
    return ["fetch_mcp", "health", "occupation"]

workflow.add_conditional_edges(
    "kyc",
    check_kyc_outcome,
    {
        "fetch_mcp": "fetch_mcp",
        "health": "health",
        "occupation": "occupation",
        "report": "report"
    }
)

# Branch B: MCP -> Insurance History -> Financial -> Decision
workflow.add_edge("fetch_mcp", "insurance_history")
workflow.add_edge("insurance_history", "financial")
workflow.add_edge("financial", "decision")

# Branch C: Health -> Medical Exam -> Decision
workflow.add_edge("health", "medical_exam")
workflow.add_edge("medical_exam", "decision")

# Branch D: Occupation -> Decision
workflow.add_edge("occupation", "decision")

workflow.add_edge("decision", "report")
workflow.add_edge("report", END)

from langgraph.checkpoint.mongodb import MongoDBSaver
from app_server.utils.clients import MONGODB_URI
from pymongo import MongoClient
# from langgraph.checkpoint.memory import MemorySaver

# Initialize MongoDB Client and Checkpointer
# We use a separate synchronous client for the checkpointer because MongoDBSaver performs sync I/O in __init__
mongodb_client = MongoClient(MONGODB_URI)
checkpointer = MongoDBSaver(mongodb_client)
# checkpointer = MemorySaver()

insurance_graph = workflow.compile(
    checkpointer=checkpointer,
    interrupt_before=["report"]
)
