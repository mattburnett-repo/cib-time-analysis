from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import networkx as nx
import numpy as np
import pytest

from modules.chart_utils import (
    ECHART_GRAPH_DEFAULTS,
    EDGE_COLOR_GROUP_2_5,
    EDGE_COLOR_GROUP_6_10,
    EDGE_COLOR_GROUP_11_20,
    EDGE_COLOR_PAIR,
    NETWORK_CLICK_JS,
    edge_color_for_link,
    edge_is_one_to_one,
    network_hover_clear_labels_js,
    network_hover_show_labels_js,
    plot_subgraph_echart,
    resolve_node_ref,
    users_from_edge_payload,
)
from modules.my_graph import MyGraph, cut_graph_by_weight


def _weighted_graph():
    g = nx.Graph()
    g.add_edge("a", "b", norm_weight=5.0)
    g.add_edge("a", "c", norm_weight=3.0)
    g.add_edge("b", "c", norm_weight=1.0)
    g.add_edge("c", "d", norm_weight=0.5)
    return g


@pytest.fixture
def my_graph():
    fake_manager = SimpleNamespace(
        Value=lambda *_args, **_kwargs: SimpleNamespace(value=0.0)
    )
    with patch("modules.my_graph.Manager", return_value=fake_manager):
        yield MyGraph()


def test_cut_graph_by_weight_keeps_top_edges():
    cut = cut_graph_by_weight(_weighted_graph(), num_top=2)

    weights = sorted((wt for _, _, wt in cut.edges.data("norm_weight")), reverse=True)
    assert len(cut.edges) == 2
    assert weights == [5.0, 3.0]
    assert "d" not in cut.nodes


def test_cut_graph_by_weight_removes_isolates_when_threshold_high():
    cut = cut_graph_by_weight(_weighted_graph(), num_top=1)

    assert cut.number_of_edges() == 1
    assert set(cut.nodes) == {"a", "b"}


def test_cut_graph_by_weight_keeps_all_when_num_top_exceeds_edges():
    original = _weighted_graph()
    cut = cut_graph_by_weight(original, num_top=100)

    assert cut.number_of_edges() == original.number_of_edges()


def test_plot_subgraph_echart_series_shape():
    series = plot_subgraph_echart(_weighted_graph())

    assert len(series) == 1
    assert series[0]["type"] == "graph"
    assert {node["name"] for node in series[0]["data"]} == {"a", "b", "c", "d"}
    assert len(series[0]["links"]) == 4
    assert series[0]["roam"] == "scale"
    assert series[0]["lineStyle"]["width"] == 8
    assert all(">" in link["name"] for link in series[0]["links"])


def test_plot_subgraph_echart_colors_by_group_size():
    g = nx.Graph()
    g.add_edge("a", "b", norm_weight=1.0)  # 1:1
    for i in range(3):  # hub degree 3 → 2–5
        g.add_edge("h3", f"l3_{i}", norm_weight=1.0)
    for i in range(7):  # hub degree 7 → 6–10
        g.add_edge("h7", f"l7_{i}", norm_weight=1.0)
    for i in range(12):  # hub degree 12 → 11–20
        g.add_edge("h12", f"l12_{i}", norm_weight=1.0)

    links = {
        frozenset((lk["source"], lk["target"])): lk
        for lk in plot_subgraph_echart(g)[0]["links"]
    }
    assert links[frozenset(("a", "b"))]["lineStyle"]["color"] == EDGE_COLOR_PAIR
    assert (
        links[frozenset(("h3", "l3_0"))]["lineStyle"]["color"] == EDGE_COLOR_GROUP_2_5
    )
    assert (
        links[frozenset(("h7", "l7_0"))]["lineStyle"]["color"] == EDGE_COLOR_GROUP_6_10
    )
    assert (
        links[frozenset(("h12", "l12_0"))]["lineStyle"]["color"]
        == EDGE_COLOR_GROUP_11_20
    )
    assert edge_color_for_link(g, "h12", "l12_0") == EDGE_COLOR_GROUP_11_20
    assert edge_is_one_to_one(g, "a", "b")
    assert not edge_is_one_to_one(g, "h3", "l3_0")


def test_echart_defaults_favor_edge_clicks():
    assert ECHART_GRAPH_DEFAULTS["roam"] == "scale"
    assert ECHART_GRAPH_DEFAULTS["lineStyle"]["width"] >= 8
    assert ECHART_GRAPH_DEFAULTS["label"]["show"] is False
    assert ECHART_GRAPH_DEFAULTS["emphasis"]["focus"] == "adjacency"
    assert "label" not in ECHART_GRAPH_DEFAULTS["emphasis"]
    assert "source" in NETWORK_CLICK_JS
    assert "target" in NETWORK_CLICK_JS
    assert "dataType" in NETWORK_CLICK_JS


