"""Typed context passed from the NiceGUI page into StepperController.bind()."""

from __future__ import annotations

from dataclasses import dataclass, fields
from typing import Any

from modules.my_graph import MyGraph


@dataclass
class StepperContext:
    """Page session state plus widget refs the stepper controller mutates."""

    # Session / analysis state
    graph: MyGraph
    selected_edge: dict[str, str | None]
    network_chart: dict[str, Any]
    compare_chart: dict[str, Any]
    compare_load_id: dict[str, int]

    # Stepper shell
    stepper: Any
    step_configure: Any
    step_build: Any
    step_weights: Any
    step_explore: Any
    step_inspect: Any

    # Configure / build controls
    toggle_data: Any
    toggle_analysis: Any
    step_size: Any
    win_size: Any
    config_summary: Any
    progress: Any
    status_label: Any
    create_button: Any
    next_from_build: Any

    # Explore / compare panels
    weight_chart_slot: Any
    slider: Any
    edge_select: Any
    selected_edge_label: Any
    network_chart_slot: Any
    inspect_button: Any
    edge_title: Any
    edge_meta: Any
    compare_loading: Any
    compare_loading_label: Any
    compare_chart_slot: Any
    scroll_container: Any

    def apply_to(self, target: Any) -> None:
        """Copy every field onto target as attributes (used by StepperController.bind)."""
        for field in fields(self):
            setattr(target, field.name, getattr(self, field.name))
