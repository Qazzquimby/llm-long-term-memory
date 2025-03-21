import asyncio
from src.chat_loop import ChatLoop, MAX_CONVERSATION_LENGTH
from src.conversation import ChatMessage, MODEL, Role
from src.context import get_assistant_context
from src.context_evaluation import evaluate_context
from src.consolidation import should_consolidate, consolidate
from src.environments.text_adventure.text_adventure import AnchorheadGame
from src.db import get_engine, get_sessionmaker
from sqlalchemy.orm import Session


class TextAdventureChatLoop(ChatLoop):
    def __init__(self, session: Session, previous_messages=None, headless=True, human_observer=True, max_turns=None):
        super().__init__(session=session, previous_messages=previous_messages)
        self.game = AnchorheadGame(headless=headless)
        self.human_observer = human_observer
        self.max_turns = max_turns or MAX_CONVERSATION_LENGTH

    async def run(self):
        try:
            initial_text = await self.game.start()
            
            self.conversation.add_message(
                message=ChatMessage(
                    content="You are playing the classic text adventure Anchorhead! "
                    "Respond with commands, and see if you can win. "
                    "Think things through, then put your input to the game on the final line of your responses.",
                    role=Role.SYSTEM,
                ),
            )
            
            await self.process_response(initial_text)
            
            for _ in range(self.max_turns):
                last_message = self.conversation.messages[-1].content
                llm_command = self._extract_command(last_message)
                
                if self.human_observer:
                    print(f"\nLLM Command: {llm_command}")
                
                game_response = await self.game.send_command(llm_command)
                
                if self.human_observer:
                    print(f"\nGame Response:\n{game_response}")
                
                await self.process_response(game_response)
                
                if should_consolidate(self.conversation):
                    await consolidate(session=self.session, conversation=self.conversation)
                
                if "quit" in last_message.lower() or "exit" in last_message.lower():
                    if self.human_observer:
                        print("\nLLM decided to quit the game.")
                    break
                
                if self.human_observer and input("\nPress Enter to continue or 'q' to quit: ").lower() == "q":
                    print("Human observer interrupted the game.")
                    break
        finally:
            self.game.close()

    async def get_environment_input(self) -> str:
        return ""  # Not used in this implementation

    async def process_response(self, environment_input: str):
        self.conversation.add_message(
            message=ChatMessage(
                content=f"Game response:\n{environment_input}\n\nWhat command would you like to send next?",
                role=Role.USER,
            )
        )
        
        context = get_assistant_context(self.session)
        self.conversation.add_message(
            message=ChatMessage(content=str(context), role=Role.SYSTEM, ephemeral=True),
            prepend=True,
        )
        
        await self.conversation.run(MODEL)
        
        await evaluate_context(
            session=self.session,
            context=context,
            conversation=self.conversation,
        )
    
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
    max_turns=1000,
):
    chat_loop = TextAdventureChatLoop(
        session=session, 
        previous_messages=previous_messages,
        headless=headless,
        human_observer=human_observer,
        max_turns=max_turns
    )
    await chat_loop.run()


async def main():
    engine = get_engine()
    Session = get_sessionmaker(engine)
    
    with Session() as session:
        await text_adventure_loop(
            session=session, headless=False, human_observer=True, max_turns=1000
        )


if __name__ == "__main__":
    asyncio.run(main())
