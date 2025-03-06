import uuid
from zep_python.client import Zep
from zep_python.types import Message

from conversation import Conversation, MODEL

API_KEY = "blarb"
BASE_URL = "http://localhost:8000"



class ZepMemoryPrompt(Conversation):
    """
    Enhanced Prompt class with Zep memory capabilities.
    Subclasses the original Prompt class to maintain compatibility.
    """

    def __init__(self, user_id=None,
                 session_id=None):
        # Initialize the parent Prompt class
        super().__init__()

        self.zep_client = Zep(
            api_key=API_KEY,
            base_url=BASE_URL,
        )

        # Initialize user and session
        self.user_id = user_id or uuid.uuid4().hex
        self.session_id = session_id or uuid.uuid4().hex

        self.zep_client.user.add(
            user_id=self.user_id,
            email=f"user_{self.user_id}@example.com",
            # Default email, can be updated later
            metadata={}
        )

        # Create session
        self.zep_client.memory.add_session(
            session_id=self.session_id,
            user_id=self.user_id,
            metadata={}
        )


    def add_message(self, message: str, role="user", ephemeral=False):
        """
        Override parent method to add Zep memory syncing

        Args:
            message (str): The message content
            role (str): One of "user", "assistant", "system"
            role_type (str, optional): Optional role type for Zep
        """
        # Call the parent class implementation to maintain original functionality
        super().add_message(message, role)

        if role == "user":
            self._sync_message_to_zep(message=message, role=role, role_type=role)

        return self

    def _sync_message_to_zep(self, message: str, role: str, role_type: str):
        """Sync a message to Zep memory"""
        try:
            # Convert to Zep message format
            zep_message = Message(
                role_type=role_type,
                role=role,
                content=message
            )

            # Add to Zep memory
            self.zep_client.memory.add(
                session_id=self.session_id,
                messages=[zep_message]
            )
        except Exception as e:
            print(f"Error syncing message to Zep: {e}")

    def get_memory(self, last_n=10):
        """
        Get the last N messages from memory

        Args:
            last_n (int): Number of messages to retrieve

        Returns:
            dict: Memory data including messages and relevant facts
        """
        try:
            memory = self.zep_client.memory.get(
                session_id=self.session_id,
                lastn=last_n
            )
            return {
                "messages": memory.messages,
                "relevant_facts": memory.relevant_facts
            }
        except Exception as e:
            print(f"Error retrieving memory: {e}")
            return {"messages": [], "relevant_facts": []}

    def search_memory(self, query: str, search_scope="facts"):
        """
        Search user memory across all sessions

        Args:
            query (str): The search query
            search_scope (str): Scope of search, one of "facts", "messages"

        Returns:
            list: Search results
        """
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

    def run(self, model, should_print=True, api_key=None, include_memory=True) -> str:
        """
        Override parent run method to include relevant memories

        Args:
            model: The model to use for completion
            should_print: Whether to print the response
            api_key: Optional API key for the completion service
            include_memory: Whether to include relevant memories in the prompt

        Returns:
            str: The model's response
        """
        # If memory inclusion is requested, fetch and add relevant memories
        if include_memory:
            self._inject_memories()

        # Get response using parent class implementation
        response_text = super().run(model, should_print, api_key)

        self._sync_message_to_zep(message=response_text, role="assistant", role_type="assistant")

        return response_text

    def _inject_memories(self):
        memories = self._fetch_relevant_memories()
        # Only inject if we retrieved memories
        if memories and (memories.get("relevant_facts") or memories.get(
                "relevant_messages")):
            # Format memories as a system message
            memory_text = self._format_memories_for_prompt(memories)

            # Insert the memory as a system message at the beginning of the conversation
            # We don't use add_message to avoid triggering another memory sync
            if memory_text:
                memory_msg = {"role": "system", "content": memory_text}
                # Insert after any existing system messages but before user/assistant messages
                system_end_idx = 0
                for i, msg in enumerate(self.messages):
                    if msg["role"] == "system":
                        system_end_idx = i + 1
                    else:
                        break

                self.add_message(memory_msg, role="system", ephemeral=True)



    def _fetch_relevant_memories(self):
        """
        Fetch memories relevant to the current conversation

        Returns:
            dict: Dictionary with relevant messages and facts
        """
        try:
            # Get the latest user message to use as search context
            recent_messages = self.messages[-4:]
            latest_messages_text = "\n\n".join([msg["content"] for msg in recent_messages])

            # Search for relevant facts
            facts_search = self.zep_client.memory.search_sessions(
                user_id=self.user_id,
                search_scope="facts",
                text=latest_messages_text,
                limit=25
            )
            relevant_facts = [r.fact for r in
                              facts_search.results] if facts_search.results else []

            # Search for relevant messages
            messages_search = self.zep_client.memory.search_sessions(
                user_id=self.user_id,
                search_scope="messages",
                text=latest_messages_text,
                limit=10
            )
            relevant_messages = messages_search.results if messages_search.results else []

            return {
                "relevant_facts": relevant_facts,
                "relevant_messages": relevant_messages
            }
        except Exception as e:
            print(f"Error fetching relevant memories: {e}")
            return {}

    def _format_memories_for_prompt(self, memories):
        """
        Format retrieved memories into a prompt-friendly string

        Args:
            memories (dict): Dictionary with relevant_facts and relevant_messages

        Returns:
            str: Formatted memory text for inclusion in prompt
        """
        memory_parts = []

        # Add relevant facts if any
        facts = memories.get("relevant_facts", [])
        if facts:
            memory_parts.append("### Relevant information from memory:")
            for i, fact in enumerate(facts, 1):
                memory_parts.append(f"{i}. {fact}")
            memory_parts.append("")

        # Add relevant message exchanges if any
        messages = memories.get("relevant_messages", [])
        if messages:
            memory_parts.append("### Relevant conversation history:")
            for msg in messages:
                # Format depends on the structure returned by Zep
                # Adjust as needed based on actual Zep response format
                if hasattr(msg, 'message'):
                    message = msg.message
                    memory_parts.append(f"{message.role}: {message.content}")
            memory_parts.append("")

        # Only return if we have content
        if memory_parts:
            return "\n".join(memory_parts)
        else:
            return ""

    def update_user_info(self, email=None, first_name=None, last_name=None,
                               metadata=None):
        """
        Update user information in Zep

        Args:
            email (str, optional): User email
            first_name (str, optional): User first name
            last_name (str, optional): User last name
            metadata (dict, optional): Additional user metadata
        """
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
    prompt = ZepMemoryPrompt()

    for i in range(100):
        user_input = input()
        if user_input.lower() == 'quit':
            break
        prompt.add_message(user_input, role="user")
        prompt.run(model=MODEL, include_memory=True)

if __name__ == '__main__':
    main()