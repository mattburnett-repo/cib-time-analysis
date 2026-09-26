from nicegui import app, ui

from modules.my_graph import MyGraph
from modules.session import make_stepper_context
from modules.stepper import StepperController
from modules.stepper_steps import build_stepper_panels
from modules.timeseries_gui_config import APP_TITLE, TOOLTIP_CSS

# Cursor/IDE Simple Browser probes Chrome DevTools Protocol on the app port;
# NiceGUI is not a CDP endpoint, so unanswered /json/version requests spam 404s.
# This workaround eliminates unnecessary "http://localhost:8080/json/version not found" errors in the console output.


# FIXME: we might not need this once we move the code over to CIBMT
@app.get("/json/version")
def _chrome_devtools_probe():
    return {"Browser": "NiceGUI", "Protocol-Version": "0.0"}


# FIXME: we might not need this once we move the code over to CIBMT
def _print_welcome() -> None:
    # NiceGUI's built-in welcome always says "NiceGUI"; replace it with APP_TITLE.
    urls = list(app.urls)
    if len(urls) >= 2:
        urls[-1] = "and " + urls[-1]
    print(f"{APP_TITLE} ready to go on {', '.join(urls)}", flush=True)


@ui.page("/")
def main_page():
    graph = MyGraph()
    selected_edge = {"user0": None, "user1": None}
    network_chart = {"chart": None}
    compare_chart = {"chart": None}
    compare_load_id = {"n": 0}
    stepper_controller = StepperController()

    ui.colors(primary="#1f4e79")
    ui.add_css(TOOLTIP_CSS)
    with ui.column().classes("w-full max-w-5xl mx-auto q-pa-md gap-2"):
        ui.label(APP_TITLE).classes("text-h4 text-weight-bold")
        ui.label(
            "Build a user network from posting times, then inspect linked accounts."
        ).classes("text-subtitle1 text-grey-8")

        # Step panels are created here (see modules/stepper_steps.py).
        with ui.stepper().props("animated").classes("w-full") as stepper:
            panels = build_stepper_panels(stepper, stepper_controller, graph)

        # Future steps stay disabled until prior steps succeed.
        panels.build.step.disable()
        panels.weights.step.disable()
        panels.explore.step.disable()
        panels.inspect.step.disable()

    # Page builds the UI first, then hands the controller session state + widgets
    # so clicks and step changes update the right controls and data.
    stepper_controller.bind(
        make_stepper_context(
            graph=graph,
            selected_edge=selected_edge,
            network_chart=network_chart,
            compare_chart=compare_chart,
            compare_load_id=compare_load_id,
            stepper=stepper,
            panels=panels,
        )
    )


if __name__ in {"__main__", "__mp_main__"}:
    app.on_startup(_print_welcome)
    ui.run(title=APP_TITLE, show_welcome_message=False)
