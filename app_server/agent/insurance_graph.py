import os
import json
import base64
import time
import threading
import requests
from typing import TypedDict, Annotated, List, Dict, Any, Optional
from datetime import datetime
from pymongo import MongoClient
from openai import AzureOpenAI
from langgraph.graph import StateGraph, END

from .config import UNDERWRITING_CONFIG, AZURE_CONFIG
from .medical_workflow import check_medical_exam_status, integrate_medical_findings_llm

# Initialize Clients
MONGODB_URI = os.getenv("MONGODB_URI")
mongo_client = MongoClient(MONGODB_URI)
db = mongo_client.insurance_ai

AZURE_OPENAI_ENDPOINT = os.getenv("AZURE_OPENAI_ENDPOINT")
AZURE_OPENAI_KEY = os.getenv("AZURE_OPENAI_KEY")
AZURE_DEPLOYMENT_NAME = os.getenv("AZURE_DEPLOYMENT_NAME", "gpt-4o")

client = AzureOpenAI(
    azure_endpoint=AZURE_OPENAI_ENDPOINT,
    api_key=AZURE_OPENAI_KEY,
    api_version=AZURE_CONFIG['api_version']
)

# --- Helper Functions ---

def safe_parse_json(text):
    import re
    text = re.sub(r"^```[a-zA-Z]*", "", text)
    text = re.sub(r"```$", "", text).strip()
    m = re.search(r"\{[\s\S]*\}", text)
    try:
        if m:
            return json.loads(m.group(0))
        return json.loads(text)
    except Exception:
        return {"raw": text}

def encode_image_to_b64(path):
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")

def fetch_application_from_mongodb(application_id: str, collection_name: str = "life_insurance_applications"):
    from bson import ObjectId
    
    def json_serial(obj):
        if isinstance(obj, (datetime, )):
            return obj.isoformat()
        elif isinstance(obj, ObjectId):
            return str(obj)
        raise TypeError(f"Type {type(obj)} not serializable")

    if not application_id:
        raise ValueError("Application ID is required")

    collection = db[collection_name]
    print(f"🔍 Fetching application with _id: {application_id}")

    try:
        app = collection.find_one({"_id": application_id})
        if not app and ObjectId.is_valid(application_id):
            app = collection.find_one({"_id": ObjectId(application_id)})

        if not app:
            raise ValueError(f"No application found with _id: {application_id}")

        app['_id'] = str(app['_id'])
        
        def make_serializable(obj):
            if isinstance(obj, dict):
                return {k: make_serializable(v) for k, v in obj.items()}
            elif isinstance(obj, list):
                return [make_serializable(v) for v in obj]
            else:
                return json_serial(obj) if isinstance(obj, (datetime, ObjectId)) else obj
                
        return make_serializable(app)
        
    except Exception as e:
        print(f"⚠️ Error fetching from MongoDB: {str(e)}")
        # Fallback to sample
        try:
            # Assuming running from app_server root or similar, adjust path if needed
            # For simplicity, we'll try a few paths or fail gracefully
            sample_path = os.path.join(os.path.dirname(__file__), '..', '..', 'agentic_ai', 'data', 'sample_application.json')
            if os.path.exists(sample_path):
                 with open(sample_path, 'r') as f:
                    return json.load(f)
        except:
            pass
        raise ValueError(f"Failed to fetch application: {str(e)}")

def call_mcp_tool(tool_name: str, pan_number: str, mcp_base_url: str = "http://localhost:9000") -> dict:
    try:
        mcp_url = os.getenv("MCP_SERVER_URL", mcp_base_url)
        tool_map = {
            "insurance_history": "insurance_history_tool",
            "financial_eligibility": "financial_eligibility",
        }
        mcp_tool_name = tool_map.get(tool_name)
        if not mcp_tool_name:
            return {"error": f"Unknown tool: {tool_name}"}
        
        api_base = os.getenv("INSURANCE_API_BASE", "http://localhost:8000")
        endpoint_map = {
            "insurance_history": f"{api_base}/insurance-history/{pan_number}",
            "financial_eligibility": f"{api_base}/financial-eligibility/{pan_number}",
        }
        
        url = endpoint_map.get(tool_name)
        if not url:
            return {"error": f"No endpoint found for tool: {tool_name}"}
        
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        return resp.json()
        
    except Exception as e:
        return {"error": str(e), "status": "failed"}

