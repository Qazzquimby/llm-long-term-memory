from typing import List

from sqlalchemy.orm import Session

from src.conversation import Conversation, ChatMessage, Role, MODEL

MAX_CHAT_WORDS_BEFORE_CONSOLIDATION = 2500
NUM_WORDS_TO_CONSOLIDATE = 1250


def should_consolidate(conversation: Conversation):
    non_hidden_messages = [msg for msg in conversation.messages if not msg.hidden]
    total_words = sum([msg.num_words for msg in non_hidden_messages])
    return total_words > MAX_CHAT_WORDS_BEFORE_CONSOLIDATION


async def consolidate(session: Session, conversation: Conversation):
    consolidation_window = get_consolidation_window(conversation)
    summary = await generate_summary(consolidation_window)


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


async def generate_summary(consolidation_window: List[ChatMessage]):
    conversation = Conversation()

    message_strings = []
    for message in consolidation_window:
        if message.role == Role.ASSISTANT:
            role = "me"
        else:
            role = "user"
        message_string = f"{role}: {message.content}"
        message_strings.append(message_string)

    messages_text = "\n\n".join(message_strings)

    # todo length limit?
    prompt = f"""\
Please summarize the following conversation to be very concise, while not losing important meaning.
The "" messages were written by you. Write in first person, and focus on what you'd want to remember for later.
 
{messages_text}
"""

    conversation.add_message(message=ChatMessage(content=prompt, role=Role.SYSTEM))
    response = await conversation.run(MODEL)

    return response
