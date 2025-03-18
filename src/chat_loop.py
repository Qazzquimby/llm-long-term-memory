from src.consolidation import should_consolidate, consolidate
from src.context import get_assistant_context
from src.conversation import Conversation, ChatMessage, MODEL, Role
from src.db import Message
from sqlalchemy.orm import Session
from prompt_toolkit import prompt, Application, PromptSession

MAX_CONVERSATION_LENGTH = 1000  # preventing infinite loops


async def conversation_loop(session: Session, previous_messages=None):
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
        # user_input = input("You: ")
        user_input = await prompt_session.prompt_async()

        await respond_to_input(
            session=session, user_input=user_input, conversation=conversation
        )

        if should_consolidate(conversation):
            # todo dont await, let it run in parallel
            await consolidate(session=session, conversation=conversation)


async def respond_to_input(
    session: Session, user_input: str, conversation: Conversation
):
    conversation.add_message(message=ChatMessage(content=user_input))

    context = get_assistant_context(session)

    conversation.add_message(
        message=ChatMessage(content=context, role=Role.SYSTEM, ephemeral=True),
        prepend=True,
    )
    await conversation.run(MODEL)
