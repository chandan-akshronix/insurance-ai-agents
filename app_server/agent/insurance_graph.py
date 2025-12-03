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

workflow.add_edge("ingest", "document_processing")
workflow.add_edge("ingest", "fetch_mcp")
workflow.add_edge("ingest", "health")
workflow.add_edge("ingest", "occupation")

# Branch A: Document Processing -> KYC
workflow.add_edge("document_processing", "kyc")
workflow.add_edge("kyc", "decision")

# Branch B: MCP -> Financial & Insurance History
workflow.add_edge("fetch_mcp", "financial")
workflow.add_edge("fetch_mcp", "insurance_history")
workflow.add_edge("financial", "decision")
workflow.add_edge("insurance_history", "decision")

# Branch C: Health -> Medical Exam
workflow.add_edge("health", "medical_exam")
workflow.add_edge("medical_exam", "decision")

# Branch D: Occupation
# workflow.add_edge("occupation", "decision") # Removed to ensure decision waits for longer branches

workflow.add_edge("decision", "report")
workflow.add_edge("report", END)

insurance_graph = workflow.compile()
