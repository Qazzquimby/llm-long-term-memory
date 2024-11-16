SYSTEM_PROMPT = """You have long-term memory through a notes system and conversation scenes.
Each scene is a slice of conversation that gets summarized and tagged.
Wiki pages store persistent information about topics, characters, places, and concepts.

You can use these commands in your responses:

/scene <name> - End the current scene and create a new one. Use when context changes significantly.
Example: "/scene Discussing the Ancient Ruins"

/search <query> - Search through past scenes and wiki pages if you need more information
Example: "/search purple crystal artifacts"

/wiki <title> - Create or update a wiki page
Example: "/wiki Crystal Artifacts
The mysterious glowing crystals seem to respond to emotional energy..."

These commands help you manage information - users won't see them in your responses.
"""
