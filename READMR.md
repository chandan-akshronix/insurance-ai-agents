# AI Agent with LangGraph

## Overview

This project provides a framework for building and deploying AI agents using  GenAI, LangGraph and MCP. It includes a FastAPI server that exposes the agent's capabilities through REST endpoints. This can be deployed on WCNP using Kitt and is authenticated via Service Registry.

### Key Components

- **LangGraph**: Framework for building stateful agents with chains and tools
- **Model Context Protocol (MCP)**: Protocol for connecting to different tool services
- **FastAPI**: Web server for exposing REST endpoints
- **OpenAI Client**: Integration with Azure OpenAI models

### Agent Architecture

The agent is built using LangGraph's ReAct framework, which follows a reasoning and action approach:

1. The agent processes user queries through an LLM
2. The LLM decides which tools to call based on the query
3. Tools are accessed via MCP services (external or internal)
4. Results are processed and returned to the user

The current implementation connects to:

- GenAI LLM Gateway to access OpenAI's GPT-4o-Mini model

## Environment Setup and Local Testing

### Installing Dependencies

Before you start, make sure you have the following prerequisites:

1. **Python installed** (version 3.10 or higher recommended).
   You can check your Python version with:
'''bash
python3 --version
'''

2. **Familiarity with Python virtual environments** (using `venv`, `conda`, or `uv`).
You can use any virtual environment tool you prefer.

3. **An IDE (Optional)** You can use PyCharm, VSCode, Neovim or any other IDE of your choice.

Below are steps to set up a new virtual environment using Python's built-in `venv` module and install dependencies:

'''bash
Create a new virtual environment named 'venv'
python3 -m venv venv

Activate the virtual environment
source venv/bin/activate

Install dependencies from requirements.txt
pip install -r requirements.txt
'''

If you use `conda` or `uv`, feel free to set up your environment using those tools instead.

### Run application locally

> [!NOTE]
> If you have to run the server locally, then you will need to ensure the AKeyless Secrets are pulled into your local system and made available in /etc/secrets/.

> Alternatively, you can edit the `utils/config.py` file and read the secrets from a different folder.

To start the agent server, execute the following from the root directory:

'''bash
export SSL_CERT_FILE=/path/to/ca-certificates.crt
export PYTHONPATH=$PWD/app_server:$PYTHONPATH

python -m fastapi run --host 0.0.0.0 --port 8080 app_server/app.py
'''

This should bring up the server at `http://localhost:8080`

### Testing the Agent

In Local Deployment - there is no authentication enabled. So you can directly call the API without any auth headers:

'''bash
curl http://localhost:8080/ask_weather?city=LA
'''

### Extending the Agent

To extend the agent with additional tools:

1. Add a new MCP service connection in `app_server/agent/mcp_agent.py`:

    '''python
    client = MultiServerMCPClient(
        {
            "weather": {
                "transport": "streamable_http",
                "url": get_config_value("weather_mcp_url")
                },
                "new_tool": 
                {
                    "transport": "streamable_http",
                    "url": get_config_value("new_tool_mcp_url")
                }
            }
        )
        '''

2. Create a new endpoint in `app_server/app.py` to utilize your tool:

    '''python 
    @app.get("/use_new_tool")
    async def use_new_tool(param: str):
        """ Use the new tool with the provided parameter """
        logging.info(f"Received request for new tool with param         {param}")
        llm_resp = your_agent_function("Use the new tool with       {param}")
        logging.info(f"LLM response: {llm_resp}")
        return llm_resp
    '''


3. Implement a corresponding agent function in the appropriate module

## Deploying and Testing the Application

### Setting up the secrets


Alternatively, if you are using Service Registry to connect to LLM Gateway, you will need to store the SR Private Key in Akeyless. After that, you will have to modify both the kitt.yml and the corresponding code for generating the request headers in `llm/openai_client.py`

### Testing the Deployment

Once the application has been deployed, you can test out the API using curl.

1. Use the following curl call to validate that the agent is working:

    '''
    curl -L -X GET 'add here agentic_pod_link'
    -H 'WM_CONSUMER.ID: <your-consumer-id>'
    -H 'WM_SVC.NAME: APMM022171-SAMS-LANGGRAPH-AGENT'
    -H 'WM_SVC.ENV: dev'
    -H 'WM_SEC.KEY_VERSION: 1'
    -H 'WM_SEC.AUTH_SIGNATURE: <auth-signature>'
    -H 'WM_CONSUMER.INTIMESTAMP: <timestamp>'
    '''

### Observability

The deployed application has the following Observability tools built into it:

1. Metrics Dashboard :
--Graphana Dashboard Link

2. OPenTelementry Dashboard:
 --OpenTelementry Dashboard Link
