import asyncio

import numpy as np
from nicegui import ui
from nicegui.events import GenericEventArguments

from modules.chart_utils import (
    _NETWORK_CLICK_JS,
    resolve_node_ref,
    users_from_edge_payload,
)
from modules.session import StepperContext
from modules.timeseries_gui_config import (
    DATASET_OPTIONS,
    METHOD_OPTIONS,
)


class StepperController:
    """Stepper navigation and step-panel sync for the time-analysis UI."""

    def bind(self, ctx: StepperContext) -> None:
        """Attach typed page context and listen for stepper value changes."""
        ctx.apply_to(self)
        self.stepper.on_value_change(self.on_stepper_change)

    def set_step_done(self, step, done: bool) -> None:
        if done:
            step.props("done")
        else:
            step.props(remove="done")
        step.update()

    def schedule_chart_resize(self, chart, delays=(0.05, 0.25)) -> None:
        """Resize after layout settles; skip if the chart was cleared/replaced."""

        def _resize():
            if chart is None or getattr(chart, "is_deleted", False):
                return
            chart.run_chart_method("resize")

        for delay in delays:
            ui.timer(delay, _resize, once=True)

    def refresh_config_summary(self):
        self.config_summary.set_text(
            f"{DATASET_OPTIONS[self.toggle_data.value]} · "
            f"{METHOD_OPTIONS[self.toggle_analysis.value]} · "
            f"step {int(self.step_size.value)}s · "
            f"window {int(self.win_size.value)}"
        )

    def unlock_after_build(self):
        self.set_step_done(self.step_configure, True)
        self.set_step_done(self.step_build, True)
        self.step_build.enable()
        self.step_weights.enable()

    def sync_build_step_ui(self):
        """Restore Build-step labels/buttons from graph session state."""
        self.refresh_config_summary()
        if self.graph.graph is not None:
            self.progress.visible = False
            pending = (
                self.toggle_analysis.value,
                self.toggle_data.value,
                self.step_size.value,
                self.win_size.value,
            )
            if self.graph.current_set == pending:
                self.status_label.set_text("Done. Ready to view results.")
            else:
                self.status_label.set_text(
                    "Graph ready. Build again if you changed settings."
                )
            self.create_button.enable()
            self.next_from_build.enable()
            self.unlock_after_build()
        else:
            self.status_label.set_text("Ready when you are.")
            self.next_from_build.disable()

    def go_to_build(self):
        self.set_step_done(self.step_configure, True)
        self.step_build.enable()
        self.sync_build_step_ui()
        self.stepper.set_value("Build graph")

    def go_to_weights(self):
        self.set_step_done(self.step_build, True)
        self.step_weights.enable()
        self.stepper.set_value("Weight distribution")
        # Defer until the step panel is visible — ECharts needs a real size to draw.
        ui.timer(0.15, self.sync_weights_step_ui, once=True)

    def go_to_explore(self):
        self.set_step_done(self.step_weights, True)
        self.step_explore.enable()
        self.stepper.set_value("Explore network")
        ui.timer(0.15, self.sync_explore_step_ui, once=True)

    def go_to_inspect(self):
        if self.selected_edge["user0"] is None or self.selected_edge["user1"] is None:
            ui.notify("Select a user link first (list or network edge).")
            return
        self.set_step_done(self.step_explore, True)
        self.step_inspect.enable()
        # Show loading immediately so it is visible while the step opens.
        self.edge_title.set_text(
            f"{self.selected_edge['user0']}  ↔  {self.selected_edge['user1']}"
        )
        self.edge_meta.set_text("")
        self.scroll_container.clear()
        self.compare_chart_slot.clear()
        self.compare_chart["chart"] = None
        self.compare_loading_label.set_text("Preparing comparison…")
        self.compare_loading.visible = True
        already_on_compare = self.stepper.value == "Compare users"
        self.stepper.set_value("Compare users")
        # on_stepper_change loads when the step changes; only schedule here
        # if we were already on Compare users (no value-change event).
        if already_on_compare:
            ui.timer(0.15, self.sync_compare_step_ui, once=True)

    def start_over(self):
        self.set_step_done(self.step_configure, False)
        self.set_step_done(self.step_build, False)
        self.set_step_done(self.step_weights, False)
        self.set_step_done(self.step_explore, False)
        self.set_step_done(self.step_inspect, False)
        self.step_build.disable()
        self.step_weights.disable()
        self.step_explore.disable()
        self.step_inspect.disable()
        self.selected_edge["user0"] = None
        self.selected_edge["user1"] = None
        self.selected_edge_label.set_text(
            "Or click a thick line (edge) in the network below."
        )
        self.edge_select.set_options({})
        self.edge_select.set_value(None)
        self.edge_select.disable()
        self.inspect_button.disable()
        if self.graph.graph is not None:
            self.unlock_after_build()
        self.stepper.set_value("Configure")

    def sync_weights_step_ui(self):
        """Rebuild the histogram in-place so it draws after the step becomes visible."""
        self.weight_chart_slot.clear()
        if self.graph.graph is None:
            with self.weight_chart_slot:
                ui.label("Build a graph first to see weight distribution.").classes(
                    "text-body2 text-grey-7"
                )
            return

        wts = self.graph.get_graph_weights()
        if wts is None or len(wts) == 0:
            with self.weight_chart_slot:
                ui.label("No edge weights available for this graph.").classes(
                    "text-body2 text-grey-7"
                )
            return

        hist, edges = np.histogram(np.log1p(wts), bins=50)
        options = {
            "title": {"text": "Log histogram of edge weights", "left": "center"},
            "tooltip": {"trigger": "axis"},
            "grid": {
                "left": "2%",
                "right": "2%",
                "top": 56,
                "bottom": 56,
                "containLabel": True,
            },
            "xAxis": {
                "type": "category",
                "data": [f"{edge:.2f}" for edge in edges[:-1]],
                "name": "log1p(weight)",
                "nameLocation": "middle",
                "nameGap": 28,
                "axisLabel": {"rotate": 45, "interval": 4},
            },
            "yAxis": {"type": "value", "name": "count"},
            "series": [
                {"name": "count", "type": "bar", "data": [int(v) for v in hist]}
            ],
        }
        with self.weight_chart_slot:
            chart = (
                ui.echart(options)
                .classes("w-full")
                .style("display:block; width:100%; min-width:100%; height:360px;")
            )
        # Chart often mounts before the stepper panel has its final width.
        self.schedule_chart_resize(chart)

    def refresh_edge_select_options(self):
        if self.graph.cut_graph is None:
            self.edge_select.set_options({})
            self.edge_select.set_value(None)
            self.edge_select.disable()
            return
        options = {f"{u}\t{v}": f"{u}  ↔  {v}" for u, v in self.graph.cut_graph.edges()}
        self.edge_select.set_options(options)
        self.edge_select.set_value(None)
        self.edge_select.enable()

    def sync_explore_step_ui(self):
        """Rebuild the network chart after the step becomes visible."""
        self.network_chart_slot.clear()
        self.network_chart["chart"] = None
        if self.graph.graph is None:
            with self.network_chart_slot:
                ui.label("Build a graph first to explore the network.").classes(
                    "text-body2 text-grey-7"
                )
            self.edge_select.disable()
            return

        # Ensure cut_graph matches the current slider before listing edges.
        series = self.graph.create_Egraph(self.slider.value)
        self.refresh_edge_select_options()

        with self.network_chart_slot:
            chart = (
                ui.echart({"series": series, "tooltip": {}})
                .classes("w-full")
                .style("display:block; width:100%; min-width:100%; height:420px;")
            )
            chart.on(
                "chart:click",
                self.handle_network_chart_click,
                js_handler=_NETWORK_CLICK_JS,
            )
            self.network_chart["chart"] = chart

        self.schedule_chart_resize(chart)
        self.slider.enable()

    def _resolve_node_ref(self, ref) -> str | None:
        nodes = (
            list(self.graph.cut_graph.nodes())
            if self.graph.cut_graph is not None
            else None
        )
        return resolve_node_ref(ref, nodes)

    def _users_from_edge_payload(self, args) -> tuple[str, str] | None:
        nodes = (
            list(self.graph.cut_graph.nodes())
            if self.graph.cut_graph is not None
            else None
        )
        return users_from_edge_payload(args, nodes)

    def _sync_edge_select_value(self, user0: str, user1: str) -> None:
        options = self.edge_select.options or {}
        key = f"{user0}\t{user1}"
        alt = f"{user1}\t{user0}"
        if key in options:
            self.edge_select.set_value(key)
        elif alt in options:
            self.edge_select.set_value(alt)

    async def select_user_pair(self, user0: str, user1: str, *, advance: bool = False):
        self.selected_edge["user0"] = user0
        self.selected_edge["user1"] = user1
        self.selected_edge_label.set_text(f"Selected: {user0}  ↔  {user1}")
        self._sync_edge_select_value(user0, user1)
        self.inspect_button.enable()
        ui.notify(f"Selected {user0} ↔ {user1}")
        if advance:
            self.go_to_inspect()

    def on_edge_selected_from_list(self, value):
        if not value or "\t" not in str(value):
            return
        user0, user1 = str(value).split("\t", 1)
        # Already selected via graph click — avoid duplicate notify/work.
        if (
            self.selected_edge["user0"] == user0
            and self.selected_edge["user1"] == user1
        ) or (
            self.selected_edge["user0"] == user1
            and self.selected_edge["user1"] == user0
        ):
            self.inspect_button.enable()
            return
        return self.select_user_pair(user0, user1, advance=False)

    def handle_network_chart_click(self, e: GenericEventArguments):
        users = self._users_from_edge_payload(e.args)
        if users is None:
            if isinstance(e.args, dict) and e.args.get("dataType") == "node":
                ui.notify(
                    "Click a connecting line between two users, or use the list above."
                )
            return
        user0, user1 = users
        return self.select_user_pair(user0, user1, advance=False)

    async def sync_compare_step_ui(self):
        user0 = self.selected_edge["user0"]
        user1 = self.selected_edge["user1"]
        if user0 is None or user1 is None:
            self.compare_chart_slot.clear()
            self.compare_chart["chart"] = None
            with self.compare_chart_slot:
                ui.label("Select a user link on Explore network first.").classes(
                    "text-body2 text-grey-7"
                )
            return
        await self.load_edge_inspection(user0, user1)

    async def load_edge_inspection(self, user0, user1):
        load_id = self.compare_load_id["n"] + 1
        self.compare_load_id["n"] = load_id

        self.scroll_container.clear()
        self.compare_chart_slot.clear()
        self.compare_chart["chart"] = None

        self.edge_title.set_text(f"{user0}  ↔  {user1}")
        self.edge_meta.set_text("")
        self.compare_loading_label.set_text("Loading posting activity…")
        self.compare_loading.visible = True
        # Let the browser paint the loader before starting CSV work.
        await asyncio.sleep(0)
        if load_id != self.compare_load_id["n"]:
            return
        try:
            result0 = await self.graph.get_user_tvec(user0)
            result1 = await self.graph.get_user_tvec(user1)
            if load_id != self.compare_load_id["n"]:
                return
            if result0 is None or result1 is None:
                self.edge_meta.set_text("Could not load time series for this edge.")
                with self.compare_chart_slot:
                    ui.label("Could not load activity chart.").classes(
                        "text-body2 text-grey-7"
                    )
                return
            tvec0, num_posts0 = result0
            tvec1, num_posts1 = result1
            self.edge_meta.set_text(
                f"{user0}: {num_posts0} posts · {user1}: {num_posts1} posts"
            )
            self.compare_loading_label.set_text("Rendering activity chart…")
            await asyncio.sleep(0)
            if load_id != self.compare_load_id["n"]:
                return

            options = {
                "title": {
                    "text": f"Activity over time: {user0} vs {user1}",
                    "left": "center",
                    "top": 4,
                    "padding": [0, 0, 10, 0],
                },
                "tooltip": {"trigger": "axis"},
                "legend": {"data": [user0, user1], "top": 36},
                "grid": {
                    "left": "2%",
                    "right": "2%",
                    "top": 72,
                    "bottom": 40,
                    "containLabel": True,
                },
                "xAxis": {
                    "type": "category",
                    "data": list(range(len(tvec0))),
                    "name": "time bin",
                },
                "yAxis": {"type": "value", "name": "posts"},
                "series": [
                    {"name": user0, "type": "line", "data": [float(v) for v in tvec0]},
                    {"name": user1, "type": "line", "data": [float(v) for v in tvec1]},
                ],
            }
            self.compare_chart_slot.clear()
            with self.compare_chart_slot:
                chart = (
                    ui.echart(options)
                    .classes("w-full")
                    .style("display:block; width:100%; min-width:100%; height:360px;")
                )
                self.compare_chart["chart"] = chart
            self.schedule_chart_resize(chart)

            self.compare_loading_label.set_text("Loading interleaved posts…")
            await asyncio.sleep(0)
            if load_id != self.compare_load_id["n"]:
                return
            contents0, time0 = await self.graph.get_user_content(user0)
            contents1, time1 = await self.graph.get_user_content(user1)
            if load_id != self.compare_load_id["n"]:
                return
            user_and_contents = [(user0, c, t) for c, t in zip(contents0, time0)]
            user_and_contents += [(user1, c, t) for c, t in zip(contents1, time1)]
            user_and_contents.sort(key=lambda x: x[2])
            self.scroll_container.clear()
            with self.scroll_container:
                for user, content, time in user_and_contents:
                    ui.chat_message(content, name=user, stamp=time, sent=user == user0)
        finally:
            if load_id == self.compare_load_id["n"]:
                self.compare_loading.visible = False

    def on_stepper_change(self, e):
        if e.value == "Build graph":
            self.sync_build_step_ui()
        elif e.value == "Weight distribution":
            ui.timer(0.15, self.sync_weights_step_ui, once=True)
        elif e.value == "Explore network":
            ui.timer(0.15, self.sync_explore_step_ui, once=True)
        elif e.value == "Compare users":
            ui.timer(0.15, self.sync_compare_step_ui, once=True)

    async def handle_create(self):
        self.create_button.disable()
        self.progress.visible = True
        self.status_label.set_text("Building graph…")
        await self.graph.create_graph(
            self.toggle_analysis.value,
            self.toggle_data.value,
            self.step_size.value,
            self.win_size.value,
        )
        self.progress.visible = False
        self.status_label.set_text("Done. Ready to view results.")

        self.slider.enable()
        self.create_button.enable()
        self.next_from_build.enable()
        self.unlock_after_build()

    async def handle_slider(self, value):
        series = self.graph.create_Egraph(value)
        self.refresh_edge_select_options()
        chart = self.network_chart["chart"]
        if chart is None:
            self.sync_explore_step_ui()
            return
        chart.options["series"] = series
        chart.update()
        chart.run_chart_method("resize")
