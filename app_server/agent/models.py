from pydantic import BaseModel, Field, ConfigDict
from typing import List, Optional, Dict, Any

class PersonalDetails(BaseModel):
    model_config = ConfigDict(extra="forbid")
    fullName: str = Field(..., description="Full Name of the applicant")
    dob: str = Field(..., description="Date of Birth in YYYY-MM-DD format")
    gender: Optional[str] = Field(None, description="Gender")
    address: Optional[str] = Field(None, description="Residential Address")
    panNumber: Optional[str] = Field(None, description="PAN Number")
    occupation: Optional[str] = Field(None, description="Occupation")
    annualIncome: Optional[str] = Field(None, description="Annual Income")

class ContactInfo(BaseModel):
    model_config = ConfigDict(extra="forbid")
    phone: Optional[str] = Field(None, description="Phone number")
    email: Optional[str] = Field(None, description="Email address")

class DocumentItem(BaseModel):
    model_config = ConfigDict(extra="forbid")
    filename: str = Field(..., description="Name of the file")
    url: str = Field(..., description="URL of the file")
    docType: str = Field(..., description="Type of document")
    documentId: Optional[int] = Field(None, description="Document ID")

class CoverageSelection(BaseModel):
    model_config = ConfigDict(extra="forbid")
    coverageAmount: float = Field(..., description="Sum Assured")
    term: int = Field(..., description="Policy Term")
    selectedPlan: str = Field(..., description="Selected Plan Name")

class HealthInfo(BaseModel):
    model_config = ConfigDict(extra="forbid")
    weight: Optional[str] = Field(None, description="Weight in kg")
    height: Optional[str] = Field(None, description="Height in cm")
    tobacco_consumption: bool = Field(..., description="Tobacco consumption status")
    alcohol_last_year: Optional[bool] = Field(None, description="Alcohol consumption")
    # Add other common health fields as optional to allow flexibility while being strict
    ever_consumed_narcotics: Optional[bool] = Field(None)
    hazardous_occupation_or_hobby: Optional[bool] = Field(None)
    employed_in_armed_forces_or_police: Optional[bool] = Field(None)
    prior_tests_investigations_or_surgery: Optional[bool] = Field(None)
    hypertension_high_bp_or_cholesterol: Optional[bool] = Field(None)
    chest_pain_heart_attack_or_heart_disease: Optional[bool] = Field(None)
    undergone_angioplasty_bypass_or_heart_surgery: Optional[bool] = Field(None)
    diabetes_or_related_complications: Optional[bool] = Field(None)
    respiratory_disorders_like_asthma_tb: Optional[bool] = Field(None)
    nervous_disorders_stroke_or_epilepsy: Optional[bool] = Field(None)
    gastrointestinal_disorders: Optional[bool] = Field(None)
    liver_disorders_or_hepatitis: Optional[bool] = Field(None)
    genitourinary_disorders: Optional[bool] = Field(None)
    history_of_cancer_or_tumour: Optional[bool] = Field(None)
    hiv_infection_or_positive_test: Optional[bool] = Field(None)
    anemia_or_blood_disorders: Optional[bool] = Field(None)
    psychiatric_illness: Optional[bool] = Field(None)
    other_disorder: Optional[bool] = Field(None)
    congenital_defects_or_physical_deformity: Optional[bool] = Field(None)
    family_history_hereditary_before_55: Optional[bool] = Field(None)
    ailment_or_injury_medical_leave_over_week_in_last_two_years: Optional[bool] = Field(None)
    weight_change_over_10kg_in_6_months: Optional[bool] = Field(None)

