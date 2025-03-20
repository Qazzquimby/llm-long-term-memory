from src.context import get_assistant_context
from src.context_evaluation import evaluate_context
from src.conversation import Role, Conversation

from src.db import get_db_factory
from src.dev_load_fulminate import load_fulminate
from src.main_consolidation import consolidate_fulminate_no_context


# todo work on getting context for messages
# todo grade contexitems based on usefulness
async def get_context_after_consolidation(session, messages):
    # conversation = await consolidate_fulminate_no_context(
    #     session, messages, should_return_after_num_consolidations=1
    # )
    # # temp to avoid recomputing consolidation
    conversation = Conversation(messages=messages[:20])

    # everything not handled as of the last consolidation, including recent messages present at consolidation time but not in the consolidation window.
    future_messages = messages[len(conversation.messages) :]

    last_context = None

    for message in future_messages:
        conversation.add_message(message=message)

        if message.role == Role.USER:
            last_context = get_assistant_context(session)

        elif message.role == Role.ASSISTANT:
            await evaluate_context(
                session=session, context=last_context, conversation=conversation
            )

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
