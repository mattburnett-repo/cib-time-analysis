from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import networkx as nx
import numpy as np
import pytest
from nicegui.events import GenericEventArguments

from modules.session import StepperContext
from modules.stepper import StepperController
from modules.timeseries_gui_config import DATASET_OPTIONS, METHOD_OPTIONS


def _widget(**attrs):
    w = MagicMock()
    for key, value in attrs.items():
        setattr(w, key, value)
    w.__enter__ = MagicMock(return_value=w)
    w.__exit__ = MagicMock(return_value=False)
    return w


def _weighted_graph():
    g = nx.Graph()
    g.add_edge("alice", "bob", norm_weight=5.0)
    g.add_edge("alice", "carol", norm_weight=3.0)
    return g


@pytest.fixture
def controller():
    graph = SimpleNamespace(
        graph=None,
        cut_graph=None,
        current_set=None,
        create_graph=AsyncMock(),
        create_Egraph=MagicMock(return_value=[{"type": "graph", "links": []}]),
        get_graph_weights=MagicMock(return_value=np.array([5.0, 3.0, 1.0])),
        get_user_tvec=AsyncMock(return_value=(np.array([1.0, 0.0, 1.0]), 2)),
        get_user_content=AsyncMock(return_value=(["hello", "world"], ["t0", "t1"])),
    )
    stepper = _widget(value="Configure")
    ctrl = StepperController()
    ctx = StepperContext(
        graph=graph,
        selected_edge={"user0": None, "user1": None},
        network_chart={"chart": None},
        compare_chart={"chart": None},
        compare_load_id={"n": 0},
        stepper=stepper,
        step_configure=_widget(),
        step_build=_widget(),
        step_weights=_widget(),
        step_explore=_widget(),
        step_inspect=_widget(),
        toggle_data=SimpleNamespace(value=0),
        toggle_analysis=SimpleNamespace(value=0),
        step_size=SimpleNamespace(value=300),
        win_size=SimpleNamespace(value=2),
        config_summary=_widget(),
        progress=_widget(visible=False),
        status_label=_widget(),
        create_button=_widget(),
        next_from_build=_widget(),
        weight_chart_slot=_widget(),
        slider=_widget(value=10),
        edge_select=_widget(options={}),
        selected_edge_label=_widget(),
        network_chart_slot=_widget(),
        inspect_button=_widget(),
        edge_title=_widget(),
        edge_meta=_widget(),
        compare_loading=_widget(visible=False),
        compare_loading_label=_widget(),
        compare_chart_slot=_widget(),
        scroll_container=_widget(),
    )
    with patch.object(stepper, "on_value_change") as on_value_change:
        ctrl.bind(ctx)
        on_value_change.assert_called_once_with(ctrl.on_stepper_change)
    return ctrl


def test_set_step_done_toggles_props(controller):
    step = _widget()
    controller.set_step_done(step, True)
    step.props.assert_called_with("done")
    step.update.assert_called()

    step.reset_mock()
    controller.set_step_done(step, False)
    step.props.assert_called_with(remove="done")


def test_refresh_config_summary_uses_current_settings(controller):
    controller.refresh_config_summary()
    controller.config_summary.set_text.assert_called_once_with(
        f"{DATASET_OPTIONS[0]} · {METHOD_OPTIONS[0]} · step 300s · window 2"
    )


def test_sync_build_step_ui_without_graph(controller):
    controller.sync_build_step_ui()
    controller.status_label.set_text.assert_called_with("Ready when you are.")
    controller.next_from_build.disable.assert_called()


def test_sync_build_step_ui_with_matching_graph(controller):
    controller.graph.graph = _weighted_graph()
    controller.graph.current_set = (0, 0, 300, 2)
    controller.sync_build_step_ui()
    controller.status_label.set_text.assert_called_with("Done. Ready to view results.")
    controller.next_from_build.enable.assert_called()
    controller.step_build.enable.assert_called()
    controller.step_weights.enable.assert_called()


def test_sync_build_step_ui_with_stale_settings(controller):
    controller.graph.graph = _weighted_graph()
    controller.graph.current_set = (1, 0, 300, 2)
    controller.sync_build_step_ui()
    controller.status_label.set_text.assert_called_with(
        "Graph ready. Build again if you changed settings."
    )


@patch("modules.stepper.ui.timer")
def test_go_to_weights_and_explore_schedule_sync(mock_timer, controller):
    controller.go_to_weights()
    controller.stepper.set_value.assert_called_with("Weight distribution")
    mock_timer.assert_called_with(0.15, controller.sync_weights_step_ui, once=True)

    mock_timer.reset_mock()
    controller.go_to_explore()
    controller.stepper.set_value.assert_called_with("Explore network")
    mock_timer.assert_called_with(0.15, controller.sync_explore_step_ui, once=True)


