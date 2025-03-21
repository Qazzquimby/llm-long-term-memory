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

    def get_added_content(self, other):
        if not isinstance(other, ScreenState):
            return ""

        added_grid_lines = self._get_added_lines(self.grid_lines, other.grid_lines)
        added_buffer_lines = self._get_added_lines(
            self.buffer_lines, other.buffer_lines
        )

        result = []
        if added_grid_lines:
            result.append("\n".join(added_grid_lines))
        if added_buffer_lines:
            result.append("\n".join(added_buffer_lines))

        return "\n\n".join(result)

    @staticmethod
    def _get_added_lines(old_lines, updated_lines):
        i = 0
        while (
            i < min(len(old_lines), len(updated_lines))
            and old_lines[i] == updated_lines[i]
        ):
            i += 1
        return updated_lines[i:]


class AnchorheadGame:
    def __init__(self, headless=True):
        self.headless = headless
        self.driver = None
        self.game_path = Path("anchor.z8.html")
        self.game_url = f"file://{os.path.abspath(self.game_path)}"
        self.last_screen_state = None

    async def start(self) -> str:
        options = Options()
        if self.headless:
            options.add_argument("--headless")

        self.driver = webdriver.Chrome(options=options)
        self.driver.get(self.game_url)

        WebDriverWait(self.driver, 10).until(
            EC.presence_of_element_located((By.ID, "gameport"))
        )

        await asyncio.sleep(1)

        self.last_screen_state = await self.get_screen_state()
        return str(self.last_screen_state)

    async def send_command(self, command) -> str:
        if not self.driver:
            raise RuntimeError("Game not started. Call start() first.")

        actions = ActionChains(self.driver)

        if command in ["up", "down", "left", "right"]:
            key_map = {
                "up": Keys.ARROW_UP,
                "down": Keys.ARROW_DOWN,
                "left": Keys.ARROW_LEFT,
                "right": Keys.ARROW_RIGHT,
            }
            actions.send_keys(key_map[command]).perform()
            await asyncio.sleep(0.5)
            updated_state = await self.get_screen_state()
            added_content = updated_state.get_added_content(self.last_screen_state)
            self.last_screen_state = updated_state
            return added_content

        actions.send_keys(command).perform()
        await asyncio.sleep(0.2)
        updated_state_after_typing = await self.get_screen_state()

        if self._did_unexpected_screen_change(
            updated_state_after_typing, command=command
        ):
            added_content = updated_state_after_typing.get_added_content(
                self.last_screen_state
            )
            self.last_screen_state = updated_state_after_typing
            return added_content

        actions.send_keys(Keys.ENTER).perform()
        await asyncio.sleep(0.5)
        updated_state = await self.get_screen_state()
        added_content = updated_state.get_added_content(self.last_screen_state)
        self.last_screen_state = updated_state
        return added_content

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

            response = await game.send_command(command)
            print(response)

    except KeyboardInterrupt:
        print("\nExiting game...")
    finally:
        game.close()


async def example_usage():
    game = AnchorheadGame(headless=True)

    try:
        initial_text = await game.start()
        print("Game started with text:")
        print(initial_text[:400] + "...")

        commands = ["look", "inventory", "examine me"]

        for command in commands:
            print(f"\nSending command: {command}")
            response = await game.send_command(command)
            print(f"Response: {response[:200]}...")

    finally:
        game.close()


if __name__ == "__main__":
    asyncio.run(play_interactive())
