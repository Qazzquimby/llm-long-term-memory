import enum
import os
from pathlib import Path
from typing import Type

from pydantic import BaseModel
from pydantic_ai import Agent
from pydantic_ai.messages import ModelMessagesTypeAdapter
from pydantic_ai.models.openai import OpenAIModel
from pydantic_ai.providers.openai import OpenAIProvider
from pydantic_ai.result import ResultDataT

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


class Role(enum.Enum):
    USER = "user"
    SYSTEM = "system"
    ASSISTANT = "assistant"


class ChatMessage:
    def __init__(
        self,
        content: str,
        role: Role = Role.USER,
        ephemeral=False,
        hidden=False,
    ):
        if role == Role.SYSTEM:
            role = Role.USER
            content = f"SYSTEM: {content}"
        if not content:
            raise ValueError("Message cannot be empty")

        self.content = content
        self.role = role
        self.ephemeral = ephemeral
        self.hidden = hidden

        self.num_words = len(content.split())

    def __str__(self):
        return f"{self.role.value}: {self.content}\n"

    def to_llm_friendly(self):
        return {"role": self.role.value, "content": self.content}

    def to_pydantic_ai(self):
        return ModelMessagesTypeAdapter.validate_json(
            {"role": self.role.value, "content": self.content}
        )


class Conversation:
    def __init__(
        self,
        messages=None,
        add_message_callback=None,
        result_type: Type[BaseModel] = None,
    ):
        if messages is None:
            messages = []
        self.messages: list[ChatMessage] = messages
        self.add_message_callback = add_message_callback
        self.result_type = result_type

    def add_message(self, message: ChatMessage, prepend=False):
        if prepend:
            self.messages.insert(0, message)
        else:
            self.messages.append(message)

        if self.add_message_callback:
            self.add_message_callback(message=message)
        return self

    async def run(
        self,
        model,
        should_print=True,
        max_messages=None,
        result_type: Type[BaseModel] = None,
    ) -> str:
        message_to_show = [msg for msg in self.messages if not msg.hidden]
        if max_messages:
            message_to_show = message_to_show[-max_messages:]

        # if HUMAN_MOCK:
        #     print("\nMOCK MODE: Please provide a response for the following prompt:\n")
        #     print("Context:")
        #     for msg in message_to_show:
        #         print(msg)
        #     response_text = input("Enter your response: ")
        #     result = None
        # else:
        llm_friendly_messages = [
            message.to_llm_friendly() for message in message_to_show
        ]
        active_result_type = result_type or self.result_type
        if active_result_type is None:
            active_result_type = str

        result = await self.call_llm(
            model=model,
            result_type=active_result_type,
            message_history=llm_friendly_messages,
        )
        response_text = str(result.data)

        self.add_message(ChatMessage(content=response_text, role=Role.ASSISTANT))
        if should_print:
            print(f"Bot: {response_text}\n\n")

        for message in self.messages:
            if message.ephemeral:
                message.hidden = True

        return result.data

    async def call_llm(
        self,
        model: str,
        result_type: ResultDataT,
        message_history: list[ChatMessage],
    ):
        agent = Agent(
            model=OpenAIModel(
                model.replace("openrouter/", ""),
                provider=OpenAIProvider(
                    base_url="https://openrouter.ai/api/v1",
                    api_key=OPENROUTER_API_KEY,
                ),
            ),
            result_type=result_type,
        )
        pydantic_messages = [message.to_pydantic_ai() for message in message_history]
        # todo handle hidden?
        response = await agent.run(
            user_prompt=message_history[-1].content,
            message_history=pydantic_messages[:-1],
        )
        return response
