from abc import ABC
from typing import List

from pydantic import BaseModel
from sqlalchemy.orm import Session

from src.conversation import ChatMessage
from src.models import (
    ContextItemModel,
    MessageSummaryModel,
    EntityModel,
    FactModel,
    importance_to_num,
)


class ScoredContextItem(BaseModel):
    item: ContextItemModel
    total_score: float

    recency: float

    @classmethod
    def from_item(cls, item: ContextItemModel):
        # todo score here

        # Recency
        # todo add message index to ContextItemModel
        #   pass current message index to this function
        #   Get a decaying recency score

        # Length
        # negative score, maybe dividing value?
        # todo some kind of linear decay based on length..?
        #  longer texts will be relevant to more things, and probably more likely marked useful
        #  but they cost more. Want to correct for that.

        # Keyword Search
        # todo value of how well the item matches keyword search

        # Vector Search
        # todo value ofh ow well the item matches vector search

        # Importance
        # 1-5
        importance = importance_to_num[item.importance]

        # Past Usefulness
        # todo put usage_records on ContextItemModel
        #  get avg usefulness [0-2] across past retrievals

        # ?Coherence?
        # context relevant to other relevant context for explainability
        # Later look at relationships between items

        # todo later load weights here
        # sklearn random forest or mlp to turn the following metrics into the final score
        # estimating a usefulness score from 0-1 based on UsageRecord.usefulness (normalized)

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
        all_message_summaries = MessageSummaryModel.get_all(session=session)
        all_facts = FactModel.get_all(session=session)

        all_entities = EntityModel.get_all(session=session)

        all_scored = [
            ScoredContextItem.from_item(item)
            for item in all_message_summaries + all_facts
        ]
        by_score = sorted(all_scored, key=lambda x: x.total_score, reverse=True)

        # todo get top items up to some maximum length
        #  and maybe only positive ranked items if sometimes there are fewer than that many needed items

        top_20 = by_score[:20]
        relevant_message_summaries = [
            scored_item.item
            for scored_item in top_20
            if isinstance(scored_item.item, MessageSummaryModel)
        ]
        relevant_facts = [
            scored_item.item
            for scored_item in top_20
            if isinstance(scored_item.item, FactModel)
        ]

        relevant_aliases = set()
        for context_item in relevant_message_summaries + relevant_facts:
            if "relevant_entity_names" in context_item.item.__dict__:
                relevant_aliases.update(context_item.item.relevant_entity_names)

        relevant_entities = [
            entity for entity in all_entities if entity.aliases[0] in relevant_aliases
        ]

        return cls(
            message_summaries=relevant_message_summaries,
            entities=relevant_entities,
            facts=relevant_facts,
        )


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
