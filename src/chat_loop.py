import asyncio
from abc import ABC, abstractmethod
from typing import Optional

from sqlalchemy.orm import Session
from prompt_toolkit import PromptSession
from sqlalchemy import desc

from src.consolidation import should_consolidate, consolidate
from src.context import get_assistant_context
from src.context_evaluation import evaluate_context
from src.conversation import Conversation, ChatMessage, sonnet_37, Role
from src.db import Message, MessageSummary

MAX_CONVERSATION_LENGTH = 1000  # preventing infinite loops


def load_messages_from_db(session):
    """Load all messages from the database into ChatMessage objects"""
    db_messages = session.query(Message).order_by(Message.id).all()
    chat_messages = [
        ChatMessage(content=msg.body, role=msg.sender, db_id=msg.id)
        for msg in db_messages
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

            if message.role == Role.USER:
                visible_chat_history = [
                    msg for msg in self.conversation.messages if not msg.hidden
                ]
                chat_history_length = sum(
                    [len(msg.content) for msg in visible_chat_history]
                )

                context = next(
                    (
                        msg
                        for msg in self.conversation.messages
                        if msg.role != Role.ASSISTANT and msg.ephemeral
                    ),
                    None,
                )
                entities_length = 0
                facts_length = 0
                summaries_length = 0
                if context:
                    try:
                        context_str = context.content
                        entities_length = len(context_str.split("Facts:")[0])
                        facts_length = len(
                            context_str.split("Facts:")[1].split(
                                "## Conversation Summary:"
                            )[0]
                        )
                        summaries_length = len(
                            context_str.split("## Conversation Summary:")[1]
                        )
                    except IndexError:
                        print("WARN: unable to parse context sizes")

                part_lengths = {
                    "chat_history": chat_history_length,
                    "facts": facts_length,
                    "summaries": summaries_length,
                    "entities": entities_length,
                }
            else:
                part_lengths = None

            # warn against exact duplicate message
            duplicate_message = (
                session.query(Message).filter(Message.body == message.content).first()
            )
            should_add_new_message = True
            if duplicate_message:
                # doesn't handle rng. Maybe better to assert alternating human ai
                if duplicate_message.body == self.conversation.messages[-1].content:
                    print("WARN: New message duplicates the previous message.")
                    should_add_new_message = False
                else:
                    print(
                        "WARN: New message duplicates a message from earlier in the chat."
                    )

            if should_add_new_message:
                db_message = Message(
                    body=message.content,
                    sender=message.role,
                    part_lengths=part_lengths,
                )
                session.add(db_message)
                session.commit()
                message.db_id = db_message.id

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
                asyncio.create_task(
                    consolidate(session=self.session, conversation=self.conversation)
                )

    @abstractmethod
    async def get_environment_input(self, llm_message=Optional[str]) -> str:
        pass

    async def process_response(
        self,
        environment_input: str,
    ):
        if self.conversation.messages:
            if (
                environment_input == self.conversation.messages[-1].content
                and self.conversation.messages[-1].role != Role.ASSISTANT
            ):
                print("WARN: New message duplicates the previous message. Skipping")
            else:
                self.conversation.add_message(
                    message=ChatMessage(content=environment_input)
                )

        context = AssistantContext(session=self.session)
        if str(context):
            self.conversation.add_message(
                message=ChatMessage(
                    content=str(context), role=Role.SYSTEM, ephemeral=True
                ),
                prepend=True,
            )

        await self.conversation.run(sonnet_37)

        asyncio.create_task(
            evaluate_context(
                session=self.session,
                context=context,
                conversation=self.conversation,
            )
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
            num_messages_to_hide = last_summary.created_at_message_index
            # hide first n non-ephemeral messages
            num_hidden = 0
            for message in self.conversation.messages:
                if not message.ephemeral:
                    num_hidden += 1
                    message.hidden = True
                if num_hidden >= num_messages_to_hide:
                    break


class HumanChatLoop(ChatLoop):
    def __init__(self, session: Session):
        super().__init__(session=session, response_model=ChatMessage)

        self.prompt_session = PromptSession(message="You: ")

    async def get_environment_input(self, llm_message: Optional[str] = None) -> str:
        return await self.prompt_session.prompt_async()


async def conversation_loop(session: Session):
    chat_loop = HumanChatLoop(session=session)
    await chat_loop.run()