@patch("modules.stepper.ui.notify")
def test_go_to_inspect_requires_selection(mock_notify, controller):
    controller.go_to_inspect()
    mock_notify.assert_called_once()
    controller.step_inspect.enable.assert_not_called()


@patch("modules.stepper.ui.timer")
def test_go_to_inspect_with_selection(mock_timer, controller):
    controller.selected_edge["user0"] = "alice"
    controller.selected_edge["user1"] = "bob"
    controller.stepper.value = "Explore network"

    controller.go_to_inspect()

    controller.step_inspect.enable.assert_called()
    controller.edge_title.set_text.assert_called_with("alice  ↔  bob")
    assert controller.compare_loading.visible is True
    controller.stepper.set_value.assert_called_with("Compare users")
    mock_timer.assert_not_called()


def test_start_over_clears_selection_and_resets_steps(controller):
    controller.selected_edge["user0"] = "alice"
    controller.selected_edge["user1"] = "bob"
    controller.graph.graph = None

    controller.start_over()

    assert controller.selected_edge == {"user0": None, "user1": None}
    controller.edge_select.disable.assert_called()
    controller.inspect_button.disable.assert_called()
    controller.step_build.disable.assert_called()
    controller.stepper.set_value.assert_called_with("Configure")


def test_refresh_edge_select_options_without_cut_graph(controller):
    controller.refresh_edge_select_options()
    controller.edge_select.set_options.assert_called_with({})
    controller.edge_select.disable.assert_called()


def test_refresh_edge_select_options_with_cut_graph(controller):
    controller.graph.cut_graph = _weighted_graph()
    controller.refresh_edge_select_options()
    options = controller.edge_select.set_options.call_args.args[0]
    assert "alice\tbob" in options or "bob\talice" in options
    controller.edge_select.enable.assert_called()


@pytest.mark.asyncio
@patch("modules.stepper.ui.notify")
async def test_select_user_pair_updates_state(mock_notify, controller):
    controller.edge_select.options = {"alice\tbob": "alice  ↔  bob"}
    await controller.select_user_pair("alice", "bob")

    assert controller.selected_edge == {"user0": "alice", "user1": "bob"}
    controller.selected_edge_label.set_text.assert_called_with(
        "Selected: alice  ↔  bob"
    )
    controller.edge_select.set_value.assert_called_with("alice\tbob")
    controller.inspect_button.enable.assert_called()
    mock_notify.assert_called()


def test_on_edge_selected_from_list_ignores_junk_and_duplicates(controller):
    assert controller.on_edge_selected_from_list(None) is None
    assert controller.on_edge_selected_from_list("no-tab") is None

    controller.selected_edge["user0"] = "alice"
    controller.selected_edge["user1"] = "bob"
    controller.on_edge_selected_from_list("bob\talice")
    controller.inspect_button.enable.assert_called()


@pytest.mark.asyncio
@patch("modules.stepper.ui.notify")
async def test_handle_network_chart_click_edge_and_node(mock_notify, controller):
    controller.graph.cut_graph = _weighted_graph()
    edge_event = GenericEventArguments(
        sender=None,
        client=None,
        args={"dataType": "edge", "source": "alice", "target": "bob"},
    )
    result = controller.handle_network_chart_click(edge_event)
    assert result is not None
    await result
    assert controller.selected_edge["user0"] == "alice"
    assert controller.selected_edge["user1"] == "bob"

    mock_notify.reset_mock()
    node_event = GenericEventArguments(
        sender=None, client=None, args={"dataType": "node", "name": "alice"}
    )
    assert controller.handle_network_chart_click(node_event) is None
    mock_notify.assert_called()


@pytest.mark.asyncio
@patch("modules.stepper.ui.label")
async def test_sync_compare_step_ui_without_selection(mock_label, controller):
    mock_label.return_value.classes.return_value = MagicMock()
    await controller.sync_compare_step_ui()
    controller.compare_chart_slot.clear.assert_called()
    assert controller.compare_chart["chart"] is None


