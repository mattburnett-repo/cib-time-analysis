"""Smoke checks for the NiceGUI entrypoint (no browser / full page build)."""

from dataclasses import fields

from app.time_gui_main import _chrome_devtools_probe, main_page
from modules.session import StepperContext


def test_chrome_devtools_probe_route_handler():
    payload = _chrome_devtools_probe()
    assert payload["Browser"] == "NiceGUI"
    assert "Protocol-Version" in payload


def test_main_page_is_registered_callable():
    assert callable(main_page)


def test_stepper_context_field_count_is_stable():
    # Guards against silent bind() breakage when widgets are added/removed.
    names = {field.name for field in fields(StepperContext)}
    assert "graph" in names
    assert "stepper" in names
    assert "scroll_container" in names
    assert len(names) == 32
