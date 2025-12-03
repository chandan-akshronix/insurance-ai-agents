from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any

class IngestOutput(BaseModel):
    validated: bool = Field(..., description="Whether the application data is valid")
    issues: List[str] = Field(default_factory=list, description="List of validation issues found")
    normalized_application: Dict[str, Any] = Field(..., description="The normalized application data")
    missing_fields: List[str] = Field(default_factory=list, description="List of critical missing fields")
    llm_explanation: str = Field(..., description="Brief explanation of the normalization process")

class KYCOutput(BaseModel):
    status: str = Field(..., description="Verification status: 'verified', 'failed', or 'manual_review'")
    confidence: float = Field(..., description="Confidence score between 0.0 and 1.0")
    issues: List[str] = Field(default_factory=list, description="List of discrepancies or issues found")
    summary: str = Field(..., description="Summary of the KYC verification")

class HealthOutput(BaseModel):
    medical_exam_required: bool = Field(..., description="Whether a medical exam is required")
    reason: str = Field(..., description="Reason for requiring or not requiring a medical exam")
    risk_score: float = Field(..., description="Health risk score between 0 and 100")
    risk_category: str = Field(..., description="Risk category: 'Low', 'Medium', or 'High'")
    recommendation: str = Field(..., description="Underwriting recommendation based on health")

class FinancialOutput(BaseModel):
    income_coverage_ratio: float = Field(..., description="Calculated income to coverage ratio")
    risk_score: float = Field(..., description="Financial risk score between 0 and 100")
    eligibility_status: str = Field(..., description="Eligibility status: 'Eligible', 'Ineligible', or 'Review'")
    recommendation: str = Field(..., description="Financial underwriting recommendation")

class InsuranceHistoryOutput(BaseModel):
    risk_score: float = Field(..., description="Insurance history risk score between 0 and 100")
    policy_count: int = Field(..., description="Number of existing policies")
    claims_history: str = Field(..., description="Summary of claims history")
    recommendation: str = Field(..., description="Recommendation based on insurance history")

class OccupationOutput(BaseModel):
    risk_score: float = Field(..., description="Occupation risk score between 0 and 100")
    risk_category: str = Field(..., description="Risk category: 'Low', 'Medium', or 'High'")
    recommendation: str = Field(..., description="Recommendation based on occupation")

class DecisionOutput(BaseModel):
    decision: str = Field(..., description="Final decision: 'Accept', 'Decline', or 'Manual Review'")
    final_score: float = Field(..., description="Aggregated final risk score")
    reasons: List[str] = Field(..., description="List of reasons for the decision")
    conditions: List[str] = Field(default_factory=list, description="List of conditions if accepted")

class ReportOutput(BaseModel):
    summary: str = Field(..., description="Executive summary of the application")
    key_findings: List[str] = Field(..., description="List of key findings from the underwriting process")
    risk_assessment: str = Field(..., description="Detailed risk assessment narrative")
    recommendation_text: str = Field(..., description="Final recommendation narrative")
