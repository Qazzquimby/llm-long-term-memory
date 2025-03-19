from sqlalchemy.orm import Session

from db import (
    MessageSummary,
    Entity,
    Fact,
)


class AssistantContext:
    def __init__(self, session: Session):
        self.message_summaries = session.query(MessageSummary).all()

        self.entities = session.query(Entity).all()

        self.facts = session.query(Fact).all()

        return

    # alright so to rank facts we have
    # age, age since updated
    # importance
    # salience
    # keyword matching to recent context, especially last couple messages
    # embedding relevance to the same
    # times provided
    # times useful
    # context relevant to other relevant context for explainability
    # Later look at relationships between items
    # ?prefer items that were in previous contexts? May be redundant given the above

    def __str__(self):
        context_parts = []

        # 1. Entity briefs
        if self.entities:
            context_parts.append("## Key Entities:")
            for entity in self.entities:
                context_parts.append(f"- {entity.brief}")

        # 2. Message summaries (oldest to newest)
        if self.message_summaries:
            context_parts.append("\n## Conversation Summary:")
            for summary in self.message_summaries:
                context_parts.append(f"- {summary.body}")

        # 3. Relevant facts/theories/questions/objectives
        if self.facts:
            context_parts.append("\n## Active Knowledge:")

            if self.facts:
                context_parts.append("\nFacts:")
                for fact in self.facts:
                    context_parts.append(f"- {fact.body}")

        return "\n".join(context_parts)


def get_assistant_context(session: Session) -> str:
    context = AssistantContext(session=session)
    return str(context)
