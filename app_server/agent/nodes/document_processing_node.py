import os
from app_server.agent.state import AgentState
from app_server.utils.clients import azure_client, AZURE_DEPLOYMENT_NAME
from app_server.utils.helpers import safe_parse_json, encode_image_to_b64, ensure_azure_url_has_sas

def document_processing_node(state: AgentState):
    print("--- Document Processing Node ---")
    normalized_app = state.get("normalized_by_llm", state.get("application", {}))
    documents = normalized_app.get("documents", [])
    
    if not documents:
        out = {"ocr_status": "skipped", "reason": "no_documents_found"}
        out = {"ocr_status": "skipped", "reason": "no_documents_found"}
        return {"document_processing": out}
        
    # Check if we already processed documents to avoid re-running expensive OCR
    existing_processing = state.get("document_processing", {})
    if existing_processing.get("ocr_status") == "completed" and existing_processing.get("documents_processed") == len(documents):
        print("ℹ️  Documents already processed. Skipping OCR.")
        return {}
    
    def call_vision(image_path):
        try:
            # Check if it's a URL or local file
            if image_path.startswith(('http://', 'https://')):
                # Ensure Azure Blob URLs have SAS token
                if "blob.core.windows.net" in image_path:
                    image_path = ensure_azure_url_has_sas(image_path)
                    print(f"🔐 Signed Azure Blob URL: {image_path[:50]}...")

                # For URLs, use URL directly in vision API
                prompt = """
You are a document extraction model. Extract the fields from PAN or Aadhaar document if visible. Return JSON only:
{ "document_type": "PAN|Aadhaar", "name":"", "father_name":"","gender":"","dob":"","id_number":"" }
If a field is not present, set it to null.
"""
                resp = azure_client.chat.completions.create(
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
                    resp = azure_client.chat.completions.create(
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
    
    return {"document_processing": {
        "ocr_status": "completed",
        "documents_processed": len(documents),
        "results": results
    }}
