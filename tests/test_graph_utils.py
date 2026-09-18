from types import SimpleNamespace
from unittest.mock import patch

import networkx as nx
import numpy as np
import pytest

from modules.chart_utils import (
    _NETWORK_CLICK_JS,
    ePlotDefaultOptions,
    plot_subpgraph_egraph,
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


def test_plot_subgraph_egraph_series_shape():
    series = plot_subpgraph_egraph(_weighted_graph())

    assert len(series) == 1
    assert series[0]["type"] == "graph"
    assert {node["name"] for node in series[0]["data"]} == {"a", "b", "c", "d"}
    assert len(series[0]["links"]) == 4
    assert series[0]["roam"] == "scale"
    assert series[0]["lineStyle"]["width"] == 8
    assert all(">" in link["name"] for link in series[0]["links"])


def test_eplot_defaults_favor_edge_clicks():
    assert ePlotDefaultOptions["roam"] == "scale"
    assert ePlotDefaultOptions["lineStyle"]["width"] >= 8
    assert "source" in _NETWORK_CLICK_JS
    assert "target" in _NETWORK_CLICK_JS
    assert "dataType" in _NETWORK_CLICK_JS


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


def test_mygraph_create_egraph_and_weights_without_graph(my_graph):
    assert my_graph.create_Egraph() is None
    assert my_graph.get_graph_weights() is None


def test_mygraph_create_egraph_and_weights_with_graph(my_graph):
    my_graph.graph = _weighted_graph()

    series = my_graph.create_Egraph(num_top=2)
    weights = my_graph.get_graph_weights()

    assert series is not None
    assert len(series[0]["links"]) == 2
    assert np.allclose(weights, [5.0, 3.0, 1.0, 0.5])
    assert my_graph.cut_graph.number_of_edges() == 2


@pytest.mark.asyncio
async def test_mygraph_getters_require_graph_and_membership(my_graph):
    assert await my_graph.get_user_tvec("alice") is None
    assert await my_graph.get_user_content("alice") is None

    my_graph.graph = _weighted_graph()
    my_graph.current_set = (0, 0, 60, 2)
    assert await my_graph.get_user_tvec("missing") is None
    assert await my_graph.get_user_content("missing") is None
