from typing import List

from pydantic import BaseModel, Field, conint
from pydantic_ai import Agent
from pydantic_ai.models.openai import OpenAIModel
from pydantic_ai.providers.openai import OpenAIProvider
from sqlalchemy.orm import Session

from src.context import AssistantContext
from src.conversation import MODEL, OPENROUTER_API_KEY, Conversation, Role
from src.db import UsageRecord


class ContextItemEvaluation(BaseModel):
    id: int = Field(description="The ID of the context item being evaluated")
    usefulness: conint(ge=0, le=2) = Field(
        description="""\
How useful this item was in generating the new message:
0 = Not useful or relevant to the response. Just noise.
1 = Somewhat useful or relevant. Maybe wasn't used, but could have been. 
2 = Clearly useful and influenced the response.
"""
    )


class ContextEvaluationResult(BaseModel):
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


async def evaluate_context(
    session: Session,
    context: AssistantContext,
    conversation: Conversation,
):
    new_message = conversation.messages[-1]

    # Skip evaluation if there are no context items
    if not (context.facts or context.entities or context.message_summaries):
        return

    context_items_by_id = {}
    for item in context.facts:
        context_items_by_id[item.id] = item
    for item in context.message_summaries:
        context_items_by_id[item.id] = item

    context_parts = []
    if context.entities:
        context_parts.append(
            "## Key Entities (You don't grade these, they're just for your information):"
        )
        for entity in context.entities:
            try:
                context_parts.append(f"{entity.aliases[0].alias}: {entity.brief}")
            except IndexError:
                pass

    context_parts.append("\n# Things for you to evaluate:")
    if context.message_summaries:
        for summary in context.message_summaries:
            context_parts.append(f"- [ID:{summary.id}] {summary.body}")

    if context.facts:
        for fact in context.facts:
            context_parts.append(f"- [ID:{fact.id}] {fact.body}")

    context_str = "\n".join(context_parts)

    visible_messages = [msg for msg in conversation.messages[:-1] if not msg.hidden]
    conversation_str = "\n\n".join(
        [
            f"{'User' if msg.role == Role.USER else 'Me'}: {msg.content}"
            for msg in visible_messages
        ]
    )

    # Format the new message for the evaluator
    new_message_str = f"Assistant's new response: {new_message.content}"

    # Create the prompt for the evaluator
    prompt = f"""\
You are maintaining your memory system, trying to prevent it from building up with irrelevant context and finetune it over time.
You were having the conversation below (CHAT HISTORY), and you were given the CONTEXT to write your NEW MESSAGE. 
Now you're evaluating how useful each piece of CONTEXT was for generating that NEW MESSAGE.

CHAT HISTORY
{conversation_str}

CONTEXT
{context_str}

NEW MESSAGE (the message you just sent, for which you are evaluating the context's usefulness)
{new_message_str}

Please evaluate how useful each piece of context was for generating your response.
"""

    # Run the evaluator agent
    result = await context_evaluator_agent.run(prompt)

    debugging_string_parts = []
    for evaluation in result.data.evaluations:
        item = context_items_by_id[evaluation.id]
        debugging_string_parts.append(f"{evaluation.usefulness}: {item}")
    debugging_string = "\n".join(debugging_string_parts)

    message_index = len(conversation.messages)

    for evaluation in result.data.evaluations:
        item_id = evaluation.id

        if item_id in context_items_by_id:
            context_item = context_items_by_id[item_id]
            usage_record = UsageRecord(
                context_item_id=context_item.id,
                created_at_message_index=message_index,
                usefulness=evaluation.usefulness,
            )
            session.add(usage_record)
    session.commit()
