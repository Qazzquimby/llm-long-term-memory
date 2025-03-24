import asyncio
import json
from src.environments.text_adventure.text_adventure_evaluation import analyze_game


async def main():
    print("Analyzing game progress...")

    db_paths = None  # ["memory.db", "other_run.db"]
    make_json = False

    metrics = await analyze_game(db_paths)

    if make_json:
        with open("game_metrics.json", "w") as f:
            json.dump(metrics, f, indent=2)

        if not db_paths:
            print(f"\nGame Analysis Results:")
            print(f"Total messages analyzed: {len(metrics['message_indices'])}")

            if metrics["message_indices"]:
                print(f"\nFinal metrics:")
                print(f"- Exploration score: {metrics['exploration_scores'][-1]}")
                print(f"- Puzzle score: {metrics['puzzle_scores'][-1]}")
                print(f"- Story progress: {metrics['story_progress'][-1]}%")
        else:
            print(f"\nAnalyzed {len(metrics)} game runs:")
            for run_name in metrics.keys():
                print(f"- {run_name}")


if __name__ == "__main__":
    asyncio.run(main())
