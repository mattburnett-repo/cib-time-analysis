"""Compare-users panel loading for StepperController."""

from __future__ import annotations

import asyncio

from dateutil import parser
from nicegui import ui

from modules.timeseries_gui_config import STEP_EXPLORE


def format_post_body(content, raw_time) -> str:
    """Put separate date and time lines above the post text."""
    text = str(raw_time).strip()
    body = str(content)
    if not text:
        return body
    try:
        dt = parser.parse(text)
    except (TypeError, ValueError, OverflowError):
        return f"{text}\n\n{body}"
    return f"{dt.strftime('%Y-%m-%d')}\n{dt.strftime('%H:%M:%S')}\n\n{body}"


class StepperCompareMixin:
    """Interleaved post timeline for a selected edge."""

    async def sync_compare_step_ui(self):
        user0 = self.selected_edge["user0"]
        user1 = self.selected_edge["user1"]
        if user0 is None or user1 is None:
            slot = self.panels.inspect.scroll_container
            slot.clear()
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

        inspect.edge_title.set_text(f"{user0}  ↔  {user1}")
        inspect.edge_meta.set_text("")
        inspect.compare_loading_label.set_text("Loading interleaved posts…")
        inspect.compare_loading.visible = True
        # Let the browser paint the loader before starting CSV work.
        await asyncio.sleep(0)
        if load_id != self.compare_load_id["n"]:
            return
        try:
            items = await self.graph.get_overlapping_content(user0, user1)
            if load_id != self.compare_load_id["n"]:
                return
            if items is not None:
                overlap0 = sum(1 for user, _content, _time in items if user == user0)
                overlap1 = sum(1 for user, _content, _time in items if user == user1)
                inspect.edge_meta.set_text(
                    f"{user0}: {overlap0} overlapping · "
                    f"{user1}: {overlap1} overlapping"
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
                        "for this pair (window duration = time step × window width)."
                    ).classes("text-body2 text-grey-7")
                else:
                    for user, content, time in items:
                        ui.chat_message(
                            format_post_body(content, time),
                            name=user,
                            sent=user == user0,
                        )
        finally:
            if load_id == self.compare_load_id["n"]:
                inspect.compare_loading.visible = False