def test_network_hover_label_js_targets_chart_and_endpoints():
    show_js = network_hover_show_labels_js(42)
    clear_js = network_hover_clear_labels_js(42)
    assert "getElement(42)" in show_js
    assert "dataType === 'edge'" in show_js
    assert "d.source" in show_js and "d.target" in show_js
    assert "show: show" in show_js
    assert "getElement(42)" in clear_js
    assert "show: false" in clear_js


def test_resolve_node_ref_string_and_index():
    nodes = ["alice", "bob", "carol"]
    assert resolve_node_ref("alice") == "alice"
    assert resolve_node_ref(1, nodes) == "bob"
    assert resolve_node_ref(99, nodes) is None
    assert resolve_node_ref(None) is None


def test_users_from_edge_payload_source_target():
    pair = users_from_edge_payload(
        {"dataType": "edge", "source": "alice", "target": "bob"}
    )
    assert pair == ("alice", "bob")


def test_users_from_edge_payload_nested_data_and_list_wrap():
    pair = users_from_edge_payload(
        [
            {
                "dataType": "edge",
                "data": {"source": "carol", "target": "alice"},
            }
        ]
    )
    assert pair == ("carol", "alice")


def test_users_from_edge_payload_name_fallback_and_index_nodes():
    by_name = users_from_edge_payload({"name": "alice > bob"})
    assert by_name == ("alice", "bob")

    nodes = ["alice", "bob", "carol"]
    by_index = users_from_edge_payload(
        {"dataType": "edge", "source": 0, "target": 2}, nodes
    )
    assert by_index == ("alice", "carol")


def test_users_from_edge_payload_ignores_nodes_and_junk():
    assert users_from_edge_payload({"dataType": "node", "name": "alice"}) is None
    assert users_from_edge_payload(None) is None
    assert users_from_edge_payload("not-a-payload") is None


@pytest.mark.asyncio
async def test_mygraph_csv_cache_loads_once_and_uses_window(my_graph):
    from app.time_analysis import overlapping_content_for_users
    from modules.timeseries_gui_config import DATASETS

    my_graph.graph = _weighted_graph()
    my_graph.current_set = (0, 0, 300, 2)
    csv_df = object()
    with patch("modules.my_graph.run.io_bound", new_callable=AsyncMock) as io_bound:
        io_bound.return_value = (csv_df, None)
        dataset, df1 = await my_graph._ensure_csv()
        _dataset2, df2 = await my_graph._ensure_csv()
        assert dataset is DATASETS[0]
        assert df1 is df2 is csv_df
        assert io_bound.await_count == 1

        io_bound.return_value = [("a", "hello", "t0")]
        result = await my_graph.get_overlapping_content("a", "b")
        assert result == [("a", "hello", "t0")]
        assert io_bound.await_count == 2
        assert io_bound.await_args.args[0] is overlapping_content_for_users
        assert io_bound.await_args.args[7] == 600


@pytest.mark.asyncio
async def test_mygraph_create_graph_always_rebuilds(my_graph):
    first = _weighted_graph()
    second = nx.Graph()
    second.add_edge("x", "y", norm_weight=9.0)

    with patch("modules.my_graph.run.cpu_bound", new_callable=AsyncMock) as cpu_bound:
        cpu_bound.side_effect = [first, second]
        await my_graph.create_graph(0, 0, t_step=300, win_size=2)
        assert my_graph.graph is first
        assert my_graph.current_set == (0, 0, 300, 2)

        await my_graph.create_graph(0, 0, t_step=300, win_size=2)
        assert my_graph.graph is second
        assert cpu_bound.await_count == 2


def test_mygraph_create_egraph_without_graph(my_graph):
    assert my_graph.create_egraph() is None


def test_mygraph_create_egraph_with_graph(my_graph):
    my_graph.graph = _weighted_graph()

    series = my_graph.create_egraph(num_top=2)

    assert series is not None
    assert len(series[0]["links"]) == 2
    assert my_graph.cut_graph.number_of_edges() == 2


@pytest.mark.asyncio
async def test_mygraph_getters_require_graph_and_membership(my_graph):
    assert await my_graph.get_user_content("alice") is None
    assert await my_graph.get_overlapping_content("alice", "bob") is None

    my_graph.graph = _weighted_graph()
    my_graph.current_set = (0, 0, 60, 2)
    assert await my_graph.get_user_content("missing") is None
    assert await my_graph.get_overlapping_content("missing", "bob") is None
