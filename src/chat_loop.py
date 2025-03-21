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
    @abstractmethod
    async def run(
        self, session: Session, previous_messages: Optional[List[ChatMessage]] = None
    ):
        pass

    @abstractmethod
    async def get_user_input(self) -> str:
        pass

    @abstractmethod
    async def process_response(
        self, session: Session, user_input: str, conversation: Conversation
    ):
        pass


class HumanChatLoop(ChatLoop):
    async def run(
        self, session: Session, previous_messages: Optional[List[ChatMessage]] = None
    ):
        def save_message(message: ChatMessage):
            if message.ephemeral:
                return
            session.add(Message(body=message.content, sender=message.role))
            session.commit()

        if previous_messages is None:
            previous_messages = []

        conversation = Conversation(
            messages=previous_messages, add_message_callback=save_message
        )
        prompt_session = PromptSession(message="You: ")

        for _ in range(MAX_CONVERSATION_LENGTH):
            user_input = await self.get_user_input(prompt_session)

            await self.process_response(
                session=session, user_input=user_input, conversation=conversation
            )

            if should_consolidate(conversation):
                await consolidate(session=session, conversation=conversation)

    async def get_user_input(self, prompt_session: PromptSession) -> str:
        return await prompt_session.prompt_async()

    async def process_response(
        self, session: Session, user_input: str, conversation: Conversation
    ):
        conversation.add_message(message=ChatMessage(content=user_input))

        context = get_assistant_context(session)

        conversation.add_message(
            message=ChatMessage(content=str(context), role=Role.SYSTEM, ephemeral=True),
            prepend=True,
        )
        await conversation.run(MODEL)

        # todo this doesn't need to be awaited in real use I think.
        await evaluate_context(
            session=session,
            context=context,
            conversation=conversation,
        )


async def conversation_loop(session: Session, previous_messages=None):
    chat_loop = HumanChatLoop()
    await chat_loop.run(session, previous_messages)
