"""NiceGUI stepper step panels for the time-analysis UI."""

from __future__ import annotations

from dataclasses import dataclass
from types import SimpleNamespace
from typing import Any

from nicegui import ui

from modules.timeseries_gui_config import (
    DATASET_HELP,
    DATASET_OPTIONS,
    METHOD_HELP,
    METHOD_OPTIONS,
)


@dataclass
class ConfigureStep:
    step: Any
    toggle_data: Any
    toggle_analysis: Any
    step_size: Any
    win_size: Any


@dataclass
class BuildStep:
    step: Any
    config_summary: Any
    progress: Any
    status_label: Any
    create_button: Any
    next_from_build: Any


@dataclass
class WeightsStep:
    step: Any
    weight_chart_slot: Any


@dataclass
class ExploreStep:
    step: Any
    slider: Any
    edge_select: Any
    selected_edge_label: Any
    network_chart_slot: Any
    inspect_button: Any


@dataclass
class InspectStep:
    step: Any
    edge_title: Any
    edge_meta: Any
    compare_loading: Any
    compare_loading_label: Any
    compare_chart_slot: Any
    scroll_container: Any


@dataclass
class StepperPanels:
    """All step widgets returned by build_stepper_panels()."""

    configure: ConfigureStep
    build: BuildStep
    weights: WeightsStep
    explore: ExploreStep
    inspect: InspectStep


def build_configure_step(stepper_controller: Any) -> ConfigureStep:
    with ui.step("Configure", icon="tune") as step_configure:
        ui.label("Choose the dataset and how similarity is measured.").classes(
            "text-body2 text-grey-8 q-mb-sm"
        )
        with ui.card().classes("w-full"):
            toggle_data = SimpleNamespace(value=0)
            toggle_analysis = SimpleNamespace(value=0)

            with ui.card_section():
                with ui.row().classes("items-center gap-2"):
                    ui.label("Dataset").classes("text-subtitle2")
                    with ui.icon("info", size="xs").classes("text-grey-6 cursor-help"):
                        ui.tooltip(
                            "Hover a dataset button for what it contains and relative size."
                        )
                dataset_buttons = {}

                def select_dataset(index: int) -> None:
                    toggle_data.value = index
                    for i, button in dataset_buttons.items():
                        if i == index:
                            button.props(remove="outline")
                            button.props("unelevated color=primary no-caps")
                        else:
                            button.props(remove="unelevated")
                            button.props("outline color=primary no-caps")

                with ui.row().classes("flex-wrap gap-2 q-mt-xs"):
                    for idx, label in DATASET_OPTIONS.items():
                        button = ui.button(
                            label,
                            on_click=lambda i=idx: select_dataset(i),
                        ).props(
                            "unelevated color=primary no-caps"
                            if idx == 0
                            else "outline color=primary no-caps"
                        )
                        with button:
                            ui.tooltip(DATASET_HELP[idx])
                        dataset_buttons[idx] = button

            with ui.card_section():
                with ui.row().classes("items-center gap-2"):
                    ui.label("Analysis method").classes("text-subtitle2")
                    with ui.icon("info", size="xs").classes("text-grey-6 cursor-help"):
                        ui.tooltip(
                            "Hover a method button for a short explanation of how it scores user links."
                        )
                method_buttons = {}

                def select_method(index: int) -> None:
                    toggle_analysis.value = index
                    for i, button in method_buttons.items():
                        if i == index:
                            button.props(remove="outline")
                            button.props("unelevated color=primary no-caps")
                        else:
                            button.props(remove="unelevated")
                            button.props("outline color=primary no-caps")

                with ui.row().classes("flex-wrap gap-2 q-mt-xs"):
                    for idx, label in METHOD_OPTIONS.items():
                        button = ui.button(
                            label,
                            on_click=lambda i=idx: select_method(i),
                        ).props(
                            "unelevated color=primary no-caps"
                            if idx == 0
                            else "outline color=primary no-caps"
                        )
                        with button:
                            ui.tooltip(METHOD_HELP[idx])
                        method_buttons[idx] = button

            with ui.card_section():
                ui.label("Timing parameters").classes("text-subtitle2")
                with ui.row().classes("items-center gap-4 flex-wrap"):
                    step_size = ui.number(
                        label="Step size (seconds)",
                        value=300,
                        precision=0,
                        step=1,
                        min=1,
                        max=1440,
                    ).classes("w-40")
                    with step_size:
                        ui.tooltip(
                            "Time resolution for binning posts. Larger steps build faster and are coarser."
                        )
                    win_size = ui.number(
                        label="Window size (steps)",
                        value=2,
                        precision=0,
                        step=1,
                        min=1,
                        max=1440,
                    ).classes("w-40")
                    with win_size:
                        ui.tooltip(
                            "How many steps wide each comparison window is. "
                            "Window duration ≈ step size × window size."
                        )
        with ui.stepper_navigation().classes("w-full justify-end"):
            next_configure = ui.button(
                "Next: Build graph", on_click=stepper_controller.go_to_build
            ).props("unelevated")
            with next_configure:
                ui.tooltip("Continue to build the user network with these settings.")

    return ConfigureStep(
        step=step_configure,
        toggle_data=toggle_data,
        toggle_analysis=toggle_analysis,
        step_size=step_size,
        win_size=win_size,
    )


