import uuid
from zep_python.client import Zep
from zep_python.types import Message

from conversation import Conversation, MODEL

API_KEY = "blarb"
BASE_URL = "http://localhost:8000"


class ZepMemoryPrompt(Conversation):
    def __init__(self, user_id=None, session_id=None):
        super().__init__()

        self.zep_client = Zep(
            api_key=API_KEY,
            base_url=BASE_URL,
        )

        self.user_id = user_id or uuid.uuid4().hex
        self.session_id = session_id or uuid.uuid4().hex

        try:
            self.zep_client.user.add(
                user_id=self.user_id,
                email=f"user_{self.user_id}@example.com",
                metadata={},
            )
        except:
            pass

        try:
            self.zep_client.memory.add_session(
                session_id=self.session_id, user_id=self.user_id, metadata={}
            )
        except:
            pass

    def _sync_messages_to_zep(self, messages: dict):
        zep_messages = [
            Message(
                role_type=message["role"],
                role=message["role"],
                content=message["content"],
            )
            for message in messages
        ]
        self.zep_client.memory.add(session_id=self.session_id, messages=zep_messages)

    def search_memory(self, query: str, search_scope="facts"):
        try:
            search_response = self.zep_client.memory.search_sessions(
                user_id=self.user_id,
                search_scope=search_scope,
                text=query,
            )

            if search_scope == "facts":
                return [r.fact for r in search_response.results]
            else:
                return search_response.results
        except Exception as e:
            print(f"Error searching memory: {e}")
            return []

    def run(
        self,
        model,
        should_print=True,
        api_key=None,
        include_memory=True,
        max_messages=None,
    ) -> str:
        if include_memory:
            self._inject_memories()

        response_text = super().run(
            model=model,
            should_print=should_print,
            api_key=api_key,
            max_messages=max_messages,
        )

        try:
            last_messages = self.messages[:-2]
            self._sync_messages_to_zep(messages=last_messages)
        except Exception as e:
            print("Couldn't add messages", e)

        return response_text

    def _inject_memories(self):
        memories = self._fetch_relevant_memories()
        if memories and (
            memories.get("relevant_facts") or memories.get("relevant_messages")
        ):
            memory_text = self._format_memories_for_prompt(memories)
            if memory_text:
                self.add_message(memory_text, role="system", ephemeral=True)

    def _fetch_relevant_memories(self):
        try:
            # Get the latest user message to use as search context
            recent_messages = self.messages[-4:]
            latest_messages_text = "\n\n".join(
                [msg["content"] for msg in recent_messages]
            )

            facts_search = self.zep_client.memory.search_sessions(
                user_id=self.user_id,
                search_scope="facts",
                text=latest_messages_text,
                limit=25,
            )
            relevant_facts = (
                [r.fact for r in facts_search.results] if facts_search.results else []
            )

            messages_search = self.zep_client.memory.search_sessions(
                user_id=self.user_id,
                search_scope="messages",
                text=latest_messages_text,
                limit=10,
            )
            relevant_messages = (
                messages_search.results if messages_search.results else []
            )

            return {
                "relevant_facts": relevant_facts,
                "relevant_messages": relevant_messages,
            }
        except Exception as e:
            print(f"Error fetching relevant memories: {e}")
            return {}

    def _format_memories_for_prompt(self, memories):
        memory_parts = []

        facts = memories.get("relevant_facts", [])
        if facts:
            memory_parts.append("### Relevant information from memory:")
            for i, fact in enumerate(facts, 1):
                memory_parts.append(f"{i}. {fact}")
            memory_parts.append("")

        relevant_messages = memories.get("relevant_messages", [])
        if relevant_messages:
            memory_parts.append("### Relevant conversation history:")
            for relevant_message in relevant_messages:
                if hasattr(relevant_message, "message") and relevant_message.message:
                    message = relevant_message.message
                    memory_parts.append(f"{message.role}: {message.content}")
            memory_parts.append("")

        if memory_parts:
            return "\n".join(memory_parts)
        else:
            return ""

    def update_user_info(
        self, email=None, first_name=None, last_name=None, metadata=None
    ):
        try:
            # Build update params
            update_params = {"user_id": self.user_id}
            if email:
                update_params["email"] = email
            if first_name:
                update_params["first_name"] = first_name
            if last_name:
                update_params["last_name"] = last_name
            if metadata:
                update_params["metadata"] = metadata

            # Update user
            self.zep_client.user.add(**update_params)
            return True
        except Exception as e:
            print(f"Error updating user: {e}")
            return False


def main():
    user_id = "85a63a3747264ab2af5db3057f1f3d62"
    session_id = "ea2cfe8101094286a884262c1e777d73"
    prompt = ZepMemoryPrompt(user_id=user_id, session_id=session_id)

    for i in range(100):
        user_input = input()
        if user_input.lower() == "quit":
            break
        prompt.add_message(user_input, role="user")
        prompt.run(model=MODEL, include_memory=True)


if __name__ == "__main__":
    main()


# todo load past session memories. It seems to be starting fresh.
#  chat history is really long
