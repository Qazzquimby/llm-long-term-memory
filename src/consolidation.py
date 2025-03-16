from typing import List

from pydantic import BaseModel, Field, conint
from pydantic_ai import Agent
from pydantic_ai.models.openai import OpenAIModel
from pydantic_ai.providers.openai import OpenAIProvider
from sqlalchemy.orm import Session

from src.conversation import Conversation, ChatMessage, Role, MODEL, OPENROUTER_API_KEY

MAX_CHAT_WORDS_BEFORE_CONSOLIDATION = 2500
NUM_WORDS_TO_CONSOLIDATE = 1250


class ContextItemModel(BaseModel):
    importance: conint(ge=1, le=10)
    salience: conint(ge=1, le=10)


class FactModel(ContextItemModel):
    body: str


class UpdatedFactModel(FactModel):
    index: int


class MessageSummaryModel(ContextItemModel):
    body: str


class ConsolidateResult(BaseModel):
    summary: str = Field(
        description="Summary of the new messages, first person, from the perspective of 'Me'. Focus on what you'd want to remember, being concise."
    )
    new_facts: List[FactModel] = Field(
        description="New things to remember, not already in the context. Individual meaningful statements worth remembering."
    )
    updated_facts: List[UpdatedFactModel] = Field(
        description="For any facts in the context that are now made out of date, write a new version to replace them."
    )

    # new_briefs = ...
    # updated_briefs = ...

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
    consolidation_window = get_consolidation_window(conversation)
    consolidator_context = await get_consolidator_context()

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
"""
    # later run async
    result = consolidator_agent.run_sync(prompt)
    return result  # todo use the result to update db


def get_consolidation_window(conversation: Conversation):
    # find back half of unhidden messages
    non_hidden_messages = [msg for msg in conversation.messages if not msg.hidden]

    split_index = 0
    total_words_in_window = 0
    while total_words_in_window < NUM_WORDS_TO_CONSOLIDATE:
        split_index += 1
        total_words_in_window += non_hidden_messages[split_index].num_words

    consolidate_window = non_hidden_messages[:split_index]
    return consolidate_window


class ConsolidatorContext(BaseModel):
    past_message_summaries: List[MessageSummaryModel]
    facts: List[FactModel]

    def __str__(self):
        parts = []
        if self.past_message_summaries:
            parts.append("SUMMARIES OF PAST MESSAGES:")
            parts.append(
                "\n\n".join([str(summary) for summary in self.past_message_summaries])
            )

        if self.facts:
            parts.append("FACTS:")
            parts.append(
                "\n\n".join([f"{i}: {fact}" for i, fact in enumerate(self.facts)])
            )

        return "\n\n".join(parts)


async def get_consolidator_context() -> ConsolidatorContext:
    context_summaries = []  # todo use db
    facts = []
    return ConsolidatorContext(past_message_summaries=context_summaries, facts=facts)
