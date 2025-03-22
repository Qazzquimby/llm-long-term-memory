import asyncio

from src.db import get_db_factory
from src.environments.text_adventure.text_adventure_chat import TextAdventureChatLoop


async def main():
    SessionLocal = get_db_factory()
    with SessionLocal() as session:
        chat_loop = TextAdventureChatLoop(
            session=session,
            headless=False,
            human_observer=True,
        )
        await chat_loop.run()


if __name__ == "__main__":
    asyncio.run(main())
