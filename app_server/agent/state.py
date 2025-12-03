from typing import TypedDict, Dict, Any

class AgentState(TypedDict):
    application_id: str
    application: Dict[str, Any]
    normalized_by_llm: Dict[str, Any]
    ingest_llm: Dict[str, Any]
    document_processing: Dict[str, Any]
    kyc_reconciliation: Dict[str, Any]
    health_underwriting: Dict[str, Any]
    insurance_history_mcp: Dict[str, Any]
    financial_eligibility_mcp: Dict[str, Any]
    financial_eligibility: Dict[str, Any]
    insurance_history: Dict[str, Any]
    occupation_risk: Dict[str, Any]
    policy_decision: Dict[str, Any]
    underwriting_report: Dict[str, Any]
    medical_exam_workflow: Dict[str, Any]
    health_underwriting_with_medicals: Dict[str, Any]
