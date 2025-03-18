from src.chat_loop import conversation_loop
from src.consolidation import should_consolidate, consolidate
from src.conversation import Conversation

from src.db import get_db_factory
from src.dev_load_fulminate import load_fulminate


# Make a fake conversation
# Run consolidate


async def consolidate_fulminate_no_context(
    session, messages, should_return_after_num_consolidations=None
):
    num_consolidations = 0
    # await conversation_loop(session=session, previous_messages=fulminate_messages)
    conversation = Conversation()
    for i in range(0, len(messages), 2):
        message_pair = messages[i : i + 2]
        conversation.add_message(message=message_pair[0])
        conversation.add_message(message=message_pair[1])

        if should_consolidate(conversation):
            num_consolidations += 1
            await consolidate(session=session, conversation=conversation)
            if (
                should_return_after_num_consolidations is not None
                and num_consolidations >= should_return_after_num_consolidations
            ):
                return conversation
    print("done", num_consolidations)


async def main():
    SessionLocal = get_db_factory()
    with SessionLocal() as session:
        fulminate_messages = load_fulminate()
        await consolidate_fulminate_no_context(
            session=session, messages=fulminate_messages
        )


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
