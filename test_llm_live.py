"""Quick smoke test for LLM API connectivity."""
import os
from src.llm import LLMClient

client = LLMClient(
    base_url=os.environ.get("LLM_BASE_URL", "https://open.bigmodel.cn/api/coding/paas/v4"),
    api_key=os.environ.get("LLM_API_KEY", ""),
    model=os.environ.get("LLM_MODEL", "glm-4.7"),
)

print(f"URL: {client.base_url}/chat/completions")
print(f"Model: {client.model}")
print("Calling LLM...")

result = client.complete("You are a helpful assistant.", "Say hello in Chinese, one sentence only.")
print(f"Response: {result}")
print("OK!")