# --- State Definition ---

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

# --- Nodes ---

def ingest_node(state: AgentState):
    print("--- Ingest Node ---")
    if "application" not in state or not state.get("application"):
        application_id = state.get("application_id")
        if not application_id:
             # Fallback if no ID provided
             pass 
        else:
            app = fetch_application_from_mongodb(application_id=application_id)
            state["application"] = app or {}

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

    prompt = f"""
You are a data-normalizer assistant. Inspect the provided application JSON and normalize it properly.
Your role:
1) Check presence of required fields and report any missing ones.
2) For mobile numbers, normalize to format: +91XXXXXXXXXX
3) For dates (DOB), ensure ISO YYYY-MM-DD format
4) For state/addresses, ensure Title Case
5) Validate email format
6) Ensure numeric fields are proper numbers
7) Return a JSON object only with keys:
  - validated (boolean)
  - issues (list of short strings describing validation issues)
  - normalized_application (the input JSON with normalization applied where possible)
  - missing_fields (list of critically missing fields)
  - llm_explanation (1-2 sentence summary)

Do not include chain-of-thought, only the JSON.

Application JSON:
{json.dumps(app)}
"""
    try:
        resp = client.chat.completions.create(
            model=AZURE_DEPLOYMENT_NAME,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=1000,
            temperature=0.0,
            response_format={"type": "json_object"}
        )
        out = safe_parse_json(resp.choices[0].message.content)
    except Exception as e:
        out = {"error": str(e)}

    # Include manual validation issues
    if isinstance(out, dict) and validation_issues:
        out["manual_validation_issues"] = validation_issues
        out["validated"] = out.get("validated", False)

    state["normalized_by_llm"] = out.get("normalized_application", out)
    state["ingest_llm"] = out
    return state

def document_processing_node(state: AgentState):
    print("--- Document Processing Node ---")
    normalized_app = state.get("normalized_by_llm", state.get("application", {}))
    documents = normalized_app.get("documents", [])
    
    if not documents:
        out = {"ocr_status": "skipped", "reason": "no_documents_found"}
        state["document_processing"] = out
        return state
    
    def call_vision(image_path):
        try:
            # Check if it's a URL or local file
            if image_path.startswith(('http://', 'https://')):
                # For URLs, use URL directly in vision API
                prompt = """
You are a document extraction model. Extract the fields from PAN or Aadhaar document if visible. Return JSON only:
{ "document_type": "PAN|Aadhaar", "name":"", "father_name":"","gender":"","dob":"","id_number":"" }
If a field is not present, set it to null.
"""
                resp = client.chat.completions.create(
                    model=AZURE_DEPLOYMENT_NAME,
                    messages=[{
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt},
                            {"type": "image_url", "image_url": {"url": image_path}}
                        ]
                    }],
                    max_tokens=500,
                    temperature=0.0,
                    response_format={"type": "json_object"}
                )
            else:
                # For local files, encode to base64
                if os.path.exists(image_path):
                    img_b64 = encode_image_to_b64(image_path)
                    prompt = """
You are a document extraction model. Extract the fields from PAN or Aadhaar document if visible. Return JSON only:
{ "document_type": "PAN|Aadhaar", "name":"", "father_name":"","gender":"","dob":"","id_number":"" }
If a field is not present, set it to null.
"""
                    resp = client.chat.completions.create(
                        model=AZURE_DEPLOYMENT_NAME,
                        messages=[{
                            "role": "user",
                            "content": [
                                {"type": "text", "text": prompt},
                                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{img_b64}"}}
                            ]
                        }],
                        max_tokens=500,
                        temperature=0.0,
                        response_format={"type": "json_object"}
                    )
                else:
                    return {"error": "file_not_found", "path": image_path}
            
            out = safe_parse_json(resp.choices[0].message.content)
            return out
        except Exception as e:
            return {"error": str(e), "path": image_path}
    
    # Process each document
    results = {}
    for doc in documents:
        doc_type = doc.get("docType", "unknown")
        filename = doc.get("filename", "unknown")
        url = doc.get("url", "")
        
        if url:
            try:
                doc_key = f"{filename}_{doc_type}"
                results[doc_key] = {
                    "document_type": doc_type,
                    "filename": filename,
                    "url": url,
                    "ocr_result": call_vision(url)
                }
            except Exception as e:
                results[filename] = {"error": str(e)}
        else:
            results[filename] = {"error": "no_url_provided"}
    
    state["document_processing"] = {
        "ocr_status": "completed",
        "documents_processed": len(documents),
        "results": results
    }
    return state

