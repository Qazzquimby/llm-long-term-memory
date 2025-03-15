import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents
for parent in PROJECT_ROOT:
    if (parent / ".git").exists():
        PROJECT_ROOT = parent
        break

HUMAN_MOCK = False


def get_api_key(key_name):
    env_key = os.environ.get(key_name)
    if env_key:
        return env_key

    key_file = Path(PROJECT_ROOT / f"{key_name.lower()}.txt")
    if key_file.exists():
        return key_file.read_text().strip()

    return None


MODEL = "openrouter/anthropic/claude-3.7-sonnet"
OPENROUTER_API_KEY = get_api_key("OPENROUTER_API_KEY")


import asyncio
import aiohttp


async def completion(model, messages, timeout=60, num_retries=0):
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
    }
    data = {
        "model": model.replace("openrouter/", ""),
        "messages": messages,
    }

    async with aiohttp.ClientSession() as session:
        for _ in range(1 + num_retries):
            try:
                async with session.post(
                    url="https://openrouter.ai/api/v1/chat/completions",
                    headers=headers,
                    json=data,
                    timeout=timeout,
                ) as response:
                    return await response.json()
            except aiohttp.ClientError as e:
                print(f"Error: {e}")
                if num_retries > 0:
                    await asyncio.sleep(1)
                    continue
