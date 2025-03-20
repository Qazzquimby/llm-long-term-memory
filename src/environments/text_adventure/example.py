"""
Example usage of the Anchorhead text adventure library.
"""

from main import AnchorheadGame

def run_scripted_commands():
    """
    Example of running a series of scripted commands.
    """
    game = AnchorheadGame(headless=True)
    
    try:
        # Start the game
        print("Starting Anchorhead...")
        initial_text = game.start()
        print(f"Game started with {len(initial_text)} characters of text")
        
        # Run a sequence of commands
        commands = [
            "look",
            "inventory",
            "examine me",
            "north",
            "look"
        ]
        
        for command in commands:
            print(f"\nExecuting: {command}")
            response = game.send_command(command)
            print(f"Response ({len(response)} chars): {response[:150]}...")
            
    finally:
        game.close()

def save_transcript():
    """
    Example of saving a game transcript to a file.
    """
    game = AnchorheadGame(headless=True)
    transcript = []
    
    try:
        # Start the game
        print("Starting Anchorhead...")
        initial_text = game.start()
        transcript.append(("GAME", initial_text))
        
        # Run a sequence of commands
        commands = [
            "look",
            "inventory",
            "examine me",
            "north",
            "look"
        ]
        
        for command in commands:
            transcript.append(("PLAYER", command))
            response = game.send_command(command)
            transcript.append(("GAME", response))
            
        # Save transcript to file
        with open("anchorhead_transcript.txt", "w", encoding="utf-8") as f:
            for role, text in transcript:
                f.write(f"--- {role} ---\n")
                f.write(text)
                f.write("\n\n")
                
        print("Transcript saved to anchorhead_transcript.txt")
            
    finally:
        game.close()

if __name__ == "__main__":
    print("Running scripted commands example:")
    run_scripted_commands()
    
    print("\n" + "="*50 + "\n")
    
    print("Running transcript saving example:")
    save_transcript()
