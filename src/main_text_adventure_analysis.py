import asyncio
from src.environments.text_adventure.text_adventure_evaluation import analyze_game


async def main():
    metrics = await analyze_game()
    print(metrics)


if __name__ == "__main__":
    asyncio.run(main())
