import json
import re
import base64
import os
import requests
from datetime import datetime
from bson import ObjectId
from app_server.utils.clients import db
from app_server.agent.config import AZURE_SAS_TOKEN

def ensure_azure_url_has_sas(url: str, sas_token: str = AZURE_SAS_TOKEN) -> str:
    """
    Ensure Azure Blob Storage URL has a valid SAS token.
    If it already has one, return as is. If not, append the provided SAS token.
    """
    if not url or not isinstance(url, str):
        return url
        
    if 'blob.core.windows.net' in url:
        # If URL already has a SAS token, return as is
        if '?' in url and ('sig=' in url or 'sv=' in url):
            return url
        # If we have a SAS token, append it
        elif sas_token:
            # Remove any trailing ? or & from the URL
            base_url = url.rstrip('?&')
            # Add SAS token (it should already include the leading ? or &)
            # If sas_token doesn't start with ? or &, assume it needs ?
            prefix = ""
            if not sas_token.startswith(('?', '&')):
                prefix = "?"
            return f"{base_url}{prefix}{sas_token}"
    return url

def call_mcp_tool(tool_name: str, arg: str, mcp_base_url: str = "http://localhost:9000") -> dict:
    try:
        mcp_url = os.getenv("MCP_SERVER_URL", mcp_base_url)
        tool_map = {
            "insurance_history": "insurance_history_tool",
            "financial_eligibility": "financial_eligibility",
            "sign_blob_url": "sign_blob_url",
        }
        mcp_tool_name = tool_map.get(tool_name)
        if not mcp_tool_name:
            return {"error": f"Unknown tool: {tool_name}"}
        
        api_base = os.getenv("INSURANCE_API_BASE", "http://localhost:8000")
        
        # Construct URL based on tool type
        if tool_name == "sign_blob_url":
            # For signing, we pass the URL as a query param
            # Assuming the MCP server implements: GET /sign-blob-url?url=...
            import urllib.parse
            encoded_url = urllib.parse.quote(arg)
            url = f"{api_base}/sign-blob-url?url={encoded_url}"
        else:
            # Existing tools use path parameter (arg is pan_number)
            endpoint_map = {
                "insurance_history": f"{api_base}/insurance-history/{arg}",
                "financial_eligibility": f"{api_base}/financial-eligibility/{arg}",
            }
            url = endpoint_map.get(tool_name)
        
        if not url:
            return {"error": f"No endpoint found for tool: {tool_name}"}
        
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        return resp.json()
        
    except Exception as e:
        return {"error": str(e), "status": "failed"}

def safe_parse_json(text):
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
