import asyncio

from src.chat_loop import ChatLoop, MAX_CONVERSATION_LENGTH
from src.conversation import Conversation, ChatMessage, MODEL, Role, completion
from src.context import get_assistant_context
from src.context_evaluation import evaluate_context
from src.consolidation import should_consolidate, consolidate
from src.environments.text_adventure.text_adventure import AnchorheadGame
from src.db import Message, get_engine, get_sessionmaker
from sqlalchemy.orm import Session
from typing import List, Optional


class TextAdventureChatLoop(ChatLoop):
    def __init__(self, headless=True, max_turns=100):
        self.game = AnchorheadGame(headless=headless)
        self.max_turns = max_turns
        self.human_observer = False

    async def run(
        self, session: Session, previous_messages: Optional[List[ChatMessage]] = None
    ):
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

        try:
            # Start the game and get initial text
            initial_text = await self.game.start()

            # Add initial game state as a system message
            conversation.add_message(
                message=ChatMessage(
                    content=f"You are playing a text adventure game called Anchorhead. "
                    f"Respond with commands to explore the game world. "
                    f"Here is the initial game state:\n\n{initial_text}",
                    role=Role.SYSTEM,
                ),
            )

            # Add a prompt for the LLM to make its first move
            conversation.add_message(
                message=ChatMessage(
                    content="What command would you like to send to the game?",
                    role=Role.USER,
                ),
            )

            # Get the first command from the LLM
            context = get_assistant_context(session)
            conversation.add_message(
                message=ChatMessage(
                    content=str(context), role=Role.SYSTEM, ephemeral=True
                ),
                prepend=True,
            )

            # Run the initial conversation to get the first command
            await conversation.run(MODEL)

            # Extract the LLM's first command
            first_command = conversation.messages[-1].content

            # Now start the main game loop
            for turn in range(self.max_turns):
                # Get the last assistant message (which contains the command)
                llm_command = conversation.messages[-1].content

                # Print for human observer if enabled
                if self.human_observer:
                    print(f"\nLLM Command: {llm_command}")

                # Process the command with the game
                game_response = await self.game.send_command(llm_command)

                # Print for human observer if enabled
                if self.human_observer:
                    print(f"\nGame Response:\n{game_response}")

                # Add the game's response as a user message (from the LLM's perspective)
                conversation.add_message(
                    message=ChatMessage(
                        content=f"Game response:\n{game_response}\n\nWhat command would you like to send next?",
                        role=Role.USER,
                    ),
                )

                # Get context and add it as an ephemeral system message
                context = get_assistant_context(session)
                conversation.add_message(
                    message=ChatMessage(
                        content=str(context), role=Role.SYSTEM, ephemeral=True
                    ),
                    prepend=True,
                )

                # Run the conversation to get the next command
                await conversation.run(MODEL)

                # Evaluate context
                await evaluate_context(
                    session=session,
                    context=context,
                    conversation=conversation,
                )

                # Check if we should consolidate
                if should_consolidate(conversation):
                    await consolidate(session=session, conversation=conversation)

                # Check for quit command in the LLM's response
                if (
                    "quit" in conversation.messages[-1].content.lower()
                    or "exit" in conversation.messages[-1].content.lower()
                ):
                    if self.human_observer:
                        print("\nLLM decided to quit the game.")
                    break

                # Allow human observer to interrupt
                if (
                    self.human_observer
                    and input("\nPress Enter to continue or 'q' to quit: ").lower()
                    == "q"
                ):
                    print("Human observer interrupted the game.")
                    break

        finally:
            self.game.close()

    async def get_user_input(self) -> str:
        # This method is not used in this implementation
        # since input comes from the LLM, not a human user
        raise NotImplementedError("TextAdventureChatLoop doesn't use get_user_input")

    async def process_response(
        self, session: Session, user_input: str, conversation: Conversation
    ):
        # This method is not used in this implementation
        # since the processing happens in the run method
        raise NotImplementedError("TextAdventureChatLoop doesn't use process_response")


async def text_adventure_loop(
    session: Session,
    previous_messages=None,
    headless=True,
    human_observer=True,
    max_turns=100,
):
    chat_loop = TextAdventureChatLoop(headless=headless, max_turns=max_turns)
    chat_loop.human_observer = human_observer
    await chat_loop.run(session, previous_messages)


async def main():
    engine = get_engine()
    Session = get_sessionmaker(engine)

    with Session() as session:
        await text_adventure_loop(
            session=session, headless=False, human_observer=True, max_turns=1000
        )


if __name__ == "__main__":
    asyncio.run(main())
