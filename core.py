import os
from pathlib import Path

import litellm
from litellm import completion, completion_cost

litellm.modify_params = True
# os.environ["LITELLM_LOG"] = "DEBUG"
# litellm.set_verbose = True


# Load API keys from environment variables or dev files
def get_api_key(key_name):
    env_key = os.environ.get(key_name)
    if env_key:
        return env_key

    key_file = Path(f"{key_name.lower()}.txt")
    if key_file.exists():
        return key_file.read_text().strip()

    return None


MODEL = "openrouter/anthropic/sonnet_3.5"

OPENAI_API_KEY = get_api_key("OPENAI_API_KEY")
ANTHROPIC_API_KEY = get_api_key("ANTHROPIC_API_KEY")
OPENROUTER_API_KEY = get_api_key("OPENROUTER_API_KEY")


class Prompt:
    def __init__(self):
        self.messages = []
        self.total_cost = 0

    def add_message(self, message: str, role="user"):
        if not message:
            raise ValueError("Message cannot be empty")
        if role not in ["user", "assistant", "system"]:
            raise ValueError(
                f"Invalid role: {role}. Roles are 'user', 'assistant', 'system'"
            )

        self.messages.append({"role": role, "content": message})
        return self

    def run(self, model, should_print=True, api_key=None) -> str:
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
                # fallbacks=[
                #     "openrouter/openai/gpt-4o-mini",
                #     "openrouter/nousresearch/hermes-3-llama-3.1-405b:free",
                #     "openrouter/meta-llama/llama-3.1-8b-instruct:free",
                # ],
            )
        except Exception as e:
            print("COMPLETION FAILED. Try to manually fix before continuing.", e)
            try:
                response = completion(
                    model=model,
                    messages=self.messages,
                    timeout=60,
                    num_retries=2,
                )
            except Exception as e:
                return f"(No response) {e}"
        response_text = response["choices"][0]["message"]["content"]
        self.add_message(response_text, role="assistant")
        if should_print:
            print(f"Bot: {response_text}\n\n")

        try:
            total_cost = completion_cost(completion_response=response)
        except:
            total_cost = 0

        self.total_cost += total_cost
        return response_text


system_message = ""
memory_window_size = 5

past_messages = []
if system_message:
    past_messages.append({"role": "system", "content": system_message})


def converse(initial_message: str = None, model: str = "gpt-4o-2024-08-06"):
    if initial_message:
        past_messages.append({"role": "user", "content": initial_message})

    # make new log file
    new_log_number = len(list(Path("logs").glob("log*.txt"))) + 1
    log_path = Path("logs") / f"log_{new_log_number}.txt"
    log_path.parent.mkdir(exist_ok=True)
    with open(log_path, "w+") as f:
        f.write(
            "\n".join(
                [
                    f"{message['role']}: {message['content']}"
                    for message in past_messages
                ]
            )
        )

        if initial_message:
            response = completion(
                model=model,
                messages=past_messages,
            )
            response_text = response["choices"][0]["message"]["content"]
            response_message = {"role": "assistant", "content": response_text}
            save_message(file=f, message=response_message)

            print(f"Bot: {response_text}\n\n")

        while True:
            user_input = input("You: ")
            if user_input == "quit":
                print("DONE")
                break
            user_message = {"role": "user", "content": user_input}
            save_message(file=f, message=user_message)

            response = completion(
                model=model,
                messages=past_messages,
            )
            response_text = response["choices"][0]["message"]["content"]
            response_message = {"role": "assistant", "content": response_text}
            save_message(file=f, message=response_message)

            print(f"Bot: {response_text}\n\n")


def save_message(file, message: dict):
    past_messages.append(message)
    file.write(f"\n{message['role']}: {message['content']}")
