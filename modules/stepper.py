from modules.session import StepperContext
from modules.stepper_compare import StepperCompareMixin
from modules.stepper_explore import StepperExploreMixin
from modules.stepper_nav import StepperNavMixin


class StepperController(StepperNavMixin, StepperExploreMixin, StepperCompareMixin):
    """Stepper navigation and step-panel sync for the time-analysis UI.

    Lifecycle:
    1. Constructed empty in time_gui_main (methods only; no session/widgets yet).
    2. Passed into build_stepper_panels so buttons can wire on_click to methods.
    3. After the UI exists, bind(StepperContext) copies graph / charts / panels /
       stepper onto self via apply_to, then registers on_stepper_change.
    4. Clicks and step changes then use self.panels.* and session state.

    Field shape lives on StepperContext; this class does not declare them in __init__.
    Behavior is split across StepperNavMixin, StepperExploreMixin, StepperCompareMixin.
    """

    def bind(self, ctx: StepperContext) -> None:
        """Attach typed page context and listen for stepper value changes."""
        ctx.apply_to(self)
        self.stepper.on_value_change(self.on_stepper_change)
