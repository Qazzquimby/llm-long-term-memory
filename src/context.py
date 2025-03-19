from typing import List, Dict

from pydantic import BaseModel, Field, conint
from pydantic_ai import Agent
from pydantic_ai.models.openai import OpenAIModel
from pydantic_ai.providers.openai import OpenAIProvider
from sqlalchemy.orm import Session

from db import (
    MessageSummary,
    Entity,
    Fact,
    ContextItem,
    record_context_item_usage,
)
from src.conversation import ChatMessage, Role, MODEL, OPENROUTER_API_KEY, Conversation


class ContextItemEvaluation(BaseModel):
    """Evaluation of a single context item's usefulness"""

    id: int = Field(description="The ID of the context item being evaluated")
    usefulness: conint(ge=0, le=2) = Field(
        description="How useful this item was in the conversation: 0=not useful, 1=somewhat useful, 2=very useful"
    )


class ContextEvaluationResult(BaseModel):
    """Results of evaluating all context items"""

    evaluations: List[ContextItemEvaluation] = Field(
        description="Evaluations for each context item that was provided"
    )


context_evaluator_agent = Agent(
    model=OpenAIModel(
        MODEL.replace("openrouter/", ""),
        provider=OpenAIProvider(
            base_url="https://openrouter.ai/api/v1",
            api_key=OPENROUTER_API_KEY,
        ),
    ),
    result_type=ContextEvaluationResult,
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

        # 1. Entity briefs
        if self.entities:
            context_parts.append("## Key Entities:")
            for entity in self.entities:
                context_parts.append(f"- [ID:{entity.id}] {entity.brief}")

        # 2. Message summaries (oldest to newest)
        if self.message_summaries:
            context_parts.append("\n## Conversation Summary:")
            for summary in self.message_summaries:
                context_parts.append(f"- [ID:{summary.id}] {summary.body}")

        # 3. Relevant facts/theories/questions/objectives
        if self.facts:
            context_parts.append("\n## Active Knowledge:")

            if self.facts:
                context_parts.append("\nFacts:")
                for fact in self.facts:
                    context_parts.append(f"- [ID:{fact.id}] {fact.body}")

        return "\n".join(context_parts)


def get_assistant_context(session: Session) -> AssistantContext:
    context = AssistantContext(session=session)
    return context


async def evaluate_context(
    session: Session,
    context: AssistantContext,
    conversation: Conversation,
):

    new_message = conversation.messages[-1]

    # Skip evaluation if there are no context items
    if not (context.facts or context.entities or context.message_summaries):
        return

    # Create a mapping of context items by ID for easy lookup
    context_items_by_id = {}

    # Add all context items to the mapping
    for item in context.facts:
        context_items_by_id[item.id] = item

    for item in context.entities:
        context_items_by_id[f"entity-{item.id}"] = item

    for item in context.message_summaries:
        context_items_by_id[item.id] = item

    # Format the context for the evaluator
    context_str = str(context)

    # Format the message for the evaluator
    message_str = f"Your response: {new_message.content}"

    # Create the prompt for the evaluator
    prompt = f"""\
You are maintaining your memory system, trying to prevent it from building up with irrelevant context and finetune it over time.
You were just given context to continue a conversation, and now you're evaluating how useful each piece of context was for generating your answer.
Please rate each context item on a scale of 0-2:
0 = Not useful or relevant to the response. Just noise.
1 = Somewhat useful or relevant. 
2 = Clearly useful and influenced the response.
"""

# todo improve prompt

    # Run the evaluator agent
    result = await context_evaluator_agent.run(prompt)

    message_index = len(conversation.messages)

    # Record usage for each evaluated item
    for evaluation in result.data.evaluations:
        if evaluation.id in context_items_by_id:
            context_item = context_items_by_id[evaluation.id]
            record_context_item_usage(
                session=session,
                context_item=context_item,
                message_index=message_index,
                usefulness=evaluation.usefulness,
            )
