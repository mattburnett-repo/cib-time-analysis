"""ECharts network plot defaults, click payload helpers, and series builders."""

import networkx as nx

ePlotDefaultOptions = {
    "type": "graph",
    "layout": "force",
    "symbolSize": 28,
    "roam": "scale",  # zoom only — pan/drag was swallowing edge clicks
    "label": {"show": True, "position": "right", "formatter": "{b}"},
    "edgeLabel": {"show": False},
    "lineStyle": {"opacity": 0.9, "width": 8, "curveness": 0.2},
    "edgeSymbol": ["none", "none"],
    "force": {
        "repulsion": 140,
        "edgeLength": [60, 160],
    },
    "emphasis": {"focus": "adjacency", "lineStyle": {"width": 14}},
}

# Browser-side handler for ECharts graph clicks (passed to NiceGUI's js_handler).
# The raw chart:click payload is huge and not JSON-serializable to Python, so this
# strips it down and emit()s only what we need: edge source/target or node name.
_NETWORK_CLICK_JS = """
(evt) => {
    if (!evt || evt.componentType !== 'series') return;
    if (evt.dataType === 'edge') {
        const d = evt.data || {};
        emit({
            dataType: 'edge',
            name: evt.name || '',
            source: d.source,
            target: d.target,
        });
    } else if (evt.dataType === 'node') {
        emit({ dataType: 'node', name: evt.name || '' });
    }
}
"""


def resolve_node_ref(ref, nodes: list | None = None) -> str | None:
    """Map an ECharts node id/index to a username string."""
    if ref is None:
        return None
    if isinstance(ref, str):
        return ref
    if isinstance(ref, int):
        if nodes is not None and 0 <= ref < len(nodes):
            return str(nodes[ref])
        return None
    return str(ref)


def users_from_edge_payload(args, nodes: list | None = None) -> tuple[str, str] | None:
    """Parse a network chart click payload into (user0, user1)."""
    if isinstance(args, list) and args:
        args = args[0]
    if not isinstance(args, dict):
        return None

    data_type = args.get("dataType")
    name = args.get("name") or ""

    if data_type == "edge":
        source = resolve_node_ref(args.get("source"), nodes)
        target = resolve_node_ref(args.get("target"), nodes)
        data = args.get("data")
        if (source is None or target is None) and isinstance(data, dict):
            source = source or resolve_node_ref(data.get("source"), nodes)
            target = target or resolve_node_ref(data.get("target"), nodes)
        if source is not None and target is not None:
            return source, target

    if isinstance(name, str) and ">" in name:
        left, right = name.split(">", 1)
        return left.strip(), right.strip()
    return None


def plot_subpgraph_egraph(G: nx.Graph):
    nodes = list(G.nodes())
    data = [{"name": node, "id": node, "value": 1} for node in nodes]
    links = []
    for edge in G.edges():
        weight = G.edges[edge].get("norm_weight", 1.0)
        links.append(
            {
                "source": edge[0],
                "target": edge[1],
                "name": f"{edge[0]} > {edge[1]}",
                "value": float(weight),
            }
        )
    series = [dict(ePlotDefaultOptions, data=data, links=links)]
    return series
