import os
import asyncio
from pathlib import Path
from dataclasses import dataclass
from typing import List
from selenium import webdriver
from selenium.webdriver import ActionChains
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from bs4 import BeautifulSoup
import difflib

from tqdm import tqdm


@dataclass
class ScreenState:
    grid_lines: List[str]
    buffer_lines: List[str]

    def __str__(self):
        grid_text = "\n".join(self.grid_lines)
        buffer_text = "\n".join(self.buffer_lines)
        return grid_text + "\n\n" + buffer_text

    def is_similar_to(self, other):
        if not isinstance(other, ScreenState):
            return False

        grid_similarity = difflib.SequenceMatcher(
            None, "\n".join(self.grid_lines), "\n".join(other.grid_lines)
        ).ratio()

        buffer_similarity = difflib.SequenceMatcher(
            None, "\n".join(self.buffer_lines), "\n".join(other.buffer_lines)
        ).ratio()

        return grid_similarity > 0.9 and buffer_similarity > 0.9

    def get_added_content(self, updated_state):
        if not isinstance(updated_state, ScreenState):
            return ""

        added_grid_lines = self._get_added_lines(
            self.grid_lines, updated_state.grid_lines
        )
        added_buffer_lines = self._get_added_lines(
            self.buffer_lines, updated_state.buffer_lines
        )

        result = []
        if added_grid_lines:
            result.append("\n".join(added_grid_lines))
        if added_buffer_lines:
            result.append("\n".join(added_buffer_lines))

        return "\n\n".join(result)

    @staticmethod
    def _get_added_lines(old_lines, updated_lines):
        diff = difflib.ndiff(old_lines, updated_lines)
        added_lines = []
        for line in diff:
            if line.startswith("+ "):
                added_lines.append(line[2:])
            elif line.startswith("? "):
                continue

        return added_lines


class AnchorheadGame:
    def __init__(self, headless=True):
        self.headless = headless
        self.driver = None
        self.actions = None

        self.game_path = Path("environments/text_adventure/anchor.z8.html")
        self.game_url = f"file://{os.path.abspath(self.game_path)}"
        self.last_screen_state = None

    async def start(self, setup_commands=None) -> str:
        options = Options()
        if self.headless:
            options.add_argument("--headless")

        self.driver = webdriver.Chrome(options=options)
        self.driver.get(self.game_url)
        self.actions = ActionChains(self.driver)

        WebDriverWait(self.driver, 10).until(
            EC.presence_of_element_located((By.ID, "gameport"))
        )

        await asyncio.sleep(1)
        self.last_screen_state = await self.get_screen_state()

        await self.send_commands([""], get_response=False)  # pass title screen
        await self.send_commands([""], get_response=False)  # pass intro screen
        await self.send_commands([""], get_response=True)  # pass start of day 1

        if setup_commands:
            print(f"Replaying {len(setup_commands)} commands...")
            added_content = None
            for commands in tqdm(setup_commands):
                added_content = await self.send_commands(commands)
            return str(added_content)
        else:
            return str(self.last_screen_state)

    async def send_commands(self, commands: List[str], get_response=True) -> str:
        if not self.driver:
            raise RuntimeError("Game not started. Call start() first.")

        # todo doesn't cleanly handle new day "anykeys" or arrowscreen movement.
        #  its also possible menus aren't properly displayed to the llm

        for command_i, command in enumerate(commands):

            self.actions.send_keys(command).perform()
            self.actions.send_keys(Keys.RETURN).perform()
            await asyncio.sleep(0.2)

            if get_response and command_i == len(commands) - 1:
                added_content = None
                updated_state = None
                for attempt in range(10):
                    updated_state = await self.get_screen_state()
                    added_content = self.last_screen_state.get_added_content(
                        updated_state
                    )
                    if added_content:
                        break
                    await asyncio.sleep(0.1)

                self.last_screen_state = updated_state
                if added_content:
                    return added_content
                else:
                    print("WARN: No change after inputting command:", command)
                    return str(updated_state)

    def _did_unexpected_screen_change(self, updated_state: ScreenState, command: str):
        if self.last_screen_state is None:
            return False

        if not updated_state.is_similar_to(self.last_screen_state):
            return True

        # Check if command is visible at the end of any grid line
        for line in updated_state.grid_lines:
            if line.endswith(command):
                return False

        return True

    async def get_screen_state(self) -> ScreenState:
        if not self.driver:
            raise RuntimeError("Game not started. Call start() first.")
        await asyncio.sleep(0.5)

        grid = self.driver.find_element(By.CLASS_NAME, "GridWindow")
        buffer = self.driver.find_element(By.CLASS_NAME, "BufferWindow")

        grid_soup = BeautifulSoup(grid.get_attribute("innerHTML"), "html.parser")
        buffer_soup = BeautifulSoup(buffer.get_attribute("innerHTML"), "html.parser")

        grid_html_lines = grid_soup.find_all("div", class_="GridLine")
        grid_lines = [clean(line.get_text()) for line in grid_html_lines]

        buffer_html_lines = buffer_soup.find_all("div", class_="BufferLine")
        buffer_lines = [clean(line.get_text()) for line in buffer_html_lines]

        return ScreenState(grid_lines=grid_lines, buffer_lines=buffer_lines)

    def close(self):
        if self.driver:
            self.driver.quit()
            self.driver = None


def clean(text):
    return text.replace("\xa0", "")


async def play_interactive():
    game = AnchorheadGame(headless=False)

    try:
        initial_text = await game.start()
        print("Game started!")
        print("-" * 50)
        print(initial_text)

        while True:
            command = input("\n> ")
            if command.lower() in ["quit", "exit"]:
                break

            response = await game.send_commands([command])
            print(response)

    except KeyboardInterrupt:
        print("\nExiting game...")
    finally:
        game.close()


if __name__ == "__main__":
    asyncio.run(play_interactive())


# todo track last milestone.
#  have dict of next milestone -> hint
#  if spends long time before reaching next milestone, provide hint and reset counter.
