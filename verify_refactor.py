import sys
import os

# Add the project root to the python path
sys.path.append(os.getcwd())

try:
    from app_server.agent.insurance_graph import insurance_graph
    print("✅ Successfully imported insurance_graph")
    
    # Print nodes to verify structure
    print(f"Graph nodes: {insurance_graph.nodes.keys()}")
    
    # Check for specific nodes
    required_nodes = ["ingest", "document_processing", "kyc", "health", "medical_exam", "fetch_mcp", "financial", "insurance_history", "occupation", "decision", "report"]
    missing_nodes = [node for node in required_nodes if node not in insurance_graph.nodes]
    
    if missing_nodes:
        print(f"❌ Missing nodes: {missing_nodes}")
        sys.exit(1)
    else:
        print("✅ All required nodes present")

except ImportError as e:
    print(f"❌ ImportError: {e}")
    sys.exit(1)
except Exception as e:
    print(f"❌ Error: {e}")
    sys.exit(1)