def kyc_node(state: AgentState):
    print("--- KYC Node ---")
    normalized_app = state.get("normalized_by_llm", state.get("application", {}))
    doc_processing = state.get("document_processing", {})
    ocr_results = doc_processing.get("results", {})
    
    # Extract personal and nominee details from normalized application
    personal_details = normalized_app.get("personal_details", {})
    nominee_details = normalized_app.get("nominee_details", {})
    
    # Extract OCR data from all processed documents
    ocr_extractions = {}
    for doc_key, doc_result in ocr_results.items():
        if "ocr_result" in doc_result:
            ocr_extractions[doc_key] = doc_result["ocr_result"]
    
    prompt = f"""
You are a KYC reconciliation assistant. Compare user-supplied personal and nominee details with OCR-extracted data from submitted documents.
Analyze the extracted document data and form data to verify:
1. Name matching (exact or fuzzy match)
2. Date of Birth format and consistency
3. ID numbers (PAN, Aadhaar) if present in documents
4. Gender consistency
5. Overall document authenticity indicators

Return JSON only with keys:
{{
  "kyc_status": "Verified|Manual Review|Rejected",
  "kyc_confidence": 0.0-1.0,
  "personal_verification": {{
    "name_match": true/false,
    "dob_match": true/false,
    "id_match": true/false,
    "overall": "verified/needs_review/rejected"
  }},
  "nominee_verification": {{
    "name_match": true/false,
    "dob_match": true/false,
    "overall": "verified/needs_review/rejected"
  }},
  "mismatches": [{{"field":"", "form_value":"", "ocr_value":"", "severity":"high/medium/low"}}],
  "red_flags": [],
  "llm_explanation": "2-3 sentence summary of verification result"
}}

Application Personal Details:
{json.dumps(personal_details)}

Application Nominee Details:
{json.dumps(nominee_details)}

OCR Extracted Data from Documents:
{json.dumps(ocr_extractions)}

Decision rules:
- If names exactly match with documents -> high confidence (0.8-1.0)
- If fuzzy match on names -> medium confidence (0.6-0.8)
- If major mismatches found -> low confidence or Rejected
- If documents not readable -> Manual Review
- If no critical mismatches -> Verified
"""
    try:
        resp = client.chat.completions.create(
            model=AZURE_DEPLOYMENT_NAME,
            messages=[{"role":"user","content":prompt}],
            max_tokens=600,
            temperature=0.0,
            response_format={"type":"json_object"}
        )
        out = safe_parse_json(resp.choices[0].message.content)
        
        # Add source information
        out["documents_verified"] = len(ocr_extractions)
        out["source"] = "Document OCR + Form Data Reconciliation"
    except Exception as e:
        out = {"error": str(e)}
    
    state["kyc_reconciliation"] = out
    return state

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
    # In LangGraph structure, we might need to adjust path or use config
    # For now, we'll try to find it relative to current file or use a default
    possible_paths = [
        os.path.join("insurance mcp", "underwriting_guidelines.txt"),
        os.path.join("..", "insurance mcp", "underwriting_guidelines.txt"),
        os.path.join(os.path.dirname(__file__), "..", "..", "..", "insurance mcp", "underwriting_guidelines.txt")
    ]
    for p in possible_paths:
        try:
            p_norm = os.path.normpath(p)
            if os.path.exists(p_norm):
                with open(p_norm, "r", encoding="utf-8", errors="ignore") as gf:
                    guidelines_text = gf.read()
                break
        except Exception:
            continue

    guidelines_excerpt = (guidelines_text.replace("\n", " ")[:3000]) if guidelines_text else ""

    prompt = f"""
You are an underwriting assistant. Use the provided underwriting guidelines excerpt to decide if a medical examination is required and to estimate underwriting risk.
Instructions:
- Use the applicant's health information to compute BMI (if available) and estimate a risk_score between 0.0 and 1.0.
- Recommend one of: Accept | Manual Review | Decline
- Decide whether a medical examination is required (medical_exam_required: true/false). If required, provide the `exam_type` (e.g., ML1, ML3, ML5, ML9 etc. or a list of tests like MER,FBS,ECG) based on the guidelines' medical chart.
- Provide `exam_reasons` (list of brief reasons why medicals are required).
- Return JSON ONLY with keys: bmi, risk_score, recommendation, risk_factors (list), medical_exam_required (bool), exam_type (string or list), exam_reasons (list), llm_explanation (short).

Health JSON:
{json.dumps(health)}

Computed BMI (if calculable): {bmi}

Underwriting Guidelines Excerpt:
{guidelines_excerpt}

Rules to apply (these are suggestions; use guidelines excerpt to refine):
- BMI > 35: add 0.4 to score; BMI 30-35: add 0.2; BMI 25-30: add 0.1.
- Tobacco: +0.3; Alcohol (regular): +0.1; Narcotics: +0.4.
- Major cardiac history, angioplasty, bypass, cancer, chronic respiratory disease -> +0.3 to +0.5 and consider medicals.
- Any surgery or hospitalization in last 2 years -> consider medicals.
- If resulting risk_score >= 0.6 -> recommendation should be Manual Review or Decline (use your judgment with guidelines).

Return JSON only (no explanation beyond the llm_explanation field).
"""
    try:
        resp = client.chat.completions.create(
            model=AZURE_DEPLOYMENT_NAME,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=500,
            temperature=0.0,
            response_format={"type": "json_object"}
        )
        out = safe_parse_json(resp.choices[0].message.content)
    except Exception as e:
        out = {"error": str(e)}
        
    # ensure bmi present in output
    if isinstance(out, dict) and out.get("bmi") is None and bmi is not None:
        out["bmi"] = bmi
        
    state["health_underwriting"] = out
    
    # Check medical workflow
    state = check_medical_exam_status(state, db)
    return state

