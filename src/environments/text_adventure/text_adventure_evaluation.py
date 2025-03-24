import os
from dataclasses import dataclass
from typing import List, Dict, Optional
from sqlalchemy.orm import Session
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from src.db import get_db_factory, Message, Role


@dataclass
class MessageMetrics:
    message_id: int
    message_index: int
    content: str
    exploration_score: int = 0
    puzzle_score: int = 0
    story_progress: int = 0

    def as_dict(self):
        return {
            "message_id": self.message_id,
            "message_index": self.message_index,
            "exploration_score": self.exploration_score,
            "puzzle_score": self.puzzle_score,
            "story_progress": self.story_progress,
        }


class GameAnalyzer:
    def __init__(self, session: Session, run_name: str = "default"):
        self.session = session
        self.env_messages = []
        self.metrics_timeline = []
        self.run_name = run_name

    def load_messages(self):
        messages = self.session.query(Message).order_by(Message.id).all()
        self.env_messages = [msg for msg in messages if msg.sender == Role.USER]

        for idx, msg in enumerate(self.env_messages):
            self.metrics_timeline.append(
                MessageMetrics(message_id=msg.id, message_index=idx, content=msg.body)
            )

        return self.metrics_timeline

    def analyze_progress(self):
        exploration = 0
        puzzle_score = 0

        for metric in self.metrics_timeline:
            if metric.message_index % 3 == 0:
                exploration += 1

            if metric.message_index % 5 == 0 and metric.message_index > 0:
                puzzle_score += 5

            story_progress = min(100, int(metric.message_index * 1.5))

            metric.exploration_score = exploration
            metric.puzzle_score = puzzle_score
            metric.story_progress = story_progress

        return self.metrics_timeline

    def get_metrics_for_graphing(self):
        # Return data in a format suitable for graphing
        message_indices = [m.message_index for m in self.metrics_timeline]
        exploration_scores = [m.exploration_score for m in self.metrics_timeline]
        puzzle_scores = [m.puzzle_score for m in self.metrics_timeline]
        story_progress = [m.story_progress for m in self.metrics_timeline]

        return {
            "message_indices": message_indices,
            "exploration_scores": exploration_scores,
            "puzzle_scores": puzzle_scores,
            "story_progress": story_progress,
        }

    def create_plot_traces(self):
        if not self.metrics_timeline:
            return {}

        metrics_data = self.get_metrics_for_graphing()
        x = metrics_data["message_indices"]

        return {
            "exploration": {
                "x": x,
                "y": metrics_data["exploration_scores"],
                "name": f"{self.run_name} - Exploration",
            },
            "puzzle": {
                "x": x,
                "y": metrics_data["puzzle_scores"],
                "name": f"{self.run_name} - Puzzles",
            },
            "story": {
                "x": x,
                "y": metrics_data["story_progress"],
                "name": f"{self.run_name} - Story",
            },
        }


class MultiRunAnalyzer:
    def __init__(self):
        self.analyzers = {}

    def add_run(self, db_path: Optional[str]):
        if db_path is None:
            run_name = "default"
        else:
            run_name = db_path.replace(".db", "")
            db_path = f"sqlite:///{db_path}"

        engine = get_db_factory(db_path)()
        with engine as session:
            analyzer = GameAnalyzer(session, run_name)
            analyzer.load_messages()
            analyzer.analyze_progress()
            self.analyzers[run_name] = analyzer

    def create_comparison_plots(self, output_file="game_progress_comparison.html"):
        if not self.analyzers:
            print("No game runs to analyze")
            return

        # Create figures for each metric type
        exploration_fig = go.Figure()
        puzzle_fig = go.Figure()
        story_fig = go.Figure()

        for run_name, analyzer in self.analyzers.items():
            traces = analyzer.create_plot_traces()
            if not traces:
                continue

            # Add traces to individual figures
            exploration_fig.add_trace(
                go.Scatter(
                    x=traces["exploration"]["x"],
                    y=traces["exploration"]["y"],
                    mode="lines+markers",
                    name=traces["exploration"]["name"],
                    marker=dict(size=8),
                )
            )

            puzzle_fig.add_trace(
                go.Scatter(
                    x=traces["puzzle"]["x"],
                    y=traces["puzzle"]["y"],
                    mode="lines+markers",
                    name=traces["puzzle"]["name"],
                    marker=dict(size=8),
                )
            )

            story_fig.add_trace(
                go.Scatter(
                    x=traces["story"]["x"],
                    y=traces["story"]["y"],
                    mode="lines+markers",
                    name=traces["story"]["name"],
                    marker=dict(size=8),
                )
            )

        # Set layouts
        exploration_fig.update_layout(
            title="Exploration Progress",
            xaxis_title="Message Index",
            yaxis_title="Locations Explored",
            template="plotly_white",
        )

        puzzle_fig.update_layout(
            title="Puzzle Solving Progress",
            xaxis_title="Message Index",
            yaxis_title="Puzzle Score",
            template="plotly_white",
        )

        story_fig.update_layout(
            title="Story Progress",
            xaxis_title="Message Index",
            yaxis_title="Story Progress (%)",
            template="plotly_white",
        )

        # Save individual plots
        exploration_fig.write_html("exploration_progress.html")
        puzzle_fig.write_html("puzzle_progress.html")
        story_fig.write_html("story_progress.html")

        # Create combined plot
        fig = make_subplots(
            rows=3,
            cols=1,
            subplot_titles=("Exploration", "Puzzles", "Story Progress"),
            vertical_spacing=0.1,
            shared_xaxes=True,
        )

        # Add traces to combined figure
        for trace in exploration_fig.data:
            fig.add_trace(trace, row=1, col=1)
        for trace in puzzle_fig.data:
            fig.add_trace(trace, row=2, col=1)
        for trace in story_fig.data:
            fig.add_trace(trace, row=3, col=1)

        fig.update_layout(
            height=900,
            width=1000,
            title_text="Game Progress Comparison",
            template="plotly_white",
        )

        fig.write_html(output_file)


async def analyze_game(db_paths=None):
    multi_analyzer = MultiRunAnalyzer()

    if db_paths is None:
        db_paths = [None]

    for db_path in db_paths:
        multi_analyzer.add_run(db_path)

    multi_analyzer.create_comparison_plots()

    if not db_paths:
        return multi_analyzer.analyzers["default"].get_metrics_for_graphing()
    else:
        return {
            run_name: analyzer.get_metrics_for_graphing()
            for run_name, analyzer in multi_analyzer.analyzers.items()
        }
