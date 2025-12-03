import os
import json
from datetime import datetime
from fpdf import FPDF
from app_server.agent.state import AgentState
from app_server.utils.clients import azure_client, AZURE_DEPLOYMENT_NAME
from app_server.agent.config import PATHS
from app_server.agent.models import ReportOutput
from app_server.agent.prompts import REPORT_PROMPT

def report_node(state: AgentState):
    print("--- Report Node ---")
    out_dir = "reports"
    os.makedirs(out_dir, exist_ok=True)
    app = state.get("normalized_by_llm", state.get("application", {}))
    name = app.get("personal_details", {}).get("full_name", "Applicant")
    decision = state.get("policy_decision", {})
    
    # Generate report text using LLM
    prompt = REPORT_PROMPT.format(
        app_summary=json.dumps(app, ensure_ascii=False),
        decision=json.dumps(decision, ensure_ascii=False)
    )

    try:
        resp = azure_client.beta.chat.completions.parse(
            model=AZURE_DEPLOYMENT_NAME,
            messages=[{"role": "user", "content": prompt}],
            response_format=ReportOutput,
            temperature=0.0
        )
        parsed_output = resp.choices[0].message.parsed
        report_content = parsed_output.model_dump()
        
        # Construct the text for the PDF from the structured output
        text = f"""
Executive Summary:
{report_content['summary']}

Key Findings:
{chr(10).join(['- ' + finding for finding in report_content['key_findings']])}

Risk Assessment:
{report_content['risk_assessment']}

Recommendation:
{report_content['recommendation_text']}
"""
    except Exception as e:
        print(f"❌ Error in Report LLM: {e}")
        text = f"Error generating report text: {str(e)}"

    # Build PDF with Unicode support
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = os.path.join(out_dir, f"Underwriting_Report_{name.replace(' ', '_')}_{ts}.pdf")
    
    # Create PDF with Unicode support
    pdf = FPDF()
    pdf.add_page()
    pdf.set_auto_page_break(True, 15)
    
    # Add a Unicode-compatible font (DejaVuSans supports many Unicode characters including ₹)
    font_loaded = False
    try:
        # Try to use DejaVuSans if available
        # Check common paths for DejaVuSans
        font_paths = ["DejaVuSans.ttf", "fonts/DejaVuSans.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"]
        for fp in font_paths:
            if os.path.exists(fp):
                pdf.add_font('DejaVuSans', '', fp, uni=True)
                pdf.set_font('DejaVuSans', '', 11)
                font_loaded = True
                break
    except Exception as e:
        print(f"Warning: Could not load DejaVuSans: {e}")

    if not font_loaded:
        try:
            # Fall back to Arial Unicode MS if available
            pdf.add_font('Arial', '', 'arial.ttf', uni=True)
            pdf.set_font('Arial', '', 11)
            font_loaded = True
        except:
            # Final fallback to standard font (may not support all Unicode chars)
            print("Warning: Using standard font. Unicode characters may not render correctly.")
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
    return {"underwriting_report": out}
