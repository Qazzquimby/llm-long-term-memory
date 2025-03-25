from pydantic_ai import Agent
from pydantic_ai.models.openai import OpenAIModel
from pydantic_ai.providers.openai import OpenAIProvider

from src.chat_loop import conversation_loop

from src.conversation import sonnet_37, OPENROUTER_API_KEY
from src.db import get_db_factory


async def main():
    SessionLocal = get_db_factory()
    with SessionLocal() as session:
        await conversation_loop(session)


def little_main():
    model = OpenAIModel(
        sonnet_37.replace("openrouter/", ""),
        provider=OpenAIProvider(
            base_url="https://openrouter.ai/api/v1",
            api_key=OPENROUTER_API_KEY,
        ),
    )
    agent = Agent(model)
    result = agent.run_sync(
        "What are two syllable words related to 'soul', possibly a prefix? For example 'bio' is a two syllable prefix for life."
    )
    print(result)


if __name__ == "__main__":
    # little_main()

    import asyncio

    asyncio.run(main())
