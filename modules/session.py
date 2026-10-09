"""Typed context passed from the NiceGUI page into StepperController.bind()."""

from __future__ import annotations

from dataclasses import dataclass, fields
from typing import Any

from modules.my_graph import MyGraph


@dataclass
class StepperContext:
    """Page session state plus step panels the stepper controller mutates."""

    graph: MyGraph
    selected_edge: dict[str, str | None]
    network_chart: dict[str, Any]
    compare_load_id: dict[str, int]
    stepper: Any
    panels: Any  # StepperPanels — kept Any to avoid a session↔UI import cycle

    def apply_to(self, target: Any) -> None:
        """Copy every field onto target as attributes (used by StepperController.bind)."""
        for field in fields(self):
            setattr(target, field.name, getattr(self, field.name))


def make_stepper_context(
    *,
    graph: MyGraph,
    selected_edge: dict[str, str | None],
    network_chart: dict[str, Any],
    compare_load_id: dict[str, int],
    stepper: Any,
    panels: Any,
) -> StepperContext:
    """Build the typed payload that StepperController.bind() consumes.

    Keeps session state and StepperPanels together next to StepperContext so the
    page entrypoint stays thin and the controller reads widgets via panels.*.
    """
    return StepperContext(
        graph=graph,
        selected_edge=selected_edge,
        network_chart=network_chart,
        compare_load_id=compare_load_id,
        stepper=stepper,
        panels=panels,
    )
