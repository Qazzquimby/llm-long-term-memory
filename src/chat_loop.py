from abc import ABC, abstractmethod
from src.consolidation import should_consolidate, consolidate
from src.context import get_assistant_context
from src.context_evaluation import evaluate_context
from src.conversation import Conversation, ChatMessage, MODEL, Role
from src.db import Message
from sqlalchemy.orm import Session
from prompt_toolkit import PromptSession
from typing import List, Optional

from src.db import MessageSummary
from sqlalchemy import desc

MAX_CONVERSATION_LENGTH = 1000  # preventing infinite loops


def load_messages_from_db(session):
    """Load all messages from the database into ChatMessage objects"""
    db_messages = session.query(Message).order_by(Message.id).all()
    chat_messages = [
        ChatMessage(content=msg.body, role=msg.sender) for msg in db_messages
    ]
    return chat_messages


class ChatLoop(ABC):
    def __init__(self, session: Session, response_model=None):
        self.session = session
        self.response_model = response_model

        previous_messages = load_messages_from_db(session)

        def save_message(message: ChatMessage):
            if message.ephemeral:
                return
            session.add(Message(body=message.content, sender=message.role))
            session.commit()

        if previous_messages is None:
            previous_messages = []

        self.conversation = Conversation(
            messages=previous_messages,
            add_message_callback=save_message,
            response_model=response_model,
        )

        self._hide_messages_before_last_summary()

    async def run(self):
        for _ in range(MAX_CONVERSATION_LENGTH):
            environment_input = await self.get_environment_input(
                llm_message=self._get_last_message()
            )
            if not environment_input:
                environment_input = "(Empty)"
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
        if str(context):
            self.conversation.add_message(
                message=ChatMessage(
                    content=str(context), role=Role.SYSTEM, ephemeral=True
                ),
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
        try:
            return self.conversation.messages[-1].content
        except IndexError:
            return ""

    def _hide_messages_before_last_summary(self):
        last_summary = (
            self.session.query(MessageSummary)
            .order_by(desc(MessageSummary.created_at_message_index))
            .first()
        )

        if last_summary:
            last_index = last_summary.created_at_message_index

            for i, message in enumerate(self.conversation.messages):
                if i <= last_index:
                    message.hidden = True


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
