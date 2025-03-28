from abc import ABC
from typing import List, Literal

from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from db import MessageSummary, Entity, Fact
from src.conversation import ChatMessage


# todo prevent multiple entities with same primary alias?
#  more specifically we want them to be appropriately merged.
#  could keep earliest, could keep latest, could request merge (probably increasing in length)
class EntityModel(BaseModel):
    aliases: List[str] = Field(
        description="1 or more names for the entity. Make the first one the most clear and canonical, as it will be used by default."
    )
    brief: str = Field(
        description="1-2 sentence summary of the entity and your relationship with it."
    )

    @classmethod
    def get_all(cls, session: Session):
        rows = session.query(Entity).all()
        return [
            cls(aliases=[alias.alias for alias in row.aliases], brief=row.brief)
            for row in rows
        ]


importance_to_num = {
    "trivial": 1,
    "probably not important": 2,
    "probably important": 3,
    "clearly important": 4,
    "critically important": 5,
}
num_to_importance = {v: k for k, v in importance_to_num.items()}


class ContextItemModel(BaseModel):
    importance: Literal[
        "trivial",
        "probably not important",
        "probably important",
        "clearly important",
        "critically important",
    ] = Field(
        description="Strategic importance. One of: trivial, unimportant, probably important, very important, critically important"
    )

    # importance: conint(ge=1, le=10) = Field(
    #     description="Strategic importance. 1 is trivial, 5 is probably important, and 10 is absolutely critical"
    # )
    # salience: conint(ge=1, le=10) = Field(
    #     description="Emotional valence. 1 is has no affect on you, 5 has some emotional impact, and 10 is a burned in part of your identity"
    # )


class FactModel(ContextItemModel):
    body: str = Field(
        "~1 sentence. Facts should be largely timeless, not about events or current status"
    )
    relevant_entity_names: List[str] = Field(
        description="Names of any entities related to this fact. Use the aliases of new or existing entities exactly.",
    )

    def __str__(self):
        return f"I:{self.importance} {self.body}"

    @classmethod
    def get_all(cls, session: Session):
        rows = session.query(Fact).all()
        return [
            cls(
                body=row.body,
                relevant_entity_names=[
                    entity.aliases[0].alias for entity in row.entities
                ],
                importance=num_to_importance[row.importance],
            )
            for row in rows
        ]


class MessageSummaryModel(ContextItemModel):
    body: str = Field(
        description="Stay concise and focus on events rather than factual statements (handled elsewhere). Write it like how you'd recall a memory, focusing on what stands out or seems important."
    )
    relevant_entity_names: List[str] = Field(
        description="Names of any entities in or closely related to these events. Use the aliases of new or existing entities exactly.",
    )

    @classmethod
    def get_all(cls, session: Session):
        rows = session.query(MessageSummary).all()
        return [
            cls(
                body=row.body,
                relevant_entity_names=[
                    entity.aliases[0].alias for entity in row.entities
                ],
                importance=num_to_importance[row.importance],
            )
            for row in rows
        ]


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


class ConsolidatorContextWindow(ContextWindow):
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
                "\n\n".join(
                    [f"{i}: {entity}" for i, entity in enumerate(self.entities)]
                )
            )

        if self.facts:
            parts.append("FACTS:")
            parts.append(
                "\n\n".join([f"{i}: {fact}" for i, fact in enumerate(self.facts)])
            )

        # todo badly mangled
        return "\n\n".join(parts)


async def get_consolidator_context(
    session: Session,
    consolidation_window: List[ChatMessage],
) -> ConsolidatorContextWindow:
    return ConsolidatorContextWindow.get_for_conversation(
        session=session,
        messages=consolidation_window,
    )
