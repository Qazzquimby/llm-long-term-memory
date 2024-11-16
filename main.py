from memory import MemorySystem
from core import Prompt, MODEL
from commands import SYSTEM_PROMPT


async def conversation():
    memory = MemorySystem()
    prompt = Prompt()
    prompt.add_message(SYSTEM_PROMPT, role="system")
    
    print("Conversation started (type 'quit' to end)")
    while True:
        user_input = input("> ")
        if user_input.lower() == 'quit':
            break
            
        prompt.add_message(user_input, role="user")
        response = prompt.run(MODEL)
        
        # Process any commands in the response
        if "/scene" in response:
            # Create new scene from current conversation
            await memory.create_scene(
                content="\n".join([m["content"] for m in prompt.messages]),
                tags=[]  # We can extract tags from the /tag command later
            )
            # Clear conversation history but keep system prompt
            prompt = Prompt()
            prompt.add_message(SYSTEM_PROMPT, role="system")
            
        print()  # Extra line for readability


if __name__ == "__main__":
    import asyncio
    asyncio.run(conversation())
