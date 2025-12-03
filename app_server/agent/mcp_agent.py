import logging
import asyncio
from langchain_core.tools import tool
from langgraph.prebuilt import create_react_agent
from app_server.utils.clients import azure_client
from app_server.utils.helpers import call_mcp_tool

# Enable observability for the application

@tool
def get_insurance_history(pan_number: str) -> dict:
    """
    Fetch insurance history for a given PAN number.
    Returns details about past policies, claims, and rejections.
    """
    try:
        return call_mcp_tool("insurance_history", pan_number)
    except Exception as e:
        return {"error": f"Failed to fetch insurance history: {str(e)}"}

@tool
def get_financial_eligibility(pan_number: str) -> dict:
    """
    Fetch financial eligibility data for a given PAN number.
    Returns credit score, income verification, and other financial metrics.
    """
    try:
        return call_mcp_tool("financial_eligibility", pan_number)
    except Exception as e:
        return {"error": f"Failed to fetch financial eligibility: {str(e)}"}

async def insurance_agent_demo(message: str):
    """
    Demonstrates the tool-calling feature of LLMs using our Insurance MCP tools.
    """
    
    tools = [get_insurance_history, get_financial_eligibility]
    logging.info(f"Received request: {message}")

    # Use shared azure_client
    agent = create_react_agent(azure_client, tools, prompt="You are an insurance assistant. Use the provided tools to answer questions about insurance history and financial eligibility.")

    logging.info(f"Starting the execution of the agent.")
    response = await agent.ainvoke({"messages": [f"{message}"]})

    logging.info(f"LLM response received: {response}")
    return response

if __name__ == "__main__":
    # Example usage
    result = asyncio.run(insurance_agent_demo("Check financial eligibility for PAN ABCDE1234F"))
    print(result)
