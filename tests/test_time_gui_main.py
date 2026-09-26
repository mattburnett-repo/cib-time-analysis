"""Smoke checks for the NiceGUI entrypoint (no browser / full page build)."""

import inspect
from dataclasses import fields

from app.time_gui_main import _chrome_devtools_probe, main_page
from modules.session import StepperContext


def test_chrome_devtools_probe_route_handler():
    payload = _chrome_devtools_probe()
    assert payload["Browser"] == "NiceGUI"
    assert "Protocol-Version" in payload


def test_main_page_is_registered_callable():
    assert callable(main_page)


def test_stepper_is_not_header_navigable():
    source = inspect.getsource(main_page)
    assert "header-nav" not in source
    assert 'props("animated")' in source


def test_stepper_context_keeps_panels_nested():
    # Guards against silently re-flattening widgets into bind() fields.
    names = {field.name for field in fields(StepperContext)}
    assert names == {
        "graph",
        "selected_edge",
        "network_chart",
        "compare_chart",
        "compare_load_id",
        "stepper",
        "panels",
    }
