from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import networkx as nx
import pytest
from nicegui.events import GenericEventArguments

from modules.session import StepperContext
from modules.stepper import StepperController
from modules.stepper_steps import (
    BuildStep,
    ConfigureStep,
    ExploreStep,
    InspectStep,
    StepperPanels,
)
from modules.timeseries_gui_config import (
    DATASET_OPTIONS,
    METHOD_OPTIONS,
    STEP_BUILD,
    STEP_CONFIGURE,
    STEP_EXPLORE,
    STEP_INSPECT,
    STEP_SYNC_DELAY,
)


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


def _panels():
    return StepperPanels(
        configure=ConfigureStep(
            step=_widget(),
            toggle_data=SimpleNamespace(value=0),
            toggle_analysis=SimpleNamespace(value=0),
            step_size=SimpleNamespace(value=300),
            win_size=SimpleNamespace(value=2),
        ),
        build=BuildStep(
            step=_widget(),
            intro_label=_widget(visible=True),
            config_summary=_widget(),
            progress=_widget(visible=False),
            status_label=_widget(),
            create_button=_widget(),
            next_from_build=_widget(),
        ),
        explore=ExploreStep(
            step=_widget(),
            slider=_widget(value=10),
            edge_select=_widget(options={}),
            edge_group_checks={},
            network_chart_slot=_widget(),
            inspect_button=_widget(),
        ),
        inspect=InspectStep(
            step=_widget(),
            edge_title=_widget(),
            edge_meta=_widget(),
            compare_loading=_widget(visible=False),
            compare_loading_label=_widget(),
            scroll_container=_widget(),
        ),
    )