class NomineeDetails(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(..., description="Nominee Name")
    relation: str = Field(..., description="Relationship with applicant")
    dob: str = Field(..., description="Nominee DOB")
    contact: Optional[str] = Field(None, description="Nominee Contact")

class KYCVerification(BaseModel):
    model_config = ConfigDict(extra="forbid")
    policyholder: str = Field(..., description="KYC status of policyholder")
    nominee: str = Field(..., description="KYC status of nominee")

class PaymentDetails(BaseModel):
    model_config = ConfigDict(extra="forbid")
    method: str = Field(..., description="Payment method")
    status: str = Field(..., description="Payment status")
    paid_at: Optional[str] = Field(None, description="Payment timestamp")

class RiderItem(BaseModel):
    model_config = ConfigDict(extra="forbid")
    rider_id: str = Field(..., description="ID of the rider")
    name: Optional[str] = Field(None, description="Name of the rider")
    premium: Optional[float] = Field(None, description="Premium for the rider")

class NormalizedApplication(BaseModel):
    model_config = ConfigDict(extra="forbid")
    personal_details: PersonalDetails = Field(..., description="Personal details like name, dob, etc.")
    contact_info: ContactInfo = Field(..., description="Contact information")
    documents: List[DocumentItem] = Field(..., description="List of uploaded documents")
    coverage_selection: CoverageSelection = Field(..., description="Coverage details")
    health_info: HealthInfo = Field(..., description="Health questionnaire responses")
    nominee_details: NomineeDetails = Field(..., description="Nominee details")
    kyc_verification: KYCVerification = Field(..., description="KYC verification status")
    payment: PaymentDetails = Field(..., description="Payment details")
    # Add optional fields that might be present in the raw app
    user_id: Optional[str] = Field(None)
    status: Optional[str] = Field(None)
    policy: Optional[int] = Field(None)
    created_at: Optional[str] = Field(None)
    updated_at: Optional[str] = Field(None)
    riders: Optional[List[RiderItem]] = Field(None, description="List of selected riders")

class IngestOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    validated: bool = Field(..., description="Whether the application data is valid")
    issues: List[str] = Field(default_factory=list, description="List of validation issues found")
    normalized_application: NormalizedApplication = Field(..., description="The normalized application data")
    missing_fields: List[str] = Field(default_factory=list, description="List of critical missing fields")
    llm_explanation: str = Field(..., description="Brief explanation of the normalization process")

class KYCOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    status: str = Field(..., description="Verification status: 'verified', 'failed', or 'manual_review'")
    confidence: float = Field(..., description="Confidence score between 0.0 and 1.0")
    issues: List[str] = Field(default_factory=list, description="List of discrepancies or issues found")
    summary: str = Field(..., description="Summary of the KYC verification")

class HealthOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    medical_exam_required: bool = Field(..., description="Whether a medical exam is required")
    reason: str = Field(..., description="Reason for requiring or not requiring a medical exam")
    risk_score: float = Field(..., description="Health risk score between 0 and 100")
    risk_category: str = Field(..., description="Risk category: 'Low', 'Medium', or 'High'")
    recommendation: str = Field(..., description="Underwriting recommendation based on health")

class FinancialOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    income_coverage_ratio: float = Field(..., description="Calculated income to coverage ratio")
    risk_score: float = Field(..., description="Financial risk score between 0 and 100")
    eligibility_status: str = Field(..., description="Eligibility status: 'Eligible', 'Ineligible', or 'Review'")
    recommendation: str = Field(..., description="Financial underwriting recommendation")

class InsuranceHistoryOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    risk_score: float = Field(..., description="Insurance history risk score between 0 and 100")
    policy_count: int = Field(..., description="Number of existing policies")
    claims_history: str = Field(..., description="Summary of claims history")
    recommendation: str = Field(..., description="Recommendation based on insurance history")

class OccupationOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    risk_score: float = Field(..., description="Occupation risk score between 0 and 100")
    risk_category: str = Field(..., description="Risk category: 'Low', 'Medium', or 'High'")
    recommendation: str = Field(..., description="Recommendation based on occupation")

class DecisionOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    decision: str = Field(..., description="Final decision: 'Accept', 'Decline', or 'Manual Review'")
    final_score: float = Field(..., description="Aggregated final risk score")
    reasons: List[str] = Field(..., description="List of reasons for the decision")
    conditions: List[str] = Field(default_factory=list, description="List of conditions if accepted")

class ReportOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    summary: str = Field(..., description="Executive summary of the application")
    key_findings: List[str] = Field(..., description="List of key findings from the underwriting process")
    risk_assessment: str = Field(..., description="Detailed risk assessment narrative")
    recommendation_text: str = Field(..., description="Final recommendation narrative")
