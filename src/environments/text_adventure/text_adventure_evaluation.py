import asyncio
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
from sqlalchemy.orm import Session

from src.db import get_db_factory, Message, Role
from src.conversation import ChatMessage


@dataclass
class GameMetrics:
    """Stores metrics about a text adventure game session."""

    message_count: int = 0
    environment_message_count: int = 0
    score: int = 0  # Placeholder for future scoring implementation

    # Additional metrics can be added here as needed
    # Examples:
    # commands_issued: int = 0
    # locations_visited: Set[str] = field(default_factory=set)
    # items_collected: Set[str] = field(default_factory=set)


class GameAnalyzer:
    """Analyzes text adventure game logs and extracts metrics."""

    def __init__(self, session: Session):
        self.session = session
        self.messages = []
        self.environment_messages = []
        self.metrics = GameMetrics()

    def load_messages(self) -> None:
        """Load all messages from the database."""
        self.messages = self.session.query(Message).order_by(Message.id).all()
        self.metrics.message_count = len(self.messages)

        # Extract environment messages (from the game to the LLM)
        self.environment_messages = [
            msg for msg in self.messages if msg.sender == Role.USER
        ]
        self.metrics.environment_message_count = len(self.environment_messages)

    def get_message_timeline(self) -> List[Tuple[int, str]]:
        """Returns a list of (message_id, content) for environment messages."""
        return [(msg.id, msg.body) for msg in self.environment_messages]

    def calculate_metrics(self) -> GameMetrics:
        """Calculate metrics based on the game history.
        This is a placeholder for more sophisticated metrics in the future.
        """
        # For now, just return the basic metrics we've already collected
        # Future implementations can parse message content to extract game state
        return self.metrics

    def print_summary(self) -> None:
        """Print a summary of the game metrics."""
        print(f"Game Analysis Summary")
        print(f"====================")
        print(f"Total messages: {self.metrics.message_count}")
        print(f"Environment messages: {self.metrics.environment_message_count}")
        print(f"Current score: {self.metrics.score}")
        print("\nEnvironment Message Timeline:")

        for idx, (msg_id, content) in enumerate(self.get_message_timeline()):
            # Print a truncated version of each message
            truncated = content[:50] + "..." if len(content) > 50 else content
            print(f"{idx+1}. Message #{msg_id}: {truncated}")


async def analyze_game():
    """Main function to analyze a text adventure game session."""
    SessionLocal = get_db_factory()
    with SessionLocal() as session:
        analyzer = GameAnalyzer(session)
        analyzer.load_messages()
        metrics = analyzer.calculate_metrics()
        analyzer.print_summary()
        return metrics