def fetch_mcp_data_node(state: AgentState):
    print("--- Fetch MCP Data Node ---")
    app = state.get("normalized_by_llm", state.get("application", {}))
    pan_number = app.get("personal_details", {}).get("panNumber")
    
    if pan_number:
        # Sequential for simplicity in graph, can be parallelized
        hist = call_mcp_tool("insurance_history", pan_number)
        fin = call_mcp_tool("financial_eligibility", pan_number)
        
        state["insurance_history_mcp"] = {"data": hist, "timestamp": datetime.now().isoformat()}
        state["financial_eligibility_mcp"] = {"data": fin, "timestamp": datetime.now().isoformat()}
    else:
        state["insurance_history_mcp"] = {"error": "No PAN"}
        state["financial_eligibility_mcp"] = {"error": "No PAN"}
        
    return state

def financial_node(state: AgentState):
    print("--- Financial Node ---")
    # Get the MCP financial data we already fetched
    mcp_financial = state.get("financial_eligibility_mcp", {})
    
    # If we have an error from MCP, return it
    if "error" in mcp_financial:
        state["financial_eligibility"] = {
            "status": "error",
            "error": mcp_financial.get("error"),
            "source": "MCP"
        }
        return state
    
    # Get other necessary data
    app = state.get("normalized_by_llm", state.get("application", {}))
    fin = app.get("financial_information", {})
    policy = app.get("policy_selection", {})
    personal = app.get("personal_details", {})
    
    # Calculate age from DOB if available
    age = None
    if personal.get("dob"):
        try:
            from datetime import datetime
            birth_date = datetime.strptime(personal["dob"], "%Y-%m-%d")
            age = (datetime.now() - birth_date).days // 365
        except:
            pass
    
    prompt = f"""
You are a financial eligibility engine. Given the applicant's financial data from MCP and application, compute:
- income_to_coverage_ratio
- risk_score (0-1) using age and occupation adjustments
- recommendation: Accept | Manual Review | Decline
Return JSON only with these keys.

MCP Financial Data:
{json.dumps(mcp_financial, indent=2)}

Application Financial Data:
{json.dumps(fin, indent=2)}

Policy Details:
{json.dumps(policy, indent=2)}

Applicant Age: {age if age else "Not specified"}

Rules:
1. Ideal max ratio depends on age: <30 ->25, 30-40->20, 40-50->15, >50->10
2. Self-employed or risky occupations add 0.1 to risk
3. Consider existing liabilities and assets from MCP data
4. Check income_to_sum_assured_ratio from MCP data if available
5. Higher risk if premium_to_income_ratio > 0.15
"""
    try:
        resp = client.chat.completions.create(
            model=AZURE_DEPLOYMENT_NAME,
            messages=[{"role":"user","content":prompt}],
            max_tokens=400,
            temperature=0.0,
            response_format={"type":"json_object"}
        )
        out = safe_parse_json(resp.choices[0].message.content)
        out["source"] = "MCP Financial Data"
    except Exception as e:
        out = {
            "status": "error",
            "error": str(e),
            "source": "MCP"
        }
    
    state["financial_eligibility"] = out
    return state

