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


class AnchorheadGame:
    def __init__(self, headless=True):
        self.headless = headless
        self.driver = None
        self.game_path = Path("anchor.z8.html")
        self.game_url = f"file://{os.path.abspath(self.game_path)}"

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

        return self.get_game_text()

    def send_command(self, command) -> str:
        if not self.driver:
            raise RuntimeError("Game not started. Call start() first.")

        # input_element = self.driver.find_element(By.ID, "gameport")

        # input_element.send_keys(command)
        # input_element.send_keys(Keys.RETURN)

        actions = ActionChains(self.driver)
        actions.send_keys(command).perform()
        actions.send_keys(Keys.ENTER).perform()

        time.sleep(0.5)

        return self.get_game_text()

    def get_game_text(self) -> str:
        if not self.driver:
            raise RuntimeError("Game not started. Call start() first.")

        # gameport = self.driver.find_element(By.ID, "gameport")

        grid = self.driver.find_element(By.CLASS_NAME, "GridWindow")
        buffer = self.driver.find_element(By.CLASS_NAME, "BufferWindow")

        grid_soup = BeautifulSoup(grid.get_attribute("innerHTML"), "html.parser")
        buffer_soup = BeautifulSoup(buffer.get_attribute("innerHTML"), "html.parser")

        grid_text = grid_soup.get_text(separator="\n", strip=False)
        buffer_text = buffer_soup.get_text(separator="\n", strip=False)

        game_text = grid_text + "\n\n" + buffer_text

        return game_text

    def close(self):
        if self.driver:
            self.driver.quit()
            self.driver = None


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