def build_build_step(stepper: Any, stepper_controller: Any, graph: Any) -> BuildStep:
    with ui.step("Build graph", icon="hub") as step_build:
        with ui.column().classes("w-full items-center gap-2"):
            ui.label(
                "Run the analysis. This can take a while on larger datasets."
            ).classes("text-body2 text-grey-8 text-center")
            config_summary = ui.label("").classes("text-body2 text-center")
            progress = (
                ui.linear_progress(value=0)
                .props("instant-feedback")
                .classes("w-full max-w-md")
            )
            progress.visible = False
            status_label = ui.label("Ready when you are.").classes(
                "text-caption text-grey-7"
            )
            create_button = ui.button(
                "Build Graph", on_click=stepper_controller.handle_create
            ).props("unelevated color=primary")
            with create_button:
                ui.tooltip(
                    "Run the selected analysis. Large datasets can take a while; "
                    "identical settings are cached for this session."
                )
        ui.timer(
            0.1,
            callback=lambda: progress.set_value(graph.managed_progress_value.value),
        )
        with ui.stepper_navigation().classes("w-full justify-between"):
            ui.button("Back", on_click=stepper.previous).props("flat")
            next_from_build = ui.button(
                "Next: Weight distribution",
                on_click=stepper_controller.go_to_weights,
            ).props("unelevated")
            with next_from_build:
                ui.tooltip(
                    "View how strongly users are linked before browsing the network."
                )
            next_from_build.disable()

    return BuildStep(
        step=step_build,
        config_summary=config_summary,
        progress=progress,
        status_label=status_label,
        create_button=create_button,
        next_from_build=next_from_build,
    )


def build_weights_step(stepper: Any, stepper_controller: Any) -> WeightsStep:
    with ui.step("Weight distribution", icon="bar_chart") as step_weights:
        ui.label(
            "Review how edge weights are distributed before browsing the network."
        ).classes("text-body2 text-grey-8 q-mb-sm")
        with ui.card().classes("w-full"):
            with ui.card_section().classes("w-full"):
                weight_chart_slot = ui.element("div").classes("w-full")
        with ui.stepper_navigation().classes("w-full justify-between"):
            ui.button("Back", on_click=stepper.previous).props("flat")
            ui.button(
                "Next: Explore network",
                on_click=stepper_controller.go_to_explore,
            ).props("unelevated").tooltip(
                "Open the network graph and choose a user link to compare."
            )

    return WeightsStep(step=step_weights, weight_chart_slot=weight_chart_slot)


