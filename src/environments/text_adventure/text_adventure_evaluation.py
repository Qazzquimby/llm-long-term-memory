from dataclasses import dataclass
from dataclasses import dataclass
from typing import List, Optional

import numpy as np
from sqlalchemy.orm import Session
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from src.db import get_db_factory, Message, Role


@dataclass
class Metric:
    name: str
    display_name: str
    value: int = 0


@dataclass
class MessageMetrics:
    message_id: int
    message_index: int
    content: str
    metrics: List[Metric] = None

    def __post_init__(self):
        if self.metrics is None:
            self.metrics = [
                Metric(name="new_lines", display_name="New Response Lines"),
                Metric(name="score", display_name="Score"),
            ]

    def as_dict(self):
        result = {
            "message_id": self.message_id,
            "message_index": self.message_index,
        }
        for metric in self.metrics:
            result[metric.name] = metric.value
        return result

    def get_metric(self, name):
        for metric in self.metrics:
            if metric.name == name:
                return metric
        return None


class GameAnalyzer:
    def __init__(self, session: Session, run_name: str = "default"):
        self.session = session
        self.env_messages = []
        self.metrics_timeline: List[MessageMetrics] = []
        self.run_name = run_name

    def load_messages(self):
        messages = self.session.query(Message).order_by(Message.id).all()
        self.env_messages = [msg for msg in messages if msg.sender == Role.USER]

        # todo this should be overengineering. Probably remove
        # find last index of system prompt to guard against multiple runs in the same session
        system_prompt = self.env_messages[0].body
        system_prompt_indices = [
            i for i, msg in enumerate(self.env_messages) if msg.body == system_prompt
        ] + [len(self.env_messages) - 1]
        run_lengths = [
            system_prompt_indices[i + 1] - system_prompt_indices[i]
            for i in range(len(system_prompt_indices))
        ]
        longest_run_start_index = system_prompt_indices[np.argmax(run_lengths)]
        longest_run_end_index = system_prompt_indices[np.argmax(run_lengths) + 1]

        self.env_messages = self.env_messages[
            longest_run_start_index:longest_run_end_index
        ]

        for idx, msg in enumerate(self.env_messages):
            self.metrics_timeline.append(
                MessageMetrics(message_id=msg.id, message_index=idx, content=msg.body)
            )

        return self.metrics_timeline

    def analyze_progress(self):
        num_new_lines = 0
        score = 0

        previous_messages = []
        previous_lines = set()
        for state_metrics in self.metrics_timeline:
            lines = [line.strip() for line in state_metrics.content.split("\n")]
            new_lines = [line for line in lines if line not in previous_lines]
            num_new_lines += len(new_lines)

            if "score has just gone up" in state_metrics.content:
                score += 1

            state_metrics.get_metric("new_lines").value = num_new_lines
            state_metrics.get_metric("score").value = score

            previous_messages.append(state_metrics.content)
            previous_lines.update(lines)

        return self.metrics_timeline

    def get_metrics_for_graphing(self):
        # Return data in a format suitable for graphing
        message_indices = [m.message_index for m in self.metrics_timeline]
        result = {"message_indices": message_indices}

        # Get all metric names from the first message metrics object
        if self.metrics_timeline:
            for metric in self.metrics_timeline[0].metrics:
                result[metric.name] = [
                    m.get_metric(metric.name).value for m in self.metrics_timeline
                ]

        return result

    def create_plot_traces(self):
        if not self.metrics_timeline:
            return {}

        metrics_data = self.get_metrics_for_graphing()
        x = metrics_data["message_indices"]

        traces = {}

        # Create a trace for each metric
        if self.metrics_timeline:
            for metric in self.metrics_timeline[0].metrics:
                traces[metric.name] = {
                    "x": x,
                    "y": metrics_data[metric.name],
                    "name": f"{self.run_name} - {metric.display_name}",
                }

        return traces


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

        # Get metric names from the first analyzer
        metric_names = []
        if self.analyzers:
            first_analyzer = next(iter(self.analyzers.values()))
            if first_analyzer.metrics_timeline:
                metric_names = [
                    metric.name for metric in first_analyzer.metrics_timeline[0].metrics
                ]

        # Create a figure for each metric type
        metric_figures = {name: go.Figure() for name in metric_names}

        for run_name, analyzer in self.analyzers.items():
            traces = analyzer.create_plot_traces()
            if not traces:
                continue

            # Add traces to individual figures
            for metric_name, trace_data in traces.items():
                if metric_name in metric_figures:
                    metric_figures[metric_name].add_trace(
                        go.Scatter(
                            x=trace_data["x"],
                            y=trace_data["y"],
                            mode="lines+markers",
                            name=trace_data["name"],
                            marker=dict(size=8),
                        )
                    )

        # Set layouts and save individual plots
        for metric_name, fig in metric_figures.items():
            # Get display information from the first analyzer's metrics
            display_name = self._get_metric_display_name(metric_name)

            fig.update_layout(
                title=f"{display_name} Progress",
                xaxis_title="Message Index",
                yaxis_title=display_name,
                template="plotly_white",
            )

            # Save individual plot
            fig.write_html(f"{metric_name}_progress.html")

        # Create combined plot
        subplot_titles = [
            self._get_metric_display_name(name) for name in metric_figures.keys()
        ]

        fig = make_subplots(
            rows=len(metric_figures),
            cols=1,
            subplot_titles=subplot_titles,
            vertical_spacing=0.1,
            shared_xaxes=True,
        )

        # Add traces to combined figure
        for i, (metric_name, metric_fig) in enumerate(metric_figures.items(), 1):
            for trace in metric_fig.data:
                fig.add_trace(trace, row=i, col=1)

        fig.update_layout(
            height=900,
            width=1000,
            title_text="Game Progress Comparison",
            template="plotly_white",
        )

        fig.write_html(output_file)

    def _get_metric_display_name(self, metric_name):
        """Get the display name for a metric from any analyzer that has it defined"""
        for analyzer in self.analyzers.values():
            if analyzer.metrics_timeline and analyzer.metrics_timeline[0].metrics:
                for metric in analyzer.metrics_timeline[0].metrics:
                    if metric.name == metric_name:
                        return metric.display_name
        return metric_name.replace("_", " ").title()


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
