import logging
import os
from langchain_mcp_adapters.client import MultiServerMCPClient
from langgraph.prebuilt import create_react_agent
import asyncio
from llm.openai_client import create_openai_chat_client
from utils.config import get_config_value
from openai import AzureOpenAI

# Enable observability for the application

async def weather_forecast(message: str):
    """
    Demonstrates the tool-calling feature of LLMs. Here we ask a question to get weather forecast for a
    city. We use two tools, one to map the city to a (latitude, longitude) tuple from a csv file,
    and then another tool which calls open-meteo to get the current weather condition in a
    particular latitude and longitude.

    The tools are provided above as get_lat_long and get_weather.
    """

    client = MultiServerMCPClient(
        {
            "weather": {
                "transport": "streamable_http",
                "url": get_config_value("weather_mcp_url")
            },
        }
    )

    tools = await client.get_tools()
    logging.info(f"Received request: {message}")

    

    llm = AzureOpenAI(model="GPT-4o",
    api_version="2024-12-01-preview",
    azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
    api_key=os.getenv("AZURE_OPENAI_KEY"),
)   

#   llm = create_openai_chat_client(model="gpt-4o",
#                                temperature=0.0001,
#                                   api_version="2023-05-15",
#                                   max_tokens=1024)

    agent = create_react_agent(llm, tools, prompt="provide a textual explanation or summary alongside the tool call")

    logging.info(f"Starting the execution of the agent.")
    weather_response = await agent.ainvoke({"messages": [f"{message}"]})

    logging.info(f"LLM response received: {weather_response}")
    return weather_response

if __name__ == "__main__":
    result = asyncio.run(weather_forecast("How is the weather in CA"))
    print(result)
