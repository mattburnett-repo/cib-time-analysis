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
            contents0, time0 = await self.graph.get_user_content(user0)
            contents1, time1 = await self.graph.get_user_content(user1)
            if load_id != self.compare_load_id["n"]:
                return
            user_and_contents = [(user0, c, t) for c, t in zip(contents0, time0)]
            user_and_contents += [(user1, c, t) for c, t in zip(contents1, time1)]
            user_and_contents.sort(key=lambda x: x[2])
            inspect.scroll_container.clear()
            with inspect.scroll_container:
                for user, content, time in user_and_contents:
                    ui.chat_message(content, name=user, stamp=time, sent=user == user0)
        finally:
            if load_id == self.compare_load_id["n"]:
                inspect.compare_loading.visible = False
