"""Session graph state and weight-based graph cutting.

Build graph ranks the strongest links once, inside the background job, and
stores that list on the graph. Explore network slices the list down to the
slider value. The page thread does not rank or copy the full edge set when
the chart is drawn or the slider moves.
"""

from multiprocessing import Manager

import networkx as nx
from nicegui import run, ui

from app.time_analysis import (
    METHODS,
    content_for_user,
    overlapping_content_for_users,
    read_csv,
)
from modules.chart_utils import plot_subgraph_echart
from modules.timeseries_gui_config import (
    DATASETS,
    EXPLORE_MAX_PAIRS,
    PHASE_IDLE,
    PHASE_RANKING,
    PHASE_READING,
)

# Stored on the graph during Build so Explore can slice links without copying it.
TOP_EDGES_KEY = "top_edges"
RANK_PROGRESS_EVERY = 5000


def ranked_edges(G, limit):
    """Strongest edges first, capped at limit. Does not copy G."""
    ranked = sorted(
        G.edges(data=True),
        key=lambda edge: edge[2].get("norm_weight", 0.0),
        reverse=True,
    )
    return ranked[:limit]


def remember_top_edges(G, limit=EXPLORE_MAX_PAIRS, progress=None):
    """Store the strongest links on ``G`` before Build returns to the page.

    Explore reads this list. Ranking here keeps that work off the page thread.
    """
    total = G.number_of_edges()
    scanned = []
    for i, (u, v, data) in enumerate(G.edges(data=True), start=1):
        scanned.append((data.get("norm_weight", 0.0), u, v, data))
        if progress is not None and total and i % RANK_PROGRESS_EVERY == 0:
            progress.value = i / total
    scanned.sort(key=lambda item: item[0], reverse=True)
    G.graph[TOP_EDGES_KEY] = [(u, v, data) for _weight, u, v, data in scanned[:limit]]
    if progress is not None:
        progress.value = 1.0
    return G


def build_ranked_graph(method, dataset, progress, phase, win_size, t_step):
    """Run one analysis method, then store the links Explore will display.

    ``phase`` moves from reading the file, to building the graph, to ranking
    links. The page timer uses that to drive the three progress bars.
    """
    phase.value = PHASE_READING
    progress.value = 0.0
    graph = method(dataset, progress, win_size, t_step, phase=phase)
    phase.value = PHASE_RANKING
    progress.value = 0.0
    return remember_top_edges(graph, progress=progress)


def cut_graph_by_weight(G, num_top):
    """Build a small graph of the strongest ``num_top`` links.

    Slices the list ``remember_top_edges`` stored during Build. Graphs from
    tests have no list, so those are ranked here.
    """
    ranked = G.graph.get(TOP_EDGES_KEY)
    chosen = ranked[:num_top] if ranked is not None else ranked_edges(G, num_top)
    cut = nx.Graph()
    for u, v, data in chosen:
        cut.add_edge(u, v, **data)
    return cut


class MyGraph:

    def __init__(self):
        self.graph = None
        self.current_set = None
        self.cut_graph = None
        self.managed_progress_value = Manager().Value("d", 0.0)
        self.build_phase = Manager().Value("i", PHASE_IDLE)
        # Cached (DatasetSpec, DataFrame) for Compare; invalidated on rebuild.
        self._csv_cache = None

    async def create_graph(self, method_num, dataset_num, t_step=300, win_size=2):
        method = METHODS[method_num]
        dataset = DATASETS[dataset_num]
        self._csv_cache = None

        self.build_phase.value = PHASE_READING
        self.managed_progress_value.value = 0.0
        self.graph = await run.cpu_bound(
            build_ranked_graph,
            method,
            dataset,
            self.managed_progress_value,
            self.build_phase,
            win_size,
            t_step,
        )
        self.build_phase.value = PHASE_IDLE
        self.current_set = (method_num, dataset_num, t_step, win_size)

    def create_egraph(self, num_top=20):
        if self.graph is None:
            return None
        self.cut_graph = cut_graph_by_weight(self.graph, num_top)
        return plot_subgraph_echart(self.cut_graph)

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

    async def get_overlapping_content(self, user0, user1):
        """Posts from either user within the configured analysis window of the other."""
        if not self._require_user(user0) or not self._require_user(user1):
            return None
        if self.current_set is None:
            return None
        dataset, csv_df = await self._ensure_csv()
        t_step = int(self.current_set[2])
        win_size = int(self.current_set[3])
        dt = int(win_size * t_step)
        return await run.io_bound(
            overlapping_content_for_users,
            user0,
            user1,
            csv_df,
            dataset.user_col_name,
            dataset.content_col_name,
            dataset.time_col_name,
            dt,
        )
