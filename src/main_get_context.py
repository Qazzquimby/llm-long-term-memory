from src.chat_loop import conversation_loop
from src.consolidation import should_consolidate, consolidate
from src.context import get_assistant_context
from src.conversation import Conversation, Role, ChatMessage

from src.db import get_db_factory
from src.dev_load_fulminate import load_fulminate
from src.main_consolidation import consolidate_fulminate_no_context


async def evaluate_context(context, message: ChatMessage):
    print(context, message)


# todo work on getting context for messages
# todo grade contexitems based on usefulness
async def get_context_after_consolidation(session, messages):
    conversation = await consolidate_fulminate_no_context(
        session, messages, should_return_after_num_consolidations=1
    )

    future_messages = messages[len(conversation.messages) :]

    last_context = None

    for message in future_messages:
        conversation.add_message(message=message)

        if message.sender == Role.USER:
            last_context = get_assistant_context(session)

        elif message.sender == Role.ASSISTANT:
            await evaluate_context(context=last_context, message=message)

    print("ok")


async def main():
    SessionLocal = get_db_factory()
    with SessionLocal() as session:
        fulminate_messages = load_fulminate()
        await get_context_after_consolidation(
            session=session, messages=fulminate_messages
        )


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
