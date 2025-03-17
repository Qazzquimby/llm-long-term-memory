from src.chat_loop import conversation_loop
from src.consolidation import should_consolidate, consolidate
from src.conversation import Conversation

from src.db import get_db_factory
from src.dev_load_fulminate import load_fulminate


# Make a fake conversation
# Run consolidate


async def consolidate_fulminate_no_context():
    SessionLocal = get_db_factory()
    with SessionLocal() as session:
        fulminate_messages = load_fulminate()

        num_consolidations = 0
        # await conversation_loop(session=session, previous_messages=fulminate_messages)
        conversation = Conversation()
        for i in range(0, len(fulminate_messages), 2):
            message_pair = fulminate_messages[i : i + 2]
            conversation.add_message(message=message_pair[0])
            conversation.add_message(message=message_pair[1])

            if should_consolidate(conversation):
                num_consolidations += 1
                await consolidate(session=session, conversation=conversation)

        # todo work on getting context for messages
        # todo grade contexitems based on usefulness

        print("done", num_consolidations)


if __name__ == "__main__":
    import asyncio

    asyncio.run(consolidate_fulminate_no_context())
