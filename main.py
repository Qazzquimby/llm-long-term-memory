from memory import MemorySystem


async def conversation():
    memory = MemorySystem()
    
    print("Conversation started (type 'quit' to end)")
    while True:
        user_input = input("> ")
        if user_input.lower() == 'quit':
            break
            
        response = await memory.process_message(user_input)
        print(f"Bot: {response}\n")


if __name__ == "__main__":
    import asyncio
    asyncio.run(conversation())
