import os
import asyncio
from pathlib import Path
from selenium import webdriver
from selenium.webdriver import ActionChains
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from bs4 import BeautifulSoup
import difflib


class AnchorheadGame:
    def __init__(self, headless=True):
        self.headless = headless
        self.driver = None
        self.game_path = Path("anchor.z8.html")
        self.game_url = f"file://{os.path.abspath(self.game_path)}"
        self.last_screen_state = ""

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

        self.last_screen_state = await self.get_game_text()
        return self.last_screen_state

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
            new_state = await self.get_game_text()
            new_content = self._extract_new_content(self.last_screen_state, new_state)
            self.last_screen_state = new_state
            return new_content

        actions.send_keys(command).perform()
        await asyncio.sleep(0.2)
        state_after_typing = await self.get_game_text()

        if self._did_unexpected_screen_change(
            self.last_screen_state, state_after_typing, command
        ):
            new_content = self._extract_new_content(
                self.last_screen_state, state_after_typing
            )
            self.last_screen_state = state_after_typing
            return new_content

        actions.send_keys(Keys.ENTER).perform()
        await asyncio.sleep(0.5)
        new_state = await self.get_game_text()
        new_content = self._extract_new_content(self.last_screen_state, new_state)
        self.last_screen_state = new_state
        return new_content

    def _did_unexpected_screen_change(self, old_state, new_state, command: str):
        if old_state == new_state:
            return False
        if new_state.endswith(command) and old_state in new_state:
            return False

        if abs(len(new_state) - len(old_state)) > len(command) + 5:
            return True

        similarity = difflib.SequenceMatcher(None, old_state, new_state).ratio()
        return similarity < 0.9

    def _extract_new_content(self, old_state, new_state):
        if old_state == new_state:
            return ""

        if old_state in new_state:
            idx = new_state.find(old_state) + len(old_state)
            return new_state[idx:].strip()

        old_lines = old_state.split("\n")
        new_lines = new_state.split("\n")

        i = 0
        while i < min(len(old_lines), len(new_lines)) and old_lines[i] == new_lines[i]:
            i += 1
        return '\n'.join(new_lines[i:]).strip()

    async def get_game_text(self) -> str:
        if not self.driver:
            raise RuntimeError("Game not started. Call start() first.")
        await asyncio.sleep(0.5)

        grid = self.driver.find_element(By.CLASS_NAME, "GridWindow")
        buffer = self.driver.find_element(By.CLASS_NAME, "BufferWindow")

        grid_soup = BeautifulSoup(grid.get_attribute("innerHTML"), "html.parser")
        buffer_soup = BeautifulSoup(buffer.get_attribute("innerHTML"), "html.parser")

        grid_html_lines = grid_soup.find_all("div", class_="GridLine")
        grid_lines = [clean(line.get_text()) for line in grid_html_lines]
        grid_text = "\n".join(grid_lines)

        buffer_html_lines = buffer_soup.find_all("div", class_="BufferLine")
        buffer_lines = [clean(line.get_text()) for line in buffer_html_lines]
        buffer_text = "\n".join(buffer_lines)

        return grid_text + "\n\n" + buffer_text

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
