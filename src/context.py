from abc import ABC
from typing import List

from pydantic import BaseModel
from sqlalchemy.orm import Session

from src.conversation import ChatMessage
from src.models import ContextItemModel, MessageSummaryModel, EntityModel, FactModel


class ScoredContextItem(BaseModel):
    item: ContextItemModel
    total_score: float

    recency: float

    @classmethod
    def from_item(cls, item):
        # todo score here

        return cls(item=item, total_score=0, recency=0)


class ContextWindow(ABC):
    def __init__(
        self,
        message_summaries: List[MessageSummaryModel],
        entities: List[EntityModel],
        facts: List[FactModel],
    ):
        self.message_summaries = message_summaries
        self.entities = entities
        self.facts = facts

    @classmethod
    def get_for_conversation(cls, session: Session, messages: List[ChatMessage]):
        # all_message_summaries = session.query(MessageSummary).all()
        # all_entities = session.query(Entity).all()
        # all_facts = session.query(Fact).all()
        # all_scored = [ # note this should use the .get_all functions
        #     ScoredContextItem.from_item(item)
        #     for item in all_message_summaries + all_entities + all_facts
        # ]
        # todo use ranked
        return cls(
            message_summaries=MessageSummaryModel.get_all(session=session),
            entities=EntityModel.get_all(session=session),
            facts=FactModel.get_all(session=session),
        )

        # negative score based on weight
        # get all the items with positive score?
        # plus some max length

        # todo these facts will have int importances
        #   need dedicated saving and loading

        # todo later load weights here

        # TODO want to rank these.

        # sklearn random forest or mlp to turn the following metrics into the final score
        # estimating a usefulness score from 0-1 based on UsageRecord.usefulness (normalized)

        # metrics
        # age, age since updated
        # importance
        # LATER keyword matching to recent context, especially last couple messages. Need to implement first.
        # LATER embedding relevance to the same. Need to implement first.
        # past usages
        # usefulness scores across past usages. Just the average or maybe something more clever.
        # context relevant to other relevant context for explainability
        # Later look at relationships between items
        # ?prefer items that were in previous contexts? May be redundant given the above


class AssistantContextWindow(ContextWindow):
    def __str__(self):
        context_parts = []

        if self.entities:
            context_parts.append("## Key Entities:")
            for entity in self.entities:
                context_parts.append(f"{entity.aliases}: {entity.brief}")

        if self.facts:
            context_parts.append("\nFacts:")
            for fact in self.facts:
                context_parts.append(fact.body)

        if self.message_summaries:
            context_parts.append("\n## Conversation Summary:")
            for summary in self.message_summaries:
                context_parts.append(summary.body)

        return "\n".join(context_parts)


class ConsolidatorContext(ContextWindow):
    def __str__(self):
        parts = []
        if self.message_summaries:
            parts.append("SUMMARIES OF PAST MESSAGES:")
            parts.append(
                "\n\n".join([str(summary) for summary in self.message_summaries])
            )

        if self.entities:
            parts.append("ENTITIES:")
            parts.append(
                "\n\n".join([f"{entity}" for i, entity in enumerate(self.entities)])
            )

        if self.facts:
            parts.append("FACTS:")
            parts.append("\n\n".join([f"{fact}" for i, fact in enumerate(self.facts)]))

        # todo badly mangled
        return "\n\n".join(parts)
