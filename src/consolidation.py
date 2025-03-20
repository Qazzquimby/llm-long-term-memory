from typing import List

from pydantic import BaseModel, Field, conint
from pydantic_ai import Agent
from pydantic_ai.models.openai import OpenAIModel
from pydantic_ai.providers.openai import OpenAIProvider
from sqlalchemy.orm import Session

from src.conversation import Conversation, ChatMessage, Role, MODEL, OPENROUTER_API_KEY
from src.db import (
    Entity,
    EntityAlias,
    Fact,
    MessageSummary,
    Message,
    get_entity_by_name,
)

MAX_CHAT_WORDS_BEFORE_CONSOLIDATION = 2500
NUM_WORDS_TO_CONSOLIDATE = 1250


class EntityModel(BaseModel):
    aliases: List[str] = Field(
        description="Names for the entity. Make the first one the most clear and canonical, as it will be used by default."
    )
    brief: str = Field(
        description="1-2 sentence summary of the entity and your relationship with it."
    )


class UpdatedEntityModel(EntityModel):
    index: int


class ContextItemModel(BaseModel):
    importance: conint(ge=1, le=10) = Field(
        description="Strategic importance. 1 is trivial, 5 is probably important, and 10 is absolutely critical"
    )
    salience: conint(ge=1, le=10) = Field(
        description="Emotional valence. 1 is has no affect on you, 5 has some emotional impact, and 10 is a burned in part of your identity"
    )


class FactModel(ContextItemModel):
    body: str = Field(
        "~1 sentence. Facts should be largely timeless, not about events or current status"
    )
    relevant_entity_names: List[str] = Field(
        description="Names of any entities related to this fact. You must use one of their aliases exactly.",
    )

    def __str__(self):
        return f"I:{self.importance} S:{self.salience} {self.body}"


class UpdatedFactModel(FactModel):
    index: int


class MessageSummaryModel(ContextItemModel):
    body: str = Field(
        description="Stay concise and focus on events rather than factual statements (handled elsewhere). Write it like how you'd recall a memory, focusing on what stands out or seems important."
    )
    relevant_entity_names: List[str] = Field(
        description="Names of any entities in or closely related to these events. You must use one of their aliases exactly.",
    )


class ConsolidateResult(BaseModel):
    summary: MessageSummaryModel = Field(
        description="Summary of the new messages, first person, from the perspective of 'Me'. Focus on what you'd want to remember, being concise."
    )
    new_entities: List[EntityModel] = Field(
        description="New entities not already in the context. Entities should be things deserving of a wiki-page in your personal notes, not just any noun."
    )
    updated_entities: List[UpdatedEntityModel] = Field(
        description="For any entities now made out of date, write a new version to replace them."
    )
    new_facts: List[FactModel] = Field(
        description="New things to remember, not already in the context. Individual meaningful statements worth remembering."
    )
    updated_facts: List[UpdatedFactModel] = Field(
        description="For any facts in the context that are now made out of date, write a new version to replace them."
    )

    # Get new key info very rarely? Leave out for now


consolidator_agent = Agent(
    model=OpenAIModel(
        MODEL.replace("openrouter/", ""),
        provider=OpenAIProvider(
            base_url="https://openrouter.ai/api/v1",
            api_key=OPENROUTER_API_KEY,
        ),
    ),
    result_type=ConsolidateResult,
)


def should_consolidate(conversation: Conversation):
    non_hidden_messages = [msg for msg in conversation.messages if not msg.hidden]
    total_words = sum([msg.num_words for msg in non_hidden_messages])
    return total_words > MAX_CHAT_WORDS_BEFORE_CONSOLIDATION


async def consolidate(session: Session, conversation: Conversation):
    consolidation_window, start_index = get_consolidation_window_and_index(conversation)
    consolidator_context = await get_consolidator_context(consolidation_window)
    for message in consolidation_window:
        message.hidden = True
    # todo get consolidator context from context.py
    recent_messages = []
    for message in consolidation_window:
        if message.role == Role.ASSISTANT:
            role = "me"
        else:
            role = "user"
        message_string = f"{role}: {message.content}"
        recent_messages.append(message_string)
    recent_messages_text = "\n\n".join(recent_messages)

    prompt = f"""\
CONTEXT:
{consolidator_context}


RECENT MESSAGES:
{recent_messages_text}

<<Chat Paused for Memory Consolidation>>
It's time to update and maintain your memory system based off of recent events.
For simplicity, speak in first person, where your character is "I". Out of character text can be written OOC: ...
"""
    result = await consolidator_agent.run(prompt)

    # update db

    for alias_row in result.data.new_entities:
        new_entity = Entity(brief=alias_row.brief)
        for alias in alias_row.aliases:
            new_entity.aliases.append(EntityAlias(alias=alias))
        session.add(new_entity)
    session.commit()

    new_facts = []
    for fact_data in result.data.new_facts:
        new_fact = Fact(
            body=fact_data.body,
            importance=fact_data.importance,
            salience=fact_data.salience,
            created_at_message_index=start_index,
        )
        session.add(new_fact)

        relevant_entities = [
            get_entity_by_name(session, entity_name)
            for entity_name in fact_data.relevant_entity_names
        ]
        relevant_entities = [entity for entity in relevant_entities if entity]
        new_fact.entities = relevant_entities

        new_facts.append(new_fact)

    entities_in_scene = [
        get_entity_by_name(session, entity_name)
        for entity_name in result.data.summary.relevant_entity_names
    ]

    new_message_summary = MessageSummary(
        # TODO created at message index
        importance=result.data.summary.importance,
        salience=result.data.summary.salience,
        body=result.data.summary.body,
        facts=new_facts,
        entities=entities_in_scene,
        messages=[
            Message(body=msg.content, sender=msg.role) for msg in consolidation_window
        ],
        created_at_message_index=start_index,
    )

    session.add(new_message_summary)

    session.commit()
    return


def get_consolidation_window_and_index(conversation: Conversation):
    start_index = next(
        (i for i, msg in enumerate(conversation.messages) if not msg.hidden), None
    )

    # find back half of unhidden messages
    non_hidden_messages = [msg for msg in conversation.messages if not msg.hidden]

    split_index = 0
    total_words_in_window = 0
    while total_words_in_window < NUM_WORDS_TO_CONSOLIDATE:
        split_index += 2
        total_words_in_window += non_hidden_messages[split_index - 1].num_words
        total_words_in_window += non_hidden_messages[split_index].num_words

    consolidate_window = non_hidden_messages[:split_index]
    return consolidate_window, start_index


class ConsolidatorContext(BaseModel):
    past_message_summaries: List[MessageSummaryModel]
    entities: List[EntityModel]
    facts: List[FactModel]

    def __str__(self):
        parts = []
        if self.past_message_summaries:
            parts.append("SUMMARIES OF PAST MESSAGES:")
            parts.append(
                "\n\n".join([str(summary) for summary in self.past_message_summaries])
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

        return "\n\n".join(parts)


async def get_consolidator_context(
    consolidation_window: List[ChatMessage],
) -> ConsolidatorContext:

    context_summaries = []  # todo use db
    entities = []
    facts = []
    return ConsolidatorContext(
        past_message_summaries=context_summaries, entities=entities, facts=facts
    )
