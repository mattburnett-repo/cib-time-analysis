from nicegui import app, ui

from modules.my_graph import MyGraph
from modules.session import StepperContext
from modules.stepper import StepperController
from modules.stepper_steps import build_stepper_panels


# Cursor/IDE Simple Browser probes Chrome DevTools Protocol on the app port;
# NiceGUI is not a CDP endpoint, so unanswered /json/version requests spam 404s.
# This workaround eliminates unnecessary "http://localhost:8080/json/version not found" errors in the console output.
@app.get("/json/version")
def _chrome_devtools_probe():
    return {"Browser": "NiceGUI", "Protocol-Version": "0.0"}


@ui.page("/")
def main_page():
    graph = MyGraph()
    selected_edge = {"user0": None, "user1": None}
    network_chart = {"chart": None}
    compare_chart = {"chart": None}
    compare_load_id = {"n": 0}
    stepper_controller = StepperController()

    ui.colors(primary="#1f4e79")
    ui.add_css("""
        .q-tooltip {
            font-size: 1rem !important;
            line-height: 1.45 !important;
            max-width: 28rem;
            padding: 0.55rem 0.8rem !important;
        }
        """)
    with ui.column().classes("w-full max-w-5xl mx-auto q-pa-md gap-2"):
        ui.label("CIB Time Analysis").classes("text-h4 text-weight-bold")
        ui.label(
            "Build a user network from posting times, then inspect linked accounts."
        ).classes("text-subtitle1 text-grey-8")

        # Step panels are created here (see modules/stepper_steps.py).
        with ui.stepper().props("animated header-nav").classes("w-full") as stepper:
            panels = build_stepper_panels(stepper, stepper_controller, graph)

        # Future steps stay disabled until prior steps succeed; header-nav then allows return.
        panels.build.step.disable()
        panels.weights.step.disable()
        panels.explore.step.disable()
        panels.inspect.step.disable()

    # Hand off typed page context after the UI exists.
    # Buttons already call stepper_controller methods; bind() applies StepperContext
    # (MyGraph, selection/chart dicts, step widgets, form controls) and registers
    # on_stepper_change so tab/header navigation can resync each step's panel.

    # In short: the page builds the screen first, then hands the controller everything
    # it needs so clicks and step changes can update the right widgets and data.
    stepper_controller.bind(
        StepperContext(
            graph=graph,
            selected_edge=selected_edge,
            network_chart=network_chart,
            compare_chart=compare_chart,
            compare_load_id=compare_load_id,
            stepper=stepper,
            step_configure=panels.configure.step,
            step_build=panels.build.step,
            step_weights=panels.weights.step,
            step_explore=panels.explore.step,
            step_inspect=panels.inspect.step,
            toggle_data=panels.configure.toggle_data,
            toggle_analysis=panels.configure.toggle_analysis,
            step_size=panels.configure.step_size,
            win_size=panels.configure.win_size,
            config_summary=panels.build.config_summary,
            progress=panels.build.progress,
            status_label=panels.build.status_label,
            create_button=panels.build.create_button,
            next_from_build=panels.build.next_from_build,
            weight_chart_slot=panels.weights.weight_chart_slot,
            slider=panels.explore.slider,
            edge_select=panels.explore.edge_select,
            selected_edge_label=panels.explore.selected_edge_label,
            network_chart_slot=panels.explore.network_chart_slot,
            inspect_button=panels.explore.inspect_button,
            edge_title=panels.inspect.edge_title,
            edge_meta=panels.inspect.edge_meta,
            compare_loading=panels.inspect.compare_loading,
            compare_loading_label=panels.inspect.compare_loading_label,
            compare_chart_slot=panels.inspect.compare_chart_slot,
            scroll_container=panels.inspect.scroll_container,
        )
    )


if __name__ in {"__main__", "__mp_main__"}:
    ui.run()
