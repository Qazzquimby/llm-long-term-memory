from abc import ABC, abstractmethod
from src.consolidation import should_consolidate, consolidate
from src.context import get_assistant_context
from src.context_evaluation import evaluate_context
from src.conversation import Conversation, ChatMessage, MODEL, Role
from src.db import Message
from sqlalchemy.orm import Session
from prompt_toolkit import PromptSession
from typing import List, Optional

MAX_CONVERSATION_LENGTH = 1000  # preventing infinite loops


class ChatLoop(ABC):
    def __init__(self, session: Session, previous_messages=None):
        self.session = session

        def save_message(message: ChatMessage):
            if message.ephemeral:
                return
            session.add(Message(body=message.content, sender=message.role))
            session.commit()

        if previous_messages is None:
            previous_messages = []

        if previous_messages is None:
            previous_messages = []
        self.conversation = Conversation(
            messages=previous_messages, add_message_callback=save_message
        )

    async def run(self):
        for _ in range(MAX_CONVERSATION_LENGTH):
            environment_input = await self.get_environment_input(
                llm_message=self._get_last_message()
            )
            await self.process_response(environment_input=environment_input)

            if should_consolidate(self.conversation):
                await consolidate(session=self.session, conversation=self.conversation)

    @abstractmethod
    async def get_environment_input(self, llm_message=Optional[str]) -> str:
        pass

    async def process_response(
        self,
        environment_input: str,
    ):
        self.conversation.add_message(message=ChatMessage(content=environment_input))

        context = get_assistant_context(self.session)

        self.conversation.add_message(
            message=ChatMessage(content=str(context), role=Role.SYSTEM, ephemeral=True),
            prepend=True,
        )
        await self.conversation.run(MODEL)

        # todo this doesn't need to be awaited in real use I think.
        await evaluate_context(
            session=self.session,
            context=context,
            conversation=self.conversation,
        )

    def _get_last_message(self):
        return self.conversation.messages[-1].content


class HumanChatLoop(ChatLoop):
    def __init__(
        self, session: Session, previous_messages: Optional[List[ChatMessage]] = None
    ):
        super().__init__(session=session, previous_messages=previous_messages)

        self.prompt_session = PromptSession(message="You: ")

    async def get_environment_input(self, llm_message: Optional[str] = None) -> str:
        return await self.prompt_session.prompt_async()


async def conversation_loop(session: Session, previous_messages=None):
    chat_loop = HumanChatLoop(session=session, previous_messages=previous_messages)
    await chat_loop.run()