def insurance_history_node(state: AgentState):
    print("--- Insurance History Node ---")
    # Get the MCP insurance history data we already fetched
    mcp_history = state.get("insurance_history_mcp", {})
    
    # If we have an error from MCP, return it
    if "error" in mcp_history:
        state["insurance_history"] = {
            "status": "error",
            "error": mcp_history.get("error"),
            "source": "MCP"
        }
        return state
    
    # Get other necessary data
    app = state.get("normalized_by_llm", state.get("application", {}))
    personal = app.get("personal_details", {})
    fin = app.get("financial_information", {})
    
    prompt = f"""
You are an insurance history risk evaluator.
Analyze the applicant's existing insurance history from MCP and return JSON with:
- total_existing_coverage (sum of all active policies)
- risk_score (0.0–1.0)
- recommendation: Accept | Manual Review | Decline
- red_flags (list)
- llm_explanation (1-2 sentences)

MCP Insurance History:
{json.dumps(mcp_history, indent=2)}

Applicant Details:
{json.dumps(personal, indent=2)}

Financial Information:
{json.dumps(fin, indent=2)}

Rules:
1. If total coverage > 25× of annual income → Manual Review
2. If ≥2 active policies → +0.2 risk
3. If any rejection or claim history > 0 → +0.3 risk
4. Consider the underwritingFlag from MCP data
5. Higher risk if multiple claims or lapses in coverage
"""
    try:
        resp = client.chat.completions.create(
            model=AZURE_DEPLOYMENT_NAME,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=500,
            temperature=0.0,
            response_format={"type": "json_object"}
        )
        out = safe_parse_json(resp.choices[0].message.content)
        out["source"] = "MCP Insurance History"
    except Exception as e:
        out = {
            "status": "error",
            "error": str(e),
            "source": "MCP"
        }
    
    state["insurance_history"] = out
    return state

def occupation_node(state: AgentState):
    print("--- Occupation Node ---")
    occ = state.get("normalized_by_llm", {}).get("occupation_details", {})
    prompt = f"""
You are an occupation risk assessor. Given occupation_details JSON, return:
- risk_score (0-1)
- recommendation: Accept|Manual Review|Decline
- reasons (list)
Return JSON only.
Occupation JSON:
{json.dumps(occ)}
Rules:
- High risk industries: export, jewellery, real estate, scrap, shipping, stock broking, mining, aviation -> +0.3
- Self-employed -> +0.2
- Physical hazardous jobs -> +0.3
"""
    try:
        resp = client.chat.completions.create(
            model=AZURE_DEPLOYMENT_NAME,
            messages=[{"role":"user","content":prompt}],
            max_tokens=250,
            temperature=0.0,
            response_format={"type":"json_object"}
        )
        out = safe_parse_json(resp.choices[0].message.content)
    except Exception as e:
        out = {"error": str(e)}
        
    state["occupation_risk"] = out
    return state

def decision_node(state: AgentState):
    print("--- Decision Node ---")
    # Aggregate scores
    kyc = state.get("kyc_reconciliation", {})
    health = state.get("health_underwriting", {})
    fin = state.get("financial_eligibility", {})
    occ = state.get("occupation_risk", {})
    
    prompt = f"""
You are a senior underwriting decision engine. Combine the following component JSONs and produce:
- overall_risk_score (0-1) computed by weighting: kyc 0.1, health 0.4, financial 0.3, occupation 0.2
- final_decision: Accept | Manual Review | Decline (thresholds: <=0.3 accept, <=0.6 manual review, >0.6 decline)
- reasons: short bullet list of top 3 reasons
- ai_summary: 2-sentence human-readable explanation
Return JSON only with keys: overall_risk_score, final_decision, reasons (array), ai_summary
KYC JSON:
{json.dumps(kyc)}
Health JSON:
{json.dumps(health)}
Financial JSON:
{json.dumps(fin)}
Occupation JSON:
{json.dumps(occ)}
"""
    try:
        resp = client.chat.completions.create(
            model=AZURE_DEPLOYMENT_NAME,
            messages=[{"role":"user","content":prompt}],
            max_tokens=300,
            temperature=0.0,
            response_format={"type":"json_object"}
        )
        out = safe_parse_json(resp.choices[0].message.content)
    except Exception as e:
        out = {"error": str(e)}
        
    state["policy_decision"] = out
    return state

