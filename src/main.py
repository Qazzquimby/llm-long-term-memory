from src.consolidation import should_consolidate, consolidate
from src.conversation import Conversation, ChatMessage, MODEL, Role
from src.db import get_sessionmaker, get_engine, Base, Message
from sqlalchemy.orm import Session
from prompt_toolkit import prompt


MAX_CONVERSATION_LENGTH = 1000  # preventing infinite loops


async def conversation_loop(session: Session):
    def save_message(message: ChatMessage):
        if message.ephemeral:
            return
        session.add(Message(body=message.content, sender=message.role))
        session.commit()

    conversation = Conversation(add_message_callback=save_message)

    for _ in range(MAX_CONVERSATION_LENGTH):
        user_input = prompt("You: ")
        conversation.add_message(message=ChatMessage(content=user_input))

        # todo get context
        context = ""
        conversation.add_message(
            message=ChatMessage(content=context, role=Role.SYSTEM, ephemeral=True),
            prepend=True,
        )
        await conversation.run(MODEL)

        if should_consolidate(conversation):
            # todo dont await, let it run in parallel
            await consolidate(session=session, conversation=conversation)


async def main():
    engine = get_engine()
    Base.metadata.create_all(engine)
    SessionLocal = get_sessionmaker()

    with SessionLocal() as session:
        await conversation_loop(session)


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
