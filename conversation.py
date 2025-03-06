import json
import os
import requests
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


MODEL = "openrouter/anthropic/sonnet_3.5"

OPENAI_API_KEY = get_api_key("OPENAI_API_KEY")
ANTHROPIC_API_KEY = get_api_key("ANTHROPIC_API_KEY")
OPENROUTER_API_KEY = get_api_key("OPENROUTER_API_KEY")

def completion(model, messages, timeout=60, num_retries=2):
    response = requests.post(
        url="https://openrouter.ai/api/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        },
        data=json.dumps(
            {
                "model": model.replace("openrouter/", ""),
                "messages": messages,
            }
        ),
    )
    return response.json()


class Conversation:
    def __init__(self):
        self.messages = []

    def add_message(self, message: str, role="user", ephemeral=False):
        if role == "system":
            role = "user"
            message = f"SYSTEM: {message}"
        if not message:
            raise ValueError("Message cannot be empty")
        if role not in ["user", "assistant", "system"]:
            raise ValueError(
                f"Invalid role: {role}. Roles are 'user', 'assistant', 'system'"
            )

        self.messages.append({"role": role, "content": message, "ephemeral": ephemeral})
        return self

    def run(self, model, should_print=True, api_key=None) -> str:
        if HUMAN_MOCK:
            print("\nMOCK MODE: Please provide a response for the following prompt:\n")
            print("Context:")
            for msg in self.messages:
                print(f"{msg['role']}: {msg['content']}\n")
            response_text = input("Enter your response: ")
        else:
            try:
                # Use the provided API key or the one from the environment
                if api_key:
                    os.environ["OPENROUTER_API_KEY"] = api_key
                if not os.environ.get("OPENROUTER_API_KEY"):
                    raise ValueError("No API key provided")

                response = completion(
                    model=model,
                    messages=self.messages,
                    timeout=60,
                    num_retries=2,
                )
                response_text = response["choices"][0]["message"]["content"]
            except Exception as e:
                print("COMPLETION FAILED. Try to manually fix before continuing.", e)
                try:
                    response = completion(
                        model=model,
                        messages=self.messages,
                        timeout=60,
                        num_retries=2,
                    )
                    response_text = response["choices"][0]["message"]["content"]
                except Exception as e:
                    return f"(No response) {e}"
        self.add_message(response_text, role="assistant")
        if should_print:
            print(f"Bot: {response_text}\n\n")

        self.messages = [
            message for message in self.messages if not message["ephemeral"]
        ]
        return response_text