def build_explore_step(stepper: Any, stepper_controller: Any) -> ExploreStep:
    with ui.step("Explore network", icon="account_tree") as step_explore:
        ui.label(
            "Pick a link between two users. Next you will compare their "
            "posting timelines and read their posts together."
        ).classes("text-body2 text-grey-8 q-mb-sm")
        with ui.card().classes("w-full"):
            with ui.card_section().classes("w-full"):
                with ui.row().classes("items-center gap-2"):
                    ui.label("Top edges to show").classes("text-subtitle2")
                    with ui.icon("info", size="xs").classes("text-grey-6 cursor-help"):
                        ui.tooltip(
                            "Only the strongest N links are drawn. Raise this to see more of the network."
                        )
                slider = (
                    ui.slider(min=10, max=100, value=10)
                    .classes("w-full")
                    .on(
                        "update:model-value",
                        lambda e: stepper_controller.handle_slider(e.args),
                        throttle=1.0,
                        leading_events=False,
                    )
                )
                with slider:
                    ui.tooltip(
                        "Drag to change how many top-weighted edges appear in the graph."
                    )
                slider.disable()
                slider_value_label = ui.label("10 edges").classes(
                    "text-caption text-grey-7 text-center w-full"
                )
                slider.on_value_change(
                    lambda e: slider_value_label.set_text(f"{int(e.value)} edges")
                )
            with ui.card_section().classes("w-full"):
                ui.label("Choose a user link").classes("text-subtitle2")
                edge_select = ui.select(
                    options={},
                    label="Select a connection",
                    with_input=True,
                ).classes("w-full")
                with edge_select:
                    ui.tooltip(
                        "Pick two linked users from the list. This is the most reliable way to open Compare users."
                    )
                edge_select.disable()
                edge_select.on_value_change(
                    lambda e: stepper_controller.on_edge_selected_from_list(e.value)
                )
                selected_edge_label = ui.label(
                    "Or click a thick line between two users in the network below."
                ).classes("text-caption text-grey-7 q-mt-sm")
                network_chart_slot = ui.element("div").classes("w-full")
        with ui.stepper_navigation().classes("w-full justify-between"):
            ui.button("Back", on_click=stepper.previous).props("flat")
            inspect_button = ui.button(
                "Compare these users",
                on_click=stepper_controller.go_to_inspect,
            ).props("unelevated")
            with inspect_button:
                ui.tooltip(
                    "Open posting-activity charts and an interleaved post timeline for the selected pair."
                )
            inspect_button.disable()

    return ExploreStep(
        step=step_explore,
        slider=slider,
        edge_select=edge_select,
        selected_edge_label=selected_edge_label,
        network_chart_slot=network_chart_slot,
        inspect_button=inspect_button,
    )


def build_inspect_step(stepper: Any, stepper_controller: Any) -> InspectStep:
    with ui.step("Compare users", icon="compare_arrows") as step_inspect:
        ui.label(
            "Side-by-side posting activity and an interleaved timeline of posts "
            "for the two users you selected."
        ).classes("text-body2 text-grey-8 q-mb-sm")
        with ui.card().classes("w-full"):
            with ui.card_section().classes("w-full"):
                edge_title = ui.label("No edge selected yet.").classes(
                    "text-subtitle1 text-weight-medium"
                )
                edge_meta = ui.label("").classes("text-caption text-grey-7")
                with ui.row().classes(
                    "w-full items-center justify-center gap-3 q-mt-md"
                ) as compare_loading:
                    ui.spinner(size="lg")
                    compare_loading_label = ui.label("Loading comparison…").classes(
                        "text-body2 text-grey-8"
                    )
                compare_loading.visible = False
            with ui.card_section().classes("w-full"):
                compare_chart_slot = ui.element("div").classes("w-full")
            with ui.card_section().classes("w-full"):
                ui.label("Interleaved posts").classes("text-subtitle2")
                scroll_container = ui.scroll_area().classes("w-full h-80")
        with ui.stepper_navigation().classes("w-full justify-between"):
            ui.button("Back", on_click=stepper.previous).props("flat")
            ui.button(
                "Start over",
                on_click=stepper_controller.start_over,
            ).props("flat").tooltip(
                "Return to Configure. A completed build stays available in this session."
            )

    return InspectStep(
        step=step_inspect,
        edge_title=edge_title,
        edge_meta=edge_meta,
        compare_loading=compare_loading,
        compare_loading_label=compare_loading_label,
        compare_chart_slot=compare_chart_slot,
        scroll_container=scroll_container,
    )


def build_stepper_panels(
    stepper: Any, stepper_controller: Any, graph: Any
) -> StepperPanels:
    """Build every ui.step panel (not the stepper shell). Call inside ui.stepper()."""
    return StepperPanels(
        configure=build_configure_step(stepper_controller),
        build=build_build_step(stepper, stepper_controller, graph),
        weights=build_weights_step(stepper, stepper_controller),
        explore=build_explore_step(stepper, stepper_controller),
        inspect=build_inspect_step(stepper, stepper_controller),
    )
