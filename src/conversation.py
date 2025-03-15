import os
from pathlib import Path
import asyncio
from typing import Literal

import aiohttp

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


class ChatMessage:
    def __init__(
        self,
        content: str,
        role: Literal["user", "assistant", "system"] = "user",
        ephemeral=False,
        hidden=False,
    ):
        if role == "system":
            role = "user"
            content = f"SYSTEM: {content}"
        if not content:
            raise ValueError("Message cannot be empty")
        if role not in ["user", "assistant", "system"]:
            raise ValueError(
                f"Invalid role: {role}. Roles are 'user', 'assistant', 'system'"
            )

        self.content = content
        self.role = role
        self.ephemeral = ephemeral
        self.hidden = hidden

    def __str__(self):
        return f"{self.role}: {self.content}\n"


class Conversation:
    def __init__(self, add_message_callback=None):
        self.messages: list[ChatMessage] = []
        self.add_message_callback = add_message_callback

    def add_message(self, message: ChatMessage, prepend=False):
        if prepend:
            self.messages.insert(0, message)
        else:
            self.messages.append(message)

        if self.add_message_callback:
            self.add_message_callback(message=message)
        return self

    async def run(self, model, should_print=True, max_messages=None) -> str:
        message_to_show = [msg for msg in self.messages if not msg.hidden]
        if max_messages:
            message_to_show = message_to_show[-max_messages:]
        if HUMAN_MOCK:
            print("\nMOCK MODE: Please provide a response for the following prompt:\n")
            print("Context:")
            for msg in message_to_show:
                print(msg)
            response_text = input("Enter your response: ")
        else:
            try:
                response = await completion(
                    model=model,
                    messages=message_to_show,
                    timeout=60,
                    num_retries=2,
                )
                response_text = response["choices"][0]["message"]["content"]
            except Exception as e:
                print("COMPLETION FAILED. Try to manually fix before continuing.", e)
                try:
                    response = await completion(
                        model=model,
                        messages=message_to_show,
                        timeout=60,
                        num_retries=2,
                    )
                    response_text = response["choices"][0]["message"]["content"]
                except Exception as e:
                    return f"(No response) {e}"
        self.add_message(ChatMessage(content=response_text, role="assistant"))
        if should_print:
            print(f"Bot: {response_text}\n\n")

        for message in self.messages:
            if message.ephemeral:
                message.hidden = True
        return response_text
