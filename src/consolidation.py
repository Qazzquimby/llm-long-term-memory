from typing import List

from pydantic import BaseModel, Field
from pydantic_ai.models.openai import OpenAIModel
from pydantic_ai.providers.openai import OpenAIProvider
from sqlalchemy.orm import Session

from src.architect_formatter_agent import ArchitectFormatterAgent
from src.context import (
    get_consolidator_context,
    EntityModel,
    FactModel,
    MessageSummaryModel,
)
from src.conversation import (
    Conversation,
    Role,
    OPENROUTER_API_KEY,
    r1,
    gpt_4o_mini,
)
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


class UpdatedEntityModel(EntityModel):
    index: int


importance_string_to_value = {
    "trivial": 1,
    "probably not important": 2,
    "probably important": 3,
    "clearly important": 4,
    "critically important": 5,
}


class UpdatedFactModel(FactModel):
    index: int


class ConsolidateResult(BaseModel):
    summary: MessageSummaryModel = Field(
        description="Summary of the new messages, first person, from the perspective of 'Me'. Focus on what will be strategically useful to remember, being concise."
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


consolidator_agent = ArchitectFormatterAgent(
    architect_model=OpenAIModel(
        r1.replace("openrouter/", ""),
        provider=OpenAIProvider(
            base_url="https://openrouter.ai/api/v1",
            api_key=OPENROUTER_API_KEY,
        ),
    ),
    formatter_model=OpenAIModel(
        gpt_4o_mini.replace("openrouter/", ""),
        provider=OpenAIProvider(
            base_url="https://openrouter.ai/api/v1",
            api_key=OPENROUTER_API_KEY,
        ),
    ),
    response_type=ConsolidateResult,
)


def should_consolidate(conversation: Conversation):
    non_hidden_messages = [msg for msg in conversation.messages if not msg.hidden]
    total_words = sum([msg.num_words for msg in non_hidden_messages])
    return total_words > MAX_CHAT_WORDS_BEFORE_CONSOLIDATION


async def consolidate(session: Session, conversation: Conversation):
    print("CONSOLIDATING")
    consolidation_window, end_index = get_consolidation_window_and_end_index(
        conversation
    )
    consolidator_context = await get_consolidator_context(
        session=session, consolidation_window=consolidation_window
    )
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
    result.data: ConsolidateResult

    # update db

    for entity_row in result.data.new_entities:
        new_entity = Entity(brief=entity_row.brief)
        for alias in entity_row.aliases:
            new_entity.aliases.append(EntityAlias(alias=alias))
        session.add(new_entity)
    session.commit()

    new_facts = []
    for fact_data in result.data.new_facts:
        new_fact = Fact(
            body=fact_data.body,
            importance=importance_string_to_value.get(fact_data.importance),
            created_at_message_index=end_index,
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
    entities_in_scene = [entity for entity in entities_in_scene if entity]

    db_messages = []
    for chat_message in consolidation_window:
        if chat_message.db_id:
            db_message = session.query(Message).get(chat_message.db_id)
            if db_message:
                db_messages.append(db_message)
    new_message_summary = MessageSummary(
        importance=importance_string_to_value.get(result.data.summary.importance),
        body=result.data.summary.body,
        facts=new_facts,
        entities=entities_in_scene,
        messages=db_messages,
        created_at_message_index=end_index,
    )

    session.add(new_message_summary)

    session.commit()

    # do this last so that the chat loop still sees the messages while consolidating
    for message in consolidation_window:
        message.hidden = True
    return


def get_consolidation_window_and_end_index(conversation: Conversation):
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
    end_index = start_index + len(consolidate_window)
    return consolidate_window, end_index
