import os
import time
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

    def start(self) -> str:
        options = Options()
        if self.headless:
            options.add_argument("--headless")

        self.driver = webdriver.Chrome(options=options)
        self.driver.get(self.game_url)

        WebDriverWait(self.driver, 10).until(
            EC.presence_of_element_located((By.ID, "gameport"))
        )

        time.sleep(1)

        self.last_screen_state = self.get_game_text()
        return self.last_screen_state

    def send_command(self, command) -> str:
        if not self.driver:
            raise RuntimeError("Game not started. Call start() first.")

        actions = ActionChains(self.driver)

        # Special case for single key commands like arrow keys
        if command in ["up", "down", "left", "right"]:
            key_map = {
                "up": Keys.ARROW_UP,
                "down": Keys.ARROW_DOWN,
                "left": Keys.ARROW_LEFT,
                "right": Keys.ARROW_RIGHT,
            }
            actions.send_keys(key_map[command]).perform()
            time.sleep(0.5)
            current_state = self.get_game_text()
            self.last_screen_state = current_state
            return current_state

        # For normal text commands
        actions.send_keys(command).perform()
        time.sleep(0.2)

        state_after_typing = self.get_game_text()

        # Check if the screen has already changed significantly
        # This could indicate a "press any key" situation
        if self._did_unexpected_screen_change(
            self.last_screen_state, state_after_typing, command
        ):
            self.last_screen_state = state_after_typing
            return state_after_typing

        # Otherwise, press Enter to submit the command
        actions.send_keys(Keys.ENTER).perform()
        time.sleep(0.5)

        current_state = self.get_game_text()
        self.last_screen_state = current_state
        return current_state

    def _did_unexpected_screen_change(self, old_state, new_state, command: str):
        # Return if the screen changed other than the command being added to the end
        # Otherwise, return True to indicate significant change

        # Simple case: if lengths are very different, screen has changed
        if abs(len(new_state) - len(old_state)) > len(command) + 5:
            return True

        # Check if the new state just has the command appended
        if new_state.endswith(command) and old_state in new_state:
            return False

        # Use difflib to calculate similarity
        similarity = difflib.SequenceMatcher(None, old_state, new_state).ratio()

        # If similarity is low, screen has changed significantly
        return similarity < 0.9

    def get_game_text(self) -> str:
        if not self.driver:
            raise RuntimeError("Game not started. Call start() first.")

        # gameport = self.driver.find_element(By.ID, "gameport")

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

        game_text = grid_text + "\n\n" + buffer_text

        return game_text  # todo only get new text

    def close(self):
        if self.driver:
            self.driver.quit()
            self.driver = None


def clean(text):
    return text.replace("\xa0", "")


def play_interactive():
    game = AnchorheadGame(headless=False)

    try:
        initial_text = game.start()
        print("Game started!")
        print("-" * 50)
        print(initial_text)

        while True:
            command = input("\n> ")
            if command.lower() in ["quit", "exit"]:
                break

            response = game.send_command(command)
            print(response)

    except KeyboardInterrupt:
        print("\nExiting game...")
    finally:
        game.close()


def example_usage():
    game = AnchorheadGame(headless=True)

    try:
        initial_text = game.start()
        print("Game started with text:")
        print(initial_text[:400] + "...")

        commands = ["look", "inventory", "examine me"]

        for command in commands:
            print(f"\nSending command: {command}")
            response = game.send_command(command)
            print(f"Response: {response[:200]}...")

    finally:
        game.close()


if __name__ == "__main__":
    play_interactive()
