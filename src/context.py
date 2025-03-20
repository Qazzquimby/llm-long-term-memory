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

    # TODO want to rank these.
    # sklearn random forest or mlp to turn the following metrics into the final score
    # estimating a usefulness score from 0-1 based on UsageRecord.usefulness (normalized)

    # metrics
    # age, age since updated
    # importance
    # salience
    # LATER keyword matching to recent context, especially last couple messages. Need to implement first.
    # LATER embedding relevance to the same. Need to implement first.
    # past usages
    # usefulness scores across past usages. Just the average or maybe something more clever.
    # context relevant to other relevant context for explainability
    # Later look at relationships between items
    # ?prefer items that were in previous contexts? May be redundant given the above

    def __str__(self):
        context_parts = []

        if self.entities:
            context_parts.append("## Key Entities:")
            for entity in self.entities:
                context_parts.append(f"{entity.aliases[0].alias}: {entity.brief}")

        if self.facts:
            context_parts.append("\nFacts:")
            for fact in self.facts:
                context_parts.append(fact.body)

        if self.message_summaries:
            context_parts.append("\n## Conversation Summary:")
            for summary in self.message_summaries:
                context_parts.append(summary.body)

        return "\n".join(context_parts)


def get_assistant_context(session: Session) -> AssistantContext:
    context = AssistantContext(session=session)
    return context
