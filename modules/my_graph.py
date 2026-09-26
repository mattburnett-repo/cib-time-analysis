"""Session graph state and weight-based graph cutting."""

from multiprocessing import Manager

import networkx as nx
import numpy as np
from nicegui import run, ui

from app.time_analysis import (
    METHODS,
    content_for_user,
    get_tvec,
    read_csv,
)
from modules.chart_utils import plot_subgraph_echart
from modules.timeseries_gui_config import DATASETS


def cut_graph_by_weight(G, num_top):
    weights = np.array([wt for u, v, wt in G.edges.data("norm_weight")])
    thresh = np.sort(weights)[-num_top] if num_top <= len(weights) else 0
    Hcut = nx.Graph(G)
    for u, v, wt in list(Hcut.edges.data("norm_weight")):
        if wt < thresh:
            Hcut.remove_edge(u, v)

    for node in list(Hcut.nodes):
        if Hcut.degree[node] < 1:
            Hcut.remove_node(node)

    return Hcut


class MyGraph:

    def __init__(self):
        self.graph = None
        self.current_set = None
        self.cut_graph = None
        self.managed_progress_value = Manager().Value("d", 0.0)
        # Cached (DatasetSpec, DataFrame) for Compare; invalidated on rebuild.
        self._csv_cache = None

    async def create_graph(self, method_num, dataset_num, t_step=300, win_size=2):
        method = METHODS[method_num]
        dataset = DATASETS[dataset_num]
        self._csv_cache = None

        self.graph = await run.cpu_bound(
            method, dataset, self.managed_progress_value, win_size, t_step
        )
        self.current_set = (method_num, dataset_num, t_step, win_size)

    def create_egraph(self, num_top=20):
        if self.graph is None:
            return None
        self.cut_graph = cut_graph_by_weight(self.graph, num_top)
        return plot_subgraph_echart(self.cut_graph)

    def get_graph_weights(self):
        if self.graph is None:
            return None
        return np.sort(
            np.array([wt for u, v, wt in self.graph.edges.data("norm_weight")])
        )[::-1]

    async def _ensure_csv(self):
        """Load the active dataset CSV once per build; reuse for Compare queries."""
        if self._csv_cache is not None:
            return self._csv_cache
        dataset = DATASETS[self.current_set[1]]
        csv_df, _time_data = await run.io_bound(read_csv, *dataset)
        self._csv_cache = (dataset, csv_df)
        return self._csv_cache

    def _require_user(self, user):
        if self.graph is None:
            return False
        if user not in self.graph:
            ui.notify(f"User {user} not found in the graph.")
            return False
        return True

    async def get_user_tvec(self, user):
        if not self._require_user(user):
            return None
        dataset, csv_df = await self._ensure_csv()
        t_step = int(self.current_set[2])
        return await run.io_bound(get_tvec, user, csv_df, dataset.user_col_name, t_step)

    async def get_user_content(self, user):
        if not self._require_user(user):
            return None
        dataset, csv_df = await self._ensure_csv()
        return await run.io_bound(
            content_for_user,
            user,
            csv_df,
            dataset.user_col_name,
            dataset.content_col_name,
            dataset.time_col_name,
        )
