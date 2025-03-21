import asyncio
from typing import Optional

from src.chat_loop import ChatLoop
from src.environments.text_adventure.text_adventure import AnchorheadGame
from src.db import get_engine, get_sessionmaker
from sqlalchemy.orm import Session


class TextAdventureChatLoop(ChatLoop):
    def __init__(
        self,
        session: Session,
        previous_messages=None,
        headless=True,
        human_observer=True,
    ):
        super().__init__(session=session, previous_messages=previous_messages)
        self.game = AnchorheadGame(headless=headless)
        self.human_observer = human_observer

    async def get_environment_input(self, llm_message: Optional[str] = None) -> str:
        if not self.game.driver:
            start_prompt = """\
You are playing the classic text adventure Anchorhead!
Respond with commands, and see if you can win.
Think things through, then put your input to the game on the final line of your responses.
\n\n
"""
            game_start_text = await self.game.start()
            return start_prompt + game_start_text
        else:
            llm_command = self._extract_command(llm_message)
            game_response = await self.game.send_command(llm_command)
            return game_response

    @staticmethod
    def _extract_command(llm_response):
        try:
            return llm_response.split("\n")[-1].strip()
        except IndexError:
            return ""


async def text_adventure_loop(
    session: Session,
    previous_messages=None,
    headless=True,
    human_observer=True,
):
    chat_loop = TextAdventureChatLoop(
        session=session,
        previous_messages=previous_messages,
        headless=headless,
        human_observer=human_observer,
    )
    await chat_loop.run()


async def main():
    engine = get_engine()
    Session = get_sessionmaker(engine)

    with Session() as session:
        await text_adventure_loop(session=session, headless=False, human_observer=True)


if __name__ == "__main__":
    asyncio.run(main())
