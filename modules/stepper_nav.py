"""Build-step and stepper navigation helpers for StepperController."""

from __future__ import annotations

from nicegui import core, ui

from modules.timeseries_gui_config import (
    DATASET_OPTIONS,
    METHOD_OPTIONS,
    STEP_BUILD,
    STEP_CONFIGURE,
    STEP_EXPLORE,
    STEP_INSPECT,
    STEP_SYNC_DELAY,
)


class StepperNavMixin:
    """Configure → Build navigation, unlock rules, and step-value routing."""

    def dismiss_tooltips(self) -> None:
        # Quasar can leave portal tooltips stuck after the trigger leaves the
        # viewport (common with stepper transitions / Codespaces browsers).
        if core.loop is None:
            return
        ui.run_javascript(
            "document.querySelectorAll('.q-tooltip').forEach((el) => el.remove())"
        )

    def set_step_done(self, step, done: bool) -> None:
        if done:
            step.props("done")
        else:
            step.props(remove="done")
        step.update()

    def refresh_config_summary(self):
        cfg = self.panels.configure
        self.panels.build.config_summary.set_text(
            f"{DATASET_OPTIONS[cfg.toggle_data.value]} · "
            f"{METHOD_OPTIONS[cfg.toggle_analysis.value]} · "
            f"step {int(cfg.step_size.value)}s · "
            f"window size (steps) {int(cfg.win_size.value)}"
        )

    def unlock_after_build(self):
        self.set_step_done(self.panels.configure.step, True)
        self.set_step_done(self.panels.build.step, True)
        self.panels.build.step.enable()
        self.panels.explore.step.enable()

    def sync_build_step_ui(self):
        """Restore Build-step labels/buttons from graph session state."""
        self.refresh_config_summary()
        build = self.panels.build
        cfg = self.panels.configure
        if self.graph.graph is not None:
            build.intro_label.visible = False
            build.progress.visible = False
            pending = (
                cfg.toggle_analysis.value,
                cfg.toggle_data.value,
                cfg.step_size.value,
                cfg.win_size.value,
            )
            if self.graph.current_set == pending:
                build.status_label.set_text("Done. Ready to view results.")
                build.create_button.disable()
            else:
                build.status_label.set_text(
                    "Graph ready. Build again if you changed settings."
                )
                build.create_button.enable()
            build.next_from_build.enable()
            self.unlock_after_build()
        else:
            build.intro_label.visible = True
            build.status_label.set_text("Ready when you are.")
            build.create_button.enable()
            build.next_from_build.disable()

    def go_to_build(self):
        self.dismiss_tooltips()
        self.set_step_done(self.panels.configure.step, True)
        self.panels.build.step.enable()
        self.sync_build_step_ui()
        self.stepper.set_value(STEP_BUILD)

    def go_to_explore(self):
        self.dismiss_tooltips()
        self.set_step_done(self.panels.build.step, True)
        self.panels.explore.step.enable()
        self.stepper.set_value(STEP_EXPLORE)
        ui.timer(STEP_SYNC_DELAY, self.sync_explore_step_ui, once=True)

    def go_to_inspect(self):
        if self.selected_edge["user0"] is None or self.selected_edge["user1"] is None:
            ui.notify("Select a user link first (list or network edge).")
            return
        self.dismiss_tooltips()
        inspect = self.panels.inspect
        self.set_step_done(self.panels.explore.step, True)
        inspect.step.enable()
        # Show loading immediately so it is visible while the step opens.
        inspect.edge_title.set_text(
            f"{self.selected_edge['user0']}  ↔  {self.selected_edge['user1']}"
        )
        inspect.edge_meta.set_text("")
        inspect.scroll_container.clear()
        inspect.compare_chart_slot.clear()
        self.compare_chart["chart"] = None
        inspect.compare_loading_label.set_text("Preparing comparison…")
        inspect.compare_loading.visible = True
        already_on_compare = self.stepper.value == STEP_INSPECT
        self.stepper.set_value(STEP_INSPECT)
        # on_stepper_change loads when the step changes; only schedule here
        # if we were already on Compare users (no value-change event).
        if already_on_compare:
            ui.timer(STEP_SYNC_DELAY, self.sync_compare_step_ui, once=True)

    def start_over(self):
        self.dismiss_tooltips()
        self.set_step_done(self.panels.configure.step, False)
        self.set_step_done(self.panels.build.step, False)
        self.set_step_done(self.panels.explore.step, False)
        self.set_step_done(self.panels.inspect.step, False)
        self.panels.build.step.disable()
        self.panels.explore.step.disable()
        self.panels.inspect.step.disable()
        self.selected_edge["user0"] = None
        self.selected_edge["user1"] = None
        explore = self.panels.explore
        explore.edge_select.set_options({})
        explore.edge_select.set_value(None)
        explore.edge_select.disable()
        explore.inspect_button.disable()
        if self.graph.graph is not None:
            self.unlock_after_build()
        self.stepper.set_value(STEP_CONFIGURE)

    def on_stepper_change(self, e):
        # Covers Back/Next and any set_value navigation (incl. Codespaces).
        self.dismiss_tooltips()
        if e.value == STEP_BUILD:
            self.sync_build_step_ui()
        elif e.value == STEP_EXPLORE:
            ui.timer(STEP_SYNC_DELAY, self.sync_explore_step_ui, once=True)
        elif e.value == STEP_INSPECT:
            ui.timer(STEP_SYNC_DELAY, self.sync_compare_step_ui, once=True)

    async def handle_create(self):
        cfg = self.panels.configure
        build = self.panels.build
        build.create_button.disable()
        build.progress.visible = True
        build.status_label.set_text("Building graph…")
        await self.graph.create_graph(
            cfg.toggle_analysis.value,
            cfg.toggle_data.value,
            cfg.step_size.value,
            cfg.win_size.value,
        )
        build.progress.visible = False
        build.intro_label.visible = False
        build.status_label.set_text("Done. Ready to view results.")

        self.panels.explore.slider.enable()
        build.next_from_build.enable()
        self.unlock_after_build()
