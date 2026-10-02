"""Explore network panel sync and edge selection for StepperController."""

from __future__ import annotations

from nicegui import ui
from nicegui.events import GenericEventArguments

from modules.chart_utils import (
    NETWORK_CLICK_JS,
    network_hover_clear_labels_js,
    network_hover_show_labels_js,
    users_from_edge_payload,
)


class StepperExploreMixin:
    """Network chart and user-link selection."""

    def schedule_chart_resize(self, chart, delays=(0.05, 0.25)) -> None:
        """Resize after layout settles; skip if the chart was cleared/replaced."""

        def _resize():
            if chart is None or getattr(chart, "is_deleted", False):
                return
            chart.run_chart_method("resize")

        for delay in delays:
            ui.timer(delay, _resize, once=True)

    def refresh_edge_select_options(self):
        edge_select = self.panels.explore.edge_select
        if self.graph.cut_graph is None:
            edge_select.set_options({})
            edge_select.set_value(None)
            edge_select.disable()
            return
        options = {f"{u}\t{v}": f"{u}  ↔  {v}" for u, v in self.graph.cut_graph.edges()}
        edge_select.set_options(options)
        edge_select.set_value(None)
        edge_select.enable()

    def sync_explore_step_ui(self):
        """Rebuild the network chart after the step becomes visible."""
        explore = self.panels.explore
        explore.network_chart_slot.clear()
        self.network_chart["chart"] = None
        if self.graph.graph is None:
            with explore.network_chart_slot:
                ui.label("Build a graph first to explore the network.").classes(
                    "text-body2 text-grey-7"
                )
            explore.edge_select.disable()
            return

        # Ensure cut_graph matches the current slider before listing edges.
        series = self.graph.create_egraph(explore.slider.value)
        self.refresh_edge_select_options()

        with explore.network_chart_slot:
            chart = (
                ui.echart({"series": series, "tooltip": {"show": False}})
                .classes("w-full")
                .style("display:block; width:100%; min-width:100%; height:420px;")
            )
            chart.on(
                "chart:click",
                self.handle_network_chart_click,
                js_handler=NETWORK_CLICK_JS,
            )
            chart.on(
                "chart:mouseover",
                js_handler=network_hover_show_labels_js(chart.id),
            )
            chart.on(
                "chart:globalout",
                js_handler=network_hover_clear_labels_js(chart.id),
            )
            self.network_chart["chart"] = chart

        self.schedule_chart_resize(chart)
        explore.slider.enable()

    def _cut_graph_nodes(self) -> list | None:
        if self.graph.cut_graph is None:
            return None
        return list(self.graph.cut_graph.nodes())

    def _sync_edge_select_value(self, user0: str, user1: str) -> None:
        edge_select = self.panels.explore.edge_select
        options = edge_select.options or {}
        key = f"{user0}\t{user1}"
        alt = f"{user1}\t{user0}"
        if key in options:
            edge_select.set_value(key)
        elif alt in options:
            edge_select.set_value(alt)

    async def select_user_pair(self, user0: str, user1: str, *, advance: bool = False):
        explore = self.panels.explore
        self.selected_edge["user0"] = user0
        self.selected_edge["user1"] = user1
        self._sync_edge_select_value(user0, user1)
        explore.inspect_button.enable()
        if advance:
            self.go_to_inspect()

    def on_edge_selected_from_list(self, value):
        if not value or "\t" not in str(value):
            return
        user0, user1 = str(value).split("\t", 1)
        # Already selected via graph click — avoid duplicate work.
        if (
            self.selected_edge["user0"] == user0
            and self.selected_edge["user1"] == user1
        ) or (
            self.selected_edge["user0"] == user1
            and self.selected_edge["user1"] == user0
        ):
            self.panels.explore.inspect_button.enable()
            return
        return self.select_user_pair(user0, user1, advance=False)

    def handle_network_chart_click(self, e: GenericEventArguments):
        users = users_from_edge_payload(e.args, self._cut_graph_nodes())
        if users is None:
            if isinstance(e.args, dict) and e.args.get("dataType") == "node":
                ui.notify(
                    "Click a connecting line between two users, or use the list above."
                )
            return
        user0, user1 = users
        return self.select_user_pair(user0, user1, advance=False)

    async def handle_slider(self, value):
        series = self.graph.create_egraph(value)
        self.refresh_edge_select_options()
        chart = self.network_chart["chart"]
        if chart is None:
            self.sync_explore_step_ui()
            return
        chart.options["series"] = series
        chart.update()
        chart.run_chart_method("resize")
