"""Session graph state and weight-based graph cutting."""

from multiprocessing import Manager

import networkx as nx
import numpy as np
from nicegui import run, ui

from app.time_analysis import (
    METHODS,
    get_user_content,
    get_user_tvec,
)
from modules.chart_utils import plot_subpgraph_egraph
from modules.timeseries_gui_config import DATASETS


def cut_graph_by_weight(G, num_top):
    weights = np.array([wt for u, v, wt in G.edges.data("norm_weight")])
    thresh = np.sort(weights)[-num_top] if num_top <= len(weights) else 0
    # thresh = np.quantile(weights, quantile)
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

    async def create_graph(self, method_num, dataset_num, t_step=300, win_size=2):
        method = METHODS[method_num]
        dataset = DATASETS[dataset_num]

        self.graph = await run.cpu_bound(
            method, dataset, self.managed_progress_value, win_size, t_step
        )
        self.current_set = (method_num, dataset_num, t_step, win_size)

    def create_Egraph(self, num_top=20):
        if self.graph is None:
            return None
        self.cut_graph = cut_graph_by_weight(self.graph, num_top)
        return plot_subpgraph_egraph(self.cut_graph)

    def get_graph_weights(self):
        if self.graph is None:
            return None
        return np.sort(
            np.array([wt for u, v, wt in self.graph.edges.data("norm_weight")])
        )[::-1]

    async def get_user_tvec(self, user):
        if self.graph is None:
            return None
        if user not in self.graph:
            ui.notify(f"User {user} not found in the graph.")
            return None
        dataset = DATASETS[self.current_set[1]]
        return await run.io_bound(
            get_user_tvec,
            user,
            dataset[0],
            dataset[1],
            dataset[2],
            dataset[3],
            60,
        )

    async def get_user_content(self, user):
        if self.graph is None:
            return None
        if user not in self.graph:
            ui.notify(f"User {user} not found in the graph.")
            return None
        dataset = DATASETS[self.current_set[1]]
        return await run.io_bound(
            get_user_content,
            user,
            dataset[0],
            dataset[1],
            dataset[2],
            dataset[3],
        )
