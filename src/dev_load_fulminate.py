from pathlib import Path

from src.conversation import ChatMessage, Role


def load_fulminate() -> list[ChatMessage]:
    path = Path("../fulminate_0.txt")
    text = path.read_text()
    parts = text.split("\n\n\n")

    messages = []
    for part in parts:
        try:
            human, bot = part.split("Bot: ", 1)
            messages.append(ChatMessage(content=human.strip()))
            messages.append(ChatMessage(content=bot.strip(), role=Role.ASSISTANT))
        except ValueError:
            break
    return messages