@pytest.fixture
def controller():
    graph = SimpleNamespace(
        graph=None,
        cut_graph=None,
        current_set=None,
        create_graph=AsyncMock(),
        create_egraph=MagicMock(return_value=[{"type": "graph", "links": []}]),
        get_user_content=AsyncMock(return_value=(["hello", "world"], ["t0", "t1"])),
        get_overlapping_content=AsyncMock(
            return_value=[("alice", "hello", "t0"), ("bob", "world", "t1")]
        ),
    )
    stepper = _widget(value=STEP_CONFIGURE)
    ctrl = StepperController()
    ctx = StepperContext(
        graph=graph,
        selected_edge={"user0": None, "user1": None},
        network_chart={"chart": None, "full_series": None},
        compare_load_id={"n": 0},
        stepper=stepper,
        panels=_panels(),
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
    controller.panels.build.config_summary.set_text.assert_called_once_with(
        f"{DATASET_OPTIONS[0]} · {METHOD_OPTIONS[0]} · "
        f"windows are 600s, advancing every 300s"
    )


def test_sync_build_step_ui_without_graph(controller):
    controller.sync_build_step_ui()
    controller.panels.build.status_label.set_text.assert_called_with(
        "Ready when you are."
    )
    controller.panels.build.next_from_build.disable.assert_called()


def test_sync_build_step_ui_with_matching_graph(controller):
    controller.graph.graph = _weighted_graph()
    controller.graph.current_set = (0, 0, 300, 2)
    controller.sync_build_step_ui()
    controller.panels.build.status_label.set_text.assert_called_with(
        "Done. Ready to view results."
    )
    controller.panels.build.create_button.disable.assert_called()
    controller.panels.build.next_from_build.enable.assert_called()
    controller.panels.build.step.enable.assert_called()
    controller.panels.explore.step.enable.assert_called()


def test_sync_build_step_ui_with_stale_settings(controller):
    controller.graph.graph = _weighted_graph()
    controller.graph.current_set = (1, 0, 300, 2)
    controller.sync_build_step_ui()
    controller.panels.build.status_label.set_text.assert_called_with(
        "Graph ready. Build again if you changed settings."
    )
    controller.panels.build.create_button.enable.assert_called()


@patch("modules.stepper_nav.ui.timer")
def test_go_to_explore_schedules_sync(mock_timer, controller):
    controller.go_to_explore()
    controller.stepper.set_value.assert_called_with(STEP_EXPLORE)
    mock_timer.assert_called_with(
        STEP_SYNC_DELAY, controller.sync_explore_step_ui, once=True
    )


@patch("modules.stepper_nav.ui.notify")
def test_go_to_inspect_requires_selection(mock_notify, controller):
    controller.go_to_inspect()
    mock_notify.assert_called_once()
    controller.panels.inspect.step.enable.assert_not_called()


@patch("modules.stepper_nav.ui.timer")
def test_go_to_inspect_with_selection(mock_timer, controller):
    controller.selected_edge["user0"] = "alice"
    controller.selected_edge["user1"] = "bob"
    controller.stepper.value = STEP_EXPLORE

    controller.go_to_inspect()

    controller.panels.inspect.step.enable.assert_called()
    controller.panels.inspect.edge_title.set_text.assert_called_with("alice  ↔  bob")
    assert controller.panels.inspect.compare_loading.visible is True
    controller.stepper.set_value.assert_called_with(STEP_INSPECT)
    mock_timer.assert_not_called()


def test_start_over_clears_selection_and_resets_steps(controller):
    controller.selected_edge["user0"] = "alice"
    controller.selected_edge["user1"] = "bob"
    controller.graph.graph = None

    controller.start_over()

    assert controller.selected_edge == {"user0": None, "user1": None}
    controller.panels.explore.edge_select.disable.assert_called()
    controller.panels.explore.inspect_button.disable.assert_called()
    controller.panels.build.step.disable.assert_called()
    controller.stepper.set_value.assert_called_with(STEP_CONFIGURE)


def test_refresh_edge_select_options_without_cut_graph(controller):
    controller.refresh_edge_select_options()
    controller.panels.explore.edge_select.set_options.assert_called_with({})
    controller.panels.explore.edge_select.disable.assert_called()


def test_refresh_edge_select_options_with_cut_graph(controller):
    controller.graph.cut_graph = _weighted_graph()
    controller.refresh_edge_select_options()
    options = controller.panels.explore.edge_select.set_options.call_args.args[0]
    assert "alice\tbob" in options or "bob\talice" in options
    controller.panels.explore.edge_select.enable.assert_called()


@pytest.mark.asyncio
async def test_select_user_pair_updates_state(controller):
    controller.panels.explore.edge_select.options = {"alice\tbob": "alice  ↔  bob"}
    await controller.select_user_pair("alice", "bob")

    assert controller.selected_edge == {"user0": "alice", "user1": "bob"}
    controller.panels.explore.edge_select.set_value.assert_called_with("alice\tbob")
    controller.panels.explore.inspect_button.enable.assert_called()


def test_on_edge_selected_from_list_ignores_junk_and_duplicates(controller):
    assert controller.on_edge_selected_from_list(None) is None
    assert controller.on_edge_selected_from_list("no-tab") is None

    controller.selected_edge["user0"] = "alice"
    controller.selected_edge["user1"] = "bob"
    controller.on_edge_selected_from_list("bob\talice")
    controller.panels.explore.inspect_button.enable.assert_called()


@pytest.mark.asyncio
@patch("modules.stepper_explore.ui.notify")
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
@patch("modules.stepper_compare.ui.label")
async def test_sync_compare_step_ui_without_selection(mock_label, controller):
    mock_label.return_value.classes.return_value = MagicMock()
    await controller.sync_compare_step_ui()
    controller.panels.inspect.scroll_container.clear.assert_called()
    mock_label.assert_called()


@pytest.mark.asyncio
@patch("modules.stepper_compare.ui.chat_message")
async def test_load_edge_inspection_success(mock_chat, controller):
    controller.graph.get_overlapping_content = AsyncMock(
        return_value=[
            ("alice", "a1", "2024-01-01 00:00:00"),
            ("bob", "b1", "2024-01-02 14:30:05"),
        ]
    )

    await controller.load_edge_inspection("alice", "bob")

    controller.panels.inspect.edge_title.set_text.assert_any_call("alice  ↔  bob")
    meta = controller.panels.inspect.edge_meta.set_text.call_args_list[-1].args[0]
    assert "alice: 1 overlapping" in meta
    assert "bob: 1 overlapping" in meta
    assert controller.panels.inspect.compare_loading.visible is False
    mock_chat.assert_any_call("2024-01-01\n00:00:00\n\na1", name="alice", sent=True)
    mock_chat.assert_any_call("2024-01-02\n14:30:05\n\nb1", name="bob", sent=False)


def test_format_post_body_puts_date_and_time_above_text():
    from modules.stepper_compare import format_post_body

    assert format_post_body("hello", "2024-01-01 00:00:00") == (
        "2024-01-01\n00:00:00\n\nhello"
    )
    assert format_post_body("hello", "not-a-date") == "not-a-date\n\nhello"


@pytest.mark.asyncio
@patch("modules.stepper_compare.ui.label")
async def test_load_edge_inspection_handles_missing_posts(mock_label, controller):
    mock_label.return_value.classes.return_value = MagicMock()
    controller.graph.get_overlapping_content = AsyncMock(return_value=None)

    await controller.load_edge_inspection("alice", "bob")

    mock_label.assert_called()
    assert controller.panels.inspect.compare_loading.visible is False


@pytest.mark.asyncio
async def test_load_edge_inspection_aborts_when_superseded(controller):
    async def slow_overlap(*_args):
        controller.compare_load_id["n"] += 1
        return [("alice", "a1", "t0")]

    controller.graph.get_overlapping_content = AsyncMock(side_effect=slow_overlap)
    await controller.load_edge_inspection("alice", "bob")
    controller.panels.inspect.edge_meta.set_text.assert_called_with("")


@pytest.mark.asyncio
async def test_handle_create_unlocks_flow(controller):
    await controller.handle_create()
    controller.graph.create_graph.assert_awaited_once_with(0, 0, 300, 2)
    controller.panels.build.status_label.set_text.assert_called_with(
        "Done. Ready to view results."
    )
    controller.panels.explore.slider.enable.assert_called()
    controller.panels.build.next_from_build.enable.assert_called()


@pytest.mark.asyncio
@patch("modules.stepper_explore.ui.label")
@patch("modules.stepper_explore.ui.timer")
async def test_handle_slider_rebuilds_when_chart_missing(
    mock_timer, mock_label, controller
):
    mock_label.return_value.classes.return_value = MagicMock()
    controller.network_chart["chart"] = None
    controller.graph.graph = None

    await controller.handle_slider(20)

    controller.graph.create_egraph.assert_called_with(20)
    controller.panels.explore.network_chart_slot.clear.assert_called()


@pytest.mark.asyncio
async def test_handle_slider_updates_existing_chart(controller):
    chart = _widget(options={"series": []})
    controller.network_chart["chart"] = chart
    controller.graph.cut_graph = _weighted_graph()
    series = [
        {
            "type": "graph",
            "data": [{"name": "a", "id": "a"}, {"name": "b", "id": "b"}],
            "links": [
                {
                    "source": "a",
                    "target": "b",
                    "edgeGroup": "pair",
                    "lineStyle": {"color": "#B0B7C3"},
                }
            ],
        }
    ]
    controller.graph.create_egraph.return_value = series

    await controller.handle_slider(25)

    assert chart.options["series"][0]["links"] == series[0]["links"]
    assert controller.network_chart["full_series"] == series
    chart.update.assert_called()
    chart.run_chart_method.assert_called_with("resize")


def test_on_edge_group_visibility_change_filters_links(controller):
    from modules.chart_utils import EDGE_GROUP_2_5, EDGE_GROUP_PAIR

    chart = _widget(options={"series": []})
    full = [
        {
            "type": "graph",
            "data": [{"name": "a"}, {"name": "b"}, {"name": "c"}],
            "links": [
                {"source": "a", "target": "b", "edgeGroup": EDGE_GROUP_PAIR},
                {"source": "b", "target": "c", "edgeGroup": EDGE_GROUP_2_5},
            ],
        }
    ]
    controller.network_chart["chart"] = chart
    controller.network_chart["full_series"] = full
    controller.panels.explore.edge_group_checks = {
        EDGE_GROUP_PAIR: _widget(value=True),
        EDGE_GROUP_2_5: _widget(value=False),
        "g6_10": _widget(value=True),
        "g11_20": _widget(value=True),
    }

    controller.on_edge_group_visibility_change()

    links = chart.options["series"][0]["links"]
    assert len(links) == 1
    assert links[0]["edgeGroup"] == EDGE_GROUP_PAIR
    assert chart.options["series"][0]["data"] == full[0]["data"]


@patch("modules.stepper_nav.ui.timer")
def test_on_stepper_change_routes_steps(mock_timer, controller):
    controller.on_stepper_change(SimpleNamespace(value=STEP_BUILD))
    controller.panels.build.status_label.set_text.assert_called()

    mock_timer.reset_mock()
    controller.on_stepper_change(SimpleNamespace(value=STEP_EXPLORE))
    mock_timer.assert_called_with(
        STEP_SYNC_DELAY, controller.sync_explore_step_ui, once=True
    )

    mock_timer.reset_mock()
    controller.on_stepper_change(SimpleNamespace(value=STEP_INSPECT))
    mock_timer.assert_called_with(
        STEP_SYNC_DELAY, controller.sync_compare_step_ui, once=True
    )


@patch("modules.stepper_explore.ui.timer")
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
