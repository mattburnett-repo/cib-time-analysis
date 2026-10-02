"""Compare-users panel loading for StepperController."""

from __future__ import annotations

import asyncio

from nicegui import ui

from modules.timeseries_gui_config import STEP_EXPLORE


class StepperCompareMixin:
    """Activity charts and interleaved post timeline for a selected edge."""

    async def sync_compare_step_ui(self):
        user0 = self.selected_edge["user0"]
        user1 = self.selected_edge["user1"]
        if user0 is None or user1 is None:
            slot = self.panels.inspect.compare_chart_slot
            slot.clear()
            self.compare_chart["chart"] = None
            with slot:
                ui.label(f"Select a user link on {STEP_EXPLORE} first.").classes(
                    "text-body2 text-grey-7"
                )
            return
        await self.load_edge_inspection(user0, user1)

    async def load_edge_inspection(self, user0, user1):
        inspect = self.panels.inspect
        load_id = self.compare_load_id["n"] + 1
        self.compare_load_id["n"] = load_id

        inspect.scroll_container.clear()
        inspect.compare_chart_slot.clear()
        self.compare_chart["chart"] = None

        inspect.edge_title.set_text(f"{user0}  ↔  {user1}")
        inspect.edge_meta.set_text("")
        inspect.compare_loading_label.set_text("Loading posting activity…")
        inspect.compare_loading.visible = True
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
                inspect.edge_meta.set_text("Could not load time series for this edge.")
                with inspect.compare_chart_slot:
                    ui.label("Could not load activity chart.").classes(
                        "text-body2 text-grey-7"
                    )
                return
            tvec0, num_posts0 = result0
            tvec1, num_posts1 = result1
            inspect.edge_meta.set_text(
                f"{user0}: {num_posts0} posts · {user1}: {num_posts1} posts"
            )
            inspect.compare_loading_label.set_text("Rendering activity chart…")
            await asyncio.sleep(0)
            if load_id != self.compare_load_id["n"]:
                return

            options = {
                "tooltip": {"trigger": "axis"},
                "legend": {"data": [user0, user1], "top": 8},
                "grid": {
                    "left": "2%",
                    "right": "2%",
                    "top": 40,
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
            inspect.compare_chart_slot.clear()
            with inspect.compare_chart_slot:
                chart = (
                    ui.echart(options)
                    .classes("w-full")
                    .style("display:block; width:100%; min-width:100%; height:280px;")
                )
                self.compare_chart["chart"] = chart
            self.schedule_chart_resize(chart)

            inspect.compare_loading_label.set_text("Loading interleaved posts…")
            await asyncio.sleep(0)
            if load_id != self.compare_load_id["n"]:
                return
            items = await self.graph.get_overlapping_content(user0, user1)
            if load_id != self.compare_load_id["n"]:
                return
            if items is not None:
                overlap0 = sum(1 for user, _content, _time in items if user == user0)
                overlap1 = sum(1 for user, _content, _time in items if user == user1)
                inspect.edge_meta.set_text(
                    f"{user0}: {num_posts0} posts ({overlap0} overlapping) · "
                    f"{user1}: {num_posts1} posts ({overlap1} overlapping)"
                )
            inspect.scroll_container.clear()
            with inspect.scroll_container:
                if items is None:
                    ui.label("Could not load overlapping posts for this pair.").classes(
                        "text-body2 text-grey-7"
                    )
                elif not items:
                    ui.label(
                        "No posts fall within an overlapping time window "
                        "for this pair (based on step size × window size)."
                    ).classes("text-body2 text-grey-7")
                else:
                    for user, content, time in items:
                        ui.chat_message(
                            content, name=user, stamp=time, sent=user == user0
                        )
        finally:
            if load_id == self.compare_load_id["n"]:
                inspect.compare_loading.visible = False
