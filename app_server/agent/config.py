"""
Configuration for Insurance Underwriting POC
Centralized configuration for easy tuning without code changes
"""

UNDERWRITING_CONFIG = {
    # Risk score thresholds for final decision
    'risk_thresholds': {
        'accept': 0.3,        # Accept if overall_risk_score <= 0.3
        'manual_review': 0.6  # Manual review if 0.3 < score <= 0.6, else Decline
    },
    
    # Weights for aggregating component risk scores
    'risk_weights': {
        'kyc': 0.1,
        'health': 0.4,
        'financial': 0.3,
        'occupation': 0.2
    },
    
    # BMI thresholds for health underwriting
    'bmi_thresholds': {
        'high_risk': 35,      # BMI > 35
        'medium_risk': 30,    # BMI 30-35
        'low_risk': 25        # BMI 25-30
    },
    
    # Income to coverage ratio limits (age-based)
    'income_coverage_ratios': {
        'under_30': 25,
        '30_to_40': 20,
        '40_to_50': 15,
        'over_50': 10
    },
    
    # Timeout settings (seconds)
    'timeouts': {
        'llm_api': 30,
        'mcp_api': 10,
        'thread_join': 15
    },
    
    # Retry settings
    'retry': {
        'max_attempts': 3,
        'backoff_delays': [2, 4, 8]  # seconds
    }
}

# Azure OpenAI settings
AZURE_CONFIG = {
    'api_version': '2024-12-01-preview',
    'max_tokens': {
        'normalization': 1000,
        'document_ocr': 500,
        'kyc': 600,
        'health': 500,
        'financial': 300,
        'occupation': 250,
        'decision': 300,
        'report': 400
    },
    'temperature': 0.0  # Deterministic for underwriting decisions
}

# MongoDB collections
MONGODB_COLLECTIONS = {
    'applications': 'applications',
    'audit_logs': 'audit_logs',
    'manual_review_queue': 'manual_review_queue'
}

# File paths
PATHS = {
    'underwriting_guidelines': 'insurance mcp/underwriting_guidelines.txt',
    'reports_output': 'reports',
    'test_data': 'agentic_ai/data'
}
