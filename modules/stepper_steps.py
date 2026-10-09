"""NiceGUI stepper step panels for the time-analysis UI."""

from __future__ import annotations

from dataclasses import dataclass
from types import SimpleNamespace
from typing import Any

from nicegui import ui

from modules.chart_utils import EDGE_COLOR_LEGEND
from modules.timeseries_gui_config import (
    DATASET_HELP,
    DATASET_OPTIONS,
    METHOD_HELP,
    METHOD_OPTIONS,
    STEP_BUILD,
    STEP_CONFIGURE,
    STEP_EXPLORE,
    STEP_INSPECT,
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
    intro_label: Any
    config_summary: Any
    progress: Any
    status_label: Any
    create_button: Any
    next_from_build: Any


@dataclass
class ExploreStep:
    step: Any
    slider: Any
    edge_select: Any
    network_chart_slot: Any
    inspect_button: Any


@dataclass
class InspectStep:
    step: Any
    edge_title: Any
    edge_meta: Any
    compare_loading: Any
    compare_loading_label: Any
    scroll_container: Any


@dataclass
class StepperPanels:
    """All step widgets returned by build_stepper_panels()."""

    configure: ConfigureStep
    build: BuildStep
    explore: ExploreStep
    inspect: InspectStep


# Mark: Configure (shared option buttons)
def _build_option_buttons(
    options: dict[int, str],
    help_by_index: dict[int, str],
    toggle: SimpleNamespace,
) -> None:
    """Mutually exclusive option buttons that write the selected index into toggle.value."""
    buttons: dict[int, Any] = {}

    def select(index: int) -> None:
        toggle.value = index
        for i, button in buttons.items():
            if i == index:
                button.props(remove="outline")
                button.props("unelevated color=primary no-caps")
            else:
                button.props(remove="unelevated")
                button.props("outline color=primary no-caps")

    with ui.row().classes("flex-wrap gap-2 q-mt-xs"):
        for idx, label in options.items():
            button = ui.button(
                label,
                on_click=lambda i=idx: select(i),
            ).props(
                "unelevated color=primary no-caps"
                if idx == 0
                else "outline color=primary no-caps"
            )
            with button:
                ui.tooltip(help_by_index[idx])
            buttons[idx] = button


# Mark: Configure
def build_configure_step(stepper_controller: Any) -> ConfigureStep:
    with ui.step(STEP_CONFIGURE, icon="tune") as step_configure:
        ui.label("Choose the dataset and how similarity is measured.").classes(
            "text-body2 text-grey-8 q-mb-sm"
        )
        with ui.card().classes("w-full"):
            toggle_data = SimpleNamespace(value=0)
            toggle_analysis = SimpleNamespace(value=0)

            with ui.card_section():
                ui.label("Dataset").classes("text-subtitle2")
                _build_option_buttons(DATASET_OPTIONS, DATASET_HELP, toggle_data)

            with ui.card_section():
                ui.label("Analysis method").classes("text-subtitle2")
                _build_option_buttons(METHOD_OPTIONS, METHOD_HELP, toggle_analysis)

            with ui.card_section():
                ui.label("Set the analysis window").classes("text-subtitle2")
                with ui.row().classes("items-center gap-4 flex-wrap"):
                    step_size = ui.number(
                        label="Time step (seconds)",
                        value=300,
                        precision=0,
                        step=1,
                        min=1,
                        max=1440,
                    ).classes("w-40")
                    with step_size:
                        ui.tooltip(
                            "How far each window moves forward (in seconds). "
                            "Smaller = finer, slower."
                        )
                    win_size = ui.number(
                        label="Window width (× time step)",
                        value=2,
                        precision=0,
                        step=1,
                        min=1,
                        max=1440,
                    ).classes("w-40")
                    with win_size:
                        ui.tooltip(
                            "How many time steps wide each window is. "
                            "Width 2 with a 300s time step → 600s windows."
                        )
                timing_hint = ui.label("").classes("text-body2 text-grey-8 mt-4")

                def _refresh_timing_hint(_=None) -> None:
                    t_step = max(1, int(step_size.value or 1))
                    width = max(1, int(win_size.value or 1))
                    duration = t_step * width
                    overlap = duration - t_step
                    timing_hint.set_text(
                        f"Each window is {duration}s wide. "
                        f"Windows advance by {t_step}s "
                        f"(overlap {overlap}s)."
                    )

                step_size.on_value_change(_refresh_timing_hint)
                win_size.on_value_change(_refresh_timing_hint)
                _refresh_timing_hint()
        with ui.stepper_navigation().classes("w-full justify-end"):
            next_configure = ui.button(
                f"Next: {STEP_BUILD}", on_click=stepper_controller.go_to_build
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


# Mark: Build graph
def build_build_step(stepper: Any, stepper_controller: Any, graph: Any) -> BuildStep:
    with ui.step(STEP_BUILD, icon="hub") as step_build:
        with ui.column().classes("w-full items-center gap-2"):
            intro_label = ui.label(
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
                    "Run the selected analysis. Large datasets can take a while."
                )
        ui.timer(
            0.1,
            callback=lambda: progress.set_value(graph.managed_progress_value.value),
        )
        with ui.stepper_navigation().classes("w-full justify-between"):
            ui.button("Back", on_click=stepper.previous).props("flat")
            next_from_build = ui.button(
                f"Next: {STEP_EXPLORE}",
                on_click=stepper_controller.go_to_explore,
            ).props("unelevated")
            with next_from_build:
                ui.tooltip("Open the network graph and choose a user link to compare.")
            next_from_build.disable()

    return BuildStep(
        step=step_build,
        intro_label=intro_label,
        config_summary=config_summary,
        progress=progress,
        status_label=status_label,
        create_button=create_button,
        next_from_build=next_from_build,
    )


# Mark: Explore network
def build_explore_step(stepper: Any, stepper_controller: Any) -> ExploreStep:
    with ui.step(STEP_EXPLORE, icon="account_tree") as step_explore:
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
                    label="Click here to select a connection",
                    with_input=True,
                ).classes("w-full")
                with edge_select:
                    ui.tooltip(
                        f"Pick two linked users from the list. This is the most reliable way to open {STEP_INSPECT}."
                    )
                edge_select.disable()
                edge_select.on_value_change(
                    lambda e: stepper_controller.on_edge_selected_from_list(e.value)
                )
                ui.label(
                    "Or click a thick line between two users in the network below."
                ).classes("text-caption text-grey-7 q-mt-sm")
                with ui.row().classes("items-center gap-4 q-mt-xs q-mb-sm flex-wrap"):
                    for color, label in EDGE_COLOR_LEGEND:
                        with ui.row().classes("items-center gap-1"):
                            ui.element("div").style(
                                f"width:18px;height:4px;border-radius:2px;"
                                f"background:{color};"
                            )
                            ui.label(label).classes("text-caption text-grey-7")
                network_chart_slot = ui.element("div").classes("w-full")
        with ui.stepper_navigation().classes("w-full justify-between"):
            ui.button("Back", on_click=stepper.previous).props("flat")
            inspect_button = ui.button(
                "Compare these users",
                on_click=stepper_controller.go_to_inspect,
            ).props("unelevated")
            with inspect_button:
                ui.tooltip("Open an interleaved post timeline for the selected pair.")
            inspect_button.disable()

    return ExploreStep(
        step=step_explore,
        slider=slider,
        edge_select=edge_select,
        network_chart_slot=network_chart_slot,
        inspect_button=inspect_button,
    )


# Mark: Compare users
def build_inspect_step(stepper: Any, stepper_controller: Any) -> InspectStep:
    with ui.step(STEP_INSPECT, icon="compare_arrows") as step_inspect:
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

            with ui.card_section().classes("w-full q-pt-none"):
                scroll_container = ui.scroll_area().classes("w-full h-80")

        with ui.stepper_navigation().classes("w-full justify-between"):
            ui.button("Back", on_click=stepper.previous).props("flat")
            ui.button(
                "Start over",
                on_click=stepper_controller.start_over,
            ).props("flat").tooltip(
                f"Return to {STEP_CONFIGURE}. A completed build stays available in this session."
            )

    return InspectStep(
        step=step_inspect,
        edge_title=edge_title,
        edge_meta=edge_meta,
        compare_loading=compare_loading,
        compare_loading_label=compare_loading_label,
        scroll_container=scroll_container,
    )


# Mark: All steps (orchestrator)
def build_stepper_panels(
    stepper: Any, stepper_controller: Any, graph: Any
) -> StepperPanels:
    """Build every ui.step panel (not the stepper shell). Call inside ui.stepper()."""
    return StepperPanels(
        configure=build_configure_step(stepper_controller),
        build=build_build_step(stepper, stepper_controller, graph),
        explore=build_explore_step(stepper, stepper_controller),
        inspect=build_inspect_step(stepper, stepper_controller),
    )
