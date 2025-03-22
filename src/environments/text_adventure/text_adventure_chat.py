from typing import Optional, List

from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from sqlalchemy import desc

from src.chat_loop import ChatLoop
from src.environments.text_adventure.text_adventure import AnchorheadGame
from src.db import Message, MessageSummary, Role


class TextAdventureResponseModel(BaseModel):
    thinking: str = Field(description="Think things through before moving on.")
    command: str = Field(
        description="The verbatim command that will be input to the game."
    )


class TextAdventureChatLoop(ChatLoop):
    def __init__(
        self,
        session: Session,
        headless=True,
        human_observer=True,
    ):
        super().__init__(
            session=session,
            response_model=TextAdventureResponseModel,
        )
        self.game = AnchorheadGame(headless=headless)
        self.human_observer = human_observer

    async def get_environment_input(self, llm_message: Optional[str] = None) -> str:
        if not self.game.driver:
            # manually including first screens to avoid handling 'anykey' presses.
            start_prompt = """\
You are playing the classic text adventure Anchorhead!
You're not being an assistant, just playing a game and hopefully having a good time.
Respond with commands, and see if you can win.
\n\n
                             The oldest and strongest emotion of mankind                                
                             is fear, and the oldest and strongest kind                                 
                             of fear is fear of the unknown.                                            
                                                                                                        
                             -- H.P. Lovecraft                                                          
\n\n
November, 1997.
 
 
You take a deep breath of salty air as the first raindrops begin to spatter the pavement, and the swollen, slate-colored clouds that blanket the sky mutter ominous portents amongst themselves over the little coastal town of Anchorhead.
 
Squinting up into the glowering storm, you wonder how everything managed to happen so fast. The strange phone call over a month ago, from a lawyer claiming to represent the estate of some distant branch of Michael's family, was bewildering enough in itself... but then the sudden whirlwind of planning and decisions, legal details and travel arrangements, the packing up and shipping away of your entire home, your entire life...
 
Now suddenly here you are, after driving for the past two days straight, over a thousand miles away from the familiar warmth of Texas, getting ready to move into the ancestral mansion of a clan of relatives so far removed that not even Michael has ever heard of them. And you've only been married since June and none of this was any of your idea in the first place, and already it's starting to rain.
 
These days, you often find yourself feeling confused and uprooted.
 
You shake yourself and force the melancholy thoughts from your head, trying to focus on the errand at hand. You're to meet with the real estate agent and pick up the keys to your new house while Michael runs across town to take care of some paperwork at the university. He'll be back to pick you up in a few minutes, and then the two of you can begin the long, precarious process of settling in.
 
A sullen belch emanates from the clouds, and the rain starts coming down harder -- fat, cold drops smacking loudly against the cobblestones. Shouldn't it be snowing in New England at this time of year? With a sigh, you open your umbrella.
 
Welcome 
to 
Anchorhead...

\n\n

* THE FIRST DAY *                                             
                                                                                                        
                          I was far from home, and the spell of the eastern                             
                          sea was upon me.                                                              
                                                                                                        
                          -- H.P. Lovecraft    
                          
\n\n

"""
            setup_commands = self.extract_commands_from_db()
            game_start_text = await self.game.start(setup_commands=setup_commands)
            return start_prompt + game_start_text
        else:
            llm_response_obj = TextAdventureResponseModel.model_validate_json(
                llm_message
            )
            game_response = await self.game.send_command(llm_response_obj.command)

            if self.human_observer:
                print(f"\n\nGame Response:\n{game_response}\n\n")

            return game_response

    def extract_commands_from_db(self) -> List[str]:
        commands = []
        for message in self.conversation.messages:
            if message.sender == Role.ASSISTANT:
                response_obj = TextAdventureResponseModel.model_validate_json(
                    message.body
                )
                commands.append(response_obj.command)
        return commands
