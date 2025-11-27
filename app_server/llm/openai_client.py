from langchain_openai.chat_models import AzureChatOpenAI

import os
import ssl
import httpx
from utils.config import get_headers


def create_openai_chat_client(model, model_version=None, api_version='2024-10-21', **kwargs):
    headers = get_headers()

    # Build a Headers built into it
    context = ssl.create_default_context()
    client = httpx.Client(verify=context, headers=headers)
    async_client = httpx.AsyncClient(verify=context, headers=headers)

    llm_chat = AzureChatOpenAI(openai_api_key=os.getenv("AZURE_OPENAI_KEY"),
                               model=model if model_version is None else f"{model}@{model_version}",
                               api_version=api_version,
                               azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
                               http_client=client,
                               http_async_client=async_client,
                               **kwargs)
    
    return llm_chat
