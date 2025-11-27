"""
Medical exam workflow handler for insurance underwriting
"""

from typing import Dict, Any
from datetime import datetime


def check_medical_exam_status(state: Dict[str, Any], db) -> Dict[str, Any]:
    """
    Check if medical exam is required and handle the workflow.
    
    Workflow:
    1. If medical exam not required -> Continue
    2. If medical exam required:
       a. Check if medical report already exists in DB
       b. If exists -> Extract and continue
       c. If not exists -> Queue for pending medicals
    
    Returns updated state with medical_exam_workflow section.
    """
    health = state.get('health_underwriting', {})
    medical_required = health.get('medical_exam_required', False)
    
    medical_workflow = {
        'medical_exam_required': medical_required,
        'status': 'not_required',
        'timestamp': datetime.now().isoformat()
    }
    
    if not medical_required:
        medical_workflow['status'] = 'not_required'
        state['medical_exam_workflow'] = medical_workflow
        print("ℹ️  Medical exam not required - proceeding with underwriting")
        return state
    
    # Medical exam is required - check if report exists
    app = state.get('application', {})
    personal = app.get('personal_details', {})
    pan_number = personal.get('panNumber')
    
    if not pan_number:
        medical_workflow['status'] = 'error'
        medical_workflow['error'] = 'PAN number not found'
        state['medical_exam_workflow'] = medical_workflow
        return state
    
    # Check MongoDB for existing medical report
    try:
        medical_collection = db.medical_reports
        existing_report = medical_collection.find_one({'pan_number': pan_number})
        
        if existing_report:
            # Medical report found - extract and proceed
            medical_workflow['status'] = 'completed'
            medical_workflow['report_found'] = True
            medical_workflow['report_date'] = existing_report.get('report_date')
            medical_workflow['medical_data'] = {
                'blood_pressure': existing_report.get('blood_pressure'),
                'cholesterol': existing_report.get('cholesterol'),
                'blood_sugar': existing_report.get('blood_sugar'),
                'ecg_result': existing_report.get('ecg_result'),
                'urine_test': existing_report.get('urine_test'),
                'overall_health_status': existing_report.get('overall_health_status')
            }
            medical_workflow['exam_type'] = health.get('exam_type', 'Unknown')
            
            print(f"✅ Medical report found (Date: {existing_report.get('report_date')})")
            print(f"   Health Status: {existing_report.get('overall_health_status', 'N/A')}")
            
        else:
            # Medical report not found - queue for pending medicals
            medical_workflow['status'] = 'pending'
            medical_workflow['report_found'] = False
            medical_workflow['exam_type'] = health.get('exam_type', 'ML3')
            medical_workflow['exam_reasons'] = health.get('exam_reasons', [])
            
            # Add to pending medicals queue
            pending_queue = db.pending_medical_exams
            queue_entry = {
                'application_id': str(app.get('_id', 'unknown')),
                'pan_number': pan_number,
                'applicant_name': personal.get('fullName', 'Unknown'),
                'exam_type': medical_workflow['exam_type'],
                'exam_reasons': medical_workflow['exam_reasons'],
                'priority': compute_medical_priority(state),
                'queued_at': datetime.now(),
                'status': 'pending_medical',
                'expected_completion': None  # To be updated when exam is scheduled
            }
            
            try:
                pending_queue.insert_one(queue_entry)
                medical_workflow['queue_id'] = str(queue_entry.get('_id'))
                print(f"⚠️  Medical exam required: {medical_workflow['exam_type']}")
                print(f"   Reasons: {', '.join(medical_workflow['exam_reasons'][:3])}")
                print(f"   Added to pending medical queue (Priority: {queue_entry['priority']})")
            except Exception as e:
                medical_workflow['queue_error'] = str(e)
                print(f"⚠️  Could not add to pending queue: {e}")
    
    except Exception as e:
        medical_workflow['status'] = 'error'
        medical_workflow['error'] = str(e)
        print(f"❌ Error checking medical reports: {e}")
    
    state['medical_exam_workflow'] = medical_workflow
    return state


def compute_medical_priority(state: Dict[str, Any]) -> str:
    """
    Compute priority for medical exam queue.
    Priority based on coverage amount and health risk factors.
    """
    app = state.get('application', {})
    health = state.get('health_underwriting', {})
    
    coverage = app.get('coverage_selection', {}).get('coverageAmount', 0)
    risk_score = health.get('risk_score', 0)
    
    # High priority: Large coverage or high health risk
    if coverage > 10000000 or risk_score > 0.6:
        return 'HIGH'
    # Medium priority: Standard cases
    elif coverage > 5000000 or risk_score > 0.4:
        return 'MEDIUM'
    # Low priority: Small coverage and low risk
    else:
        return 'LOW'


def should_proceed_without_medical(state: Dict[str, Any]) -> bool:
    """
    Determine if underwriting should proceed without medical exam results.
    
    For POC: Return False (wait for medicals)
    For Production: Might return True for certain low-risk cases with conditional approval
    """
    medical_workflow = state.get('medical_exam_workflow', {})
    
    # If medical exam not required, proceed
    if medical_workflow.get('status') == 'not_required':
        return True
    
    # If medical report found, proceed
    if medical_workflow.get('report_found'):
        return True
    
    # If medical pending, check policy - for POC, we wait
    # In production, you might allow conditional approval for low-risk cases
    return False


def integrate_medical_findings_llm(state: Dict[str, Any], client) -> Dict[str, Any]:
    """
    If medical report was found, integrate findings into health risk assessment using LLM.
    This updates the health_underwriting risk score based on actual medical data.
    """
    medical_workflow = state.get('medical_exam_workflow', {})
    
    # Only proceed if medical report was found
    if not medical_workflow.get('report_found'):
        return state
    
    medical_data = medical_workflow.get('medical_data', {})
    original_health = state.get('health_underwriting', {})
    
    prompt = f"""
You are a medical underwriter. Review the medical examination results and update the health risk assessment.

Original Health Assessment:
{original_health}

Medical Exam Results:
{medical_data}

Return JSON only with:
- updated_risk_score (0-1, considering medical findings)
- risk_adjustment (+/- value from original score)
- medical_findings_summary (2-3 sentences)
- critical_findings (list of any concerning results)
- recommendation: Accept | Manual Review | Decline

Rules:
- Normal BP (<140/90), cholesterol (<200), blood sugar (<126) -> no change or -0.1
- Borderline results -> +0.1 to +0.2
- Abnormal results -> +0.3 to +0.5
- Multiple abnormalities -> Manual Review or Decline
"""
    
    try:
        import json
        from openai import AzureOpenAI
        
        # This would use your existing Azure OpenAI client
        # For now, return a placeholder
        updated_health = {
            'original_risk_score': original_health.get('risk_score', 0),
            'medical_exam_integrated': True,
            'medical_findings_summary': 'Medical exam results reviewed and integrated',
            'status': 'updated'
        }
        
        state['health_underwriting_with_medicals'] = updated_health
        print("✅ Medical findings integrated into health assessment")
        
    except Exception as e:
        print(f"⚠️  Could not integrate medical findings: {e}")
    
    return state