@pytest.mark.asyncio
@patch("modules.stepper.ui.chat_message")
@patch("modules.stepper.ui.echart")
@patch("modules.stepper.ui.timer")
async def test_load_edge_inspection_success(
    mock_timer, mock_echart, mock_chat, controller
):
    chart = _widget(options={})
    mock_echart.return_value.classes.return_value.style.return_value = chart

    controller.graph.get_user_content = AsyncMock(
        side_effect=[
            (["a1"], ["2024-01-01"]),
            (["b1"], ["2024-01-02"]),
        ]
    )

    await controller.load_edge_inspection("alice", "bob")

    controller.edge_title.set_text.assert_any_call("alice  ↔  bob")
    assert "alice: 2 posts" in controller.edge_meta.set_text.call_args_list[-1].args[0]
    assert controller.compare_chart["chart"] is chart
    assert controller.compare_loading.visible is False
    mock_chat.assert_called()


@pytest.mark.asyncio
@patch("modules.stepper.ui.label")
async def test_load_edge_inspection_handles_missing_series(mock_label, controller):
    mock_label.return_value.classes.return_value = MagicMock()
    controller.graph.get_user_tvec = AsyncMock(return_value=None)

    await controller.load_edge_inspection("alice", "bob")

    controller.edge_meta.set_text.assert_called_with(
        "Could not load time series for this edge."
    )
    assert controller.compare_loading.visible is False


@pytest.mark.asyncio
async def test_load_edge_inspection_aborts_when_superseded(controller):
    async def slow_tvec(*_args):
        controller.compare_load_id["n"] += 1
        return (np.array([1.0]), 1)

    controller.graph.get_user_tvec = AsyncMock(side_effect=slow_tvec)
    await controller.load_edge_inspection("alice", "bob")
    controller.graph.get_user_content.assert_not_called()


@pytest.mark.asyncio
async def test_handle_create_unlocks_flow(controller):
    await controller.handle_create()
    controller.graph.create_graph.assert_awaited_once_with(0, 0, 300, 2)
    controller.status_label.set_text.assert_called_with("Done. Ready to view results.")
    controller.slider.enable.assert_called()
    controller.next_from_build.enable.assert_called()


@pytest.mark.asyncio
@patch("modules.stepper.ui.label")
@patch("modules.stepper.ui.timer")
async def test_handle_slider_rebuilds_when_chart_missing(
    mock_timer, mock_label, controller
):
    mock_label.return_value.classes.return_value = MagicMock()
    controller.network_chart["chart"] = None
    controller.graph.graph = None

    await controller.handle_slider(20)

    controller.graph.create_Egraph.assert_called_with(20)
    controller.network_chart_slot.clear.assert_called()


@pytest.mark.asyncio
async def test_handle_slider_updates_existing_chart(controller):
    chart = _widget(options={"series": []})
    controller.network_chart["chart"] = chart
    controller.graph.cut_graph = _weighted_graph()
    series = [{"type": "graph", "links": [1, 2]}]
    controller.graph.create_Egraph.return_value = series

    await controller.handle_slider(25)

    assert chart.options["series"] == series
    chart.update.assert_called()
    chart.run_chart_method.assert_called_with("resize")


@patch("modules.stepper.ui.timer")
def test_on_stepper_change_routes_steps(mock_timer, controller):
    controller.on_stepper_change(SimpleNamespace(value="Build graph"))
    controller.status_label.set_text.assert_called()

    controller.on_stepper_change(SimpleNamespace(value="Weight distribution"))
    mock_timer.assert_called_with(0.15, controller.sync_weights_step_ui, once=True)

    mock_timer.reset_mock()
    controller.on_stepper_change(SimpleNamespace(value="Explore network"))
    mock_timer.assert_called_with(0.15, controller.sync_explore_step_ui, once=True)

    mock_timer.reset_mock()
    controller.on_stepper_change(SimpleNamespace(value="Compare users"))
    mock_timer.assert_called_with(0.15, controller.sync_compare_step_ui, once=True)


@patch("modules.stepper.ui.timer")
def test_schedule_chart_resize_skips_deleted_charts(mock_timer, controller):
    chart = _widget(is_deleted=True)
    controller.schedule_chart_resize(chart, delays=(0.05,))
    callback = mock_timer.call_args.args[1]
    callback()
    chart.run_chart_method.assert_not_called()

    chart = _widget(is_deleted=False)
    controller.schedule_chart_resize(chart, delays=(0.05,))
    callback = mock_timer.call_args.args[1]
    callback()
    chart.run_chart_method.assert_called_with("resize")


@patch("modules.stepper.ui.label")
@patch("modules.stepper.ui.timer")
def test_sync_weights_step_ui_without_graph(mock_timer, mock_label, controller):
    mock_label.return_value.classes.return_value = MagicMock()
    controller.sync_weights_step_ui()
    controller.weight_chart_slot.clear.assert_called()
    mock_label.assert_called()