def report_node(state: AgentState):
    print("--- Report Node ---")
    from fpdf import FPDF
    out_dir = "reports"
    os.makedirs(out_dir, exist_ok=True)
    app = state.get("normalized_by_llm", state.get("application", {}))
    name = app.get("personal_details", {}).get("full_name", "Applicant")
    decision = state.get("policy_decision", {})
    
    # Generate report text using LLM
    prompt = f"""
You are a professional underwriting report writer. Write a concise 2-paragraph underwriting summary based on the following:
Application JSON:
{json.dumps(app, ensure_ascii=False)}
Final Decision JSON:
{json.dumps(decision, ensure_ascii=False)}
Return plain text (no JSON).
"""
    try:
        resp = client.chat.completions.create(
            model=AZURE_DEPLOYMENT_NAME,
            messages=[{"role":"user","content":prompt}],
            max_tokens=400,
            temperature=0.3
        )
        text = resp.choices[0].message.content.strip()
    except Exception as e:
        text = f"Error generating report text: {str(e)}"

    # Build PDF with Unicode support
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = os.path.join(out_dir, f"Underwriting_Report_{name.replace(' ', '_')}_{ts}.pdf")
    
    # Create PDF with Unicode support
    pdf = FPDF()
    pdf.add_page()
    pdf.set_auto_page_break(True, 15)
    
    # Add a Unicode-compatible font (DejaVuSans supports many Unicode characters including ₹)
    try:
        # Try to use DejaVuSans if available
        pdf.add_font('DejaVuSans', '', 'DejaVuSans.ttf', uni=True)
        pdf.set_font('DejaVuSans', '', 11)
    except:
        # Fall back to Arial Unicode MS if available
        try:
            pdf.add_font('Arial', '', 'arial.ttf', uni=True)
            pdf.set_font('Arial', '', 11)
        except:
            # Final fallback to standard font (may not support all Unicode chars)
            pdf.set_font('Arial', size=11)
    
    # Add header
    pdf.set_font('Arial', 'B', 14)
    pdf.cell(0, 8, "Underwriting Report", ln=True, align="C")
    pdf.ln(6)
    
    # Add main content with proper Unicode handling
    pdf.set_font('Arial', '', 11)
    
    # Replace Rupee symbol with 'Rs.' if the current font doesn't support it
    if '₹' in text and pdf.get_string_width('₹') == 0:
        text = text.replace('₹', 'Rs.')
    
    # Add multi-line text with proper encoding
    pdf.multi_cell(0, 6, text.encode('latin-1', 'replace').decode('latin-1') if pdf.font_family == 'Arial' else text)
    
    # Add footer
    pdf.ln(6)
    pdf.set_font('Arial', 'I', 9)
    pdf.cell(0, 6, f"Generated: {datetime.now().isoformat()}", ln=True)
    
    # Save the PDF
    pdf.output(path, 'F')
    
    out = {"report_path": path, "status": "success"}
    state["underwriting_report"] = out
    return state

# --- Graph Construction ---

workflow = StateGraph(AgentState)

workflow.add_node("ingest", ingest_node)
workflow.add_node("document_processing", document_processing_node)
workflow.add_node("kyc", kyc_node)
workflow.add_node("health", health_node)
workflow.add_node("fetch_mcp", fetch_mcp_data_node)
workflow.add_node("financial", financial_node)
workflow.add_node("insurance_history", insurance_history_node)
workflow.add_node("occupation", occupation_node)
workflow.add_node("decision", decision_node)
workflow.add_node("report", report_node)

workflow.set_entry_point("ingest")

workflow.add_edge("ingest", "document_processing")
workflow.add_edge("document_processing", "kyc")
workflow.add_edge("kyc", "health")
workflow.add_edge("health", "fetch_mcp")
workflow.add_edge("fetch_mcp", "financial")
workflow.add_edge("financial", "insurance_history")
workflow.add_edge("insurance_history", "occupation")
workflow.add_edge("occupation", "decision")
workflow.add_edge("decision", "report")
workflow.add_edge("report", END)

insurance_graph = workflow.compile()
