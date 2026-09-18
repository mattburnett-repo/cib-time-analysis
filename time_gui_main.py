from multiprocessing import Manager

import networkx as nx
import numpy as np
from nicegui import run, ui

import time_analysis

# DATASETS contains tuples of (csv_name, time_col_name, user_col_name, content_col_name) for each dataset.
DATASETS = [
    (
        "csv_data/data/truth_vax_2024-2025.csv",
        "created_at",
        "account.username",
        "content_cleaned",
    ),
    (
        "csv_data/24010 Confirmed Russia Troll Tweets/toprowsremoved - confirmed_russia_troll_tweets.csv",
        "Date tweet sent",
        "Twitter screenname",
        "Tweet text",
    ),
    ("csv_data/data/bsky_vax_2024.csv", "createdAt", "authorProfile.handle", "text"),
]

METHODS = [
    time_analysis.sliding_window,
    time_analysis.ado_window,
    time_analysis.time_overlap,
    time_analysis.dynamic_time_window,
]

ePlotDefaultOptions = {
    "type": "graph",
    "layout": "force",
    "symbolSize": 20,
    "roam": True,
    "label": {"show": True, "position": "right", "formatter": "{b}"},
    "lineStyle": {"opacity": 0.9, "width": 2, "curveness": 0.3},
    "force": {
        # 'initLayout': 'circular',
        # 'gravity': 0,
        "repulsion": 100,
        # 'edgeLength': 200
    },
    "emphasis": {"focus": "adjacency", "lineStyle": {"width": 10}},
}


def plot_subpgraph_egraph(G: nx.Graph):
    nodes = list(G.nodes())
    data = [{"name": node} for node in nodes]
    links = [{"source": edge[0], "target": edge[1]} for edge in G.edges()]
    series = [dict(ePlotDefaultOptions, data=data, links=links)]
    return series


class MyGraph:

    def __init__(self):
        self.graph = None
        self.current_set = None
        self.cut_graph = None
        self.saved_graphs = {}
        self.managed_progress_value = Manager().Value("d", 0.0)
        pass

    async def create_graph(self, method_num, dataset_num, t_step=60, win_size=2):
        if (
            method_num,
            dataset_num,
            t_step,
            win_size,
        ) in self.saved_graphs and self.saved_graphs[
            (method_num, dataset_num, t_step, win_size)
        ] is not None:
            self.graph = self.saved_graphs[(method_num, dataset_num, t_step, win_size)]
            self.current_set = (method_num, dataset_num, t_step, win_size)
            return
        method = METHODS[method_num]
        dataset = DATASETS[dataset_num]

        self.graph = await run.cpu_bound(
            method, dataset, self.managed_progress_value, win_size, t_step
        )
        self.current_set = (method_num, dataset_num, t_step, win_size)
        self.saved_graphs[(method_num, dataset_num, t_step, win_size)] = self.graph

    def create_Egraph(self, num_top=20):
        if self.graph is None:
            return None
        self.cut_graph = cut_graph_by_weight(self.graph, num_top)
        return plot_subpgraph_egraph(self.cut_graph)

    # def create_plotly(self, num_top=20):
    #     if self.graph is None:
    #         return None
    #     self.cut_graph = cut_graph_by_weight(self.graph, num_top)
    #     return plot_subgraph_plotly(self.cut_graph)

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
        return time_analysis.get_user_tvec(
            user,
            DATASETS[self.current_set[1]][0],
            DATASETS[self.current_set[1]][1],
            DATASETS[self.current_set[1]][2],
            DATASETS[self.current_set[1]][3],
            t_step=60,
        )

    async def get_user_content(self, user):
        if self.graph is None:
            return None
        if user not in self.graph:
            ui.notify(f"User {user} not found in the graph.")
            return None
        return time_analysis.get_user_content(
            user,
            DATASETS[self.current_set[1]][0],
            DATASETS[self.current_set[1]][1],
            DATASETS[self.current_set[1]][2],
            DATASETS[self.current_set[1]][3],
        )


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


# select which files
# select type of analysis
# network plot, plot of weights
#   select plot characteristics?
#   edge width proportional to weight
#   which weight to use for graph plot
# select an edge, show time characteristics
# select a node, show user stats (avg num posts per day, number of edges, etc.)
@ui.page("/")
def main_page():
    graph = MyGraph()
    print("starting ui")
    ui.label("Hello NiceGUI!, This is time analysis")
    ui.label("Select data source")
    toggle_data = ui.toggle(
        {0: "Truth Social Vax", 1: "Twitter Russia", 2: "Bluesky Vax"}, value=0
    )
    ui.label("Select analysis type")
    toggle_analysis = ui.toggle(
        {
            0: "Sliding Window",
            1: "Action Driven Overlapping Window",
            2: "Time Overlap",
            3: "Dynamic Time Warping",
        },
        value=0,
    )
    with ui.row():
        ui.label("Step Size (seconds)")
        step_size = ui.number(value=60, precision=0, step=1, min=1, max=1440)
        ui.label("Window Size (number of steps)")
        win_size = ui.number(value=2, precision=0, step=1, min=1, max=1440)
    button = ui.button("Create Graph", on_click=lambda e: handle_click())
    ui.label("progress bar")
    progress = ui.linear_progress(value=0).props("instant-feedback")
    progress.visible = False
    ui.timer(
        0.1, callback=lambda: progress.set_value(graph.managed_progress_value.value)
    )

    ui.label("Weight Statistics")
    echart_weight_stats = ui.echart({"series": []})

    ui.label("Network Graph (click on an edge to see user time comparison)")
    echart_net = ui.echart({"series": []}, on_click=lambda e: on_plot_click(e))
    # plot = ui.plotly(go.Figure())
    ui.label("Select number of top edges to display")
    slider = (
        ui.slider(min=10, max=100, value=10)
        .props("label-always")
        .on(
            "update:model-value",
            lambda e: handle_slider(e.args),
            throttle=1.0,
            leading_events=False,
        )
    )
    # ui.label().bind_text_from(slider, 'value')
    ui.label("Time Comparison of Selected Edge")
    echart_time_compare = ui.echart({"series": []})
    slider.disable()
    scroll_container = ui.scroll_area()

    async def on_plot_click(e):
        if ">" in e.name:
            scroll_container.clear()
            ui.notify(f"Clicked on edge: {e.name}")
            echart_time_compare.run_chart_method("showLoading")
            echart_time_compare.update()
            user0 = e.name.split(" > ")[0].strip()
            user1 = e.name.split(" > ")[1].strip()
            tvec0, num_posts0 = await graph.get_user_tvec(user0)
            tvec1, num_posts1 = await graph.get_user_tvec(user1)
            echart_time_compare.run_chart_method("hideLoading")
            ui.notify(
                f"User {user0} has {num_posts0} posts, User {user1} has {num_posts1} posts"
            )

            series = [
                {"name": f"{user0}", "type": "line", "data": tvec0.tolist()},
                {"name": f"{user1}", "type": "line", "data": tvec1.tolist()},
            ]
            echart_time_compare.options["series"] = series
            echart_time_compare.options["legend"] = {"data": [f"{user0}", f"{user1}"]}
            echart_time_compare.options["xAxis"] = {
                "type": "category",
                "data": list(range(len(tvec0))),
            }
            echart_time_compare.options["yAxis"] = {"type": "value"}
            echart_time_compare.options["tooltip"] = {"trigger": "axis"}
            echart_time_compare.options["grid"] = {"containLabel": True}
            echart_time_compare.options["animation"] = True
            echart_time_compare.options["title"] = {
                "text": f"Comparison of {user0} and {user1}"
            }
            echart_time_compare.update()
            ui.notify(f"Plotted comparison of {user0} and {user1}")
            # get user contents
            contents0, time0 = await graph.get_user_content(user0)
            contents1, time1 = await graph.get_user_content(user1)
            user_and_contets = [(user0, c, t) for c, t in zip(contents0, time0)]
            user_and_contets += [(user1, c, t) for c, t in zip(contents1, time1)]

            user_and_contets.sort(key=lambda x: x[2])
            with scroll_container:
                for user, content, time in user_and_contets:
                    ui.chat_message(content, name=user, stamp=time, sent=user == user0)
            # sort by time

    async def handle_click():
        button.disable()
        progress.visible = True
        print("Button clicked!")
        ui.notify("Creating graph...")
        await graph.create_graph(
            toggle_analysis.value, toggle_data.value, step_size.value, win_size.value
        )
        progress.visible = False
        series = graph.create_Egraph(slider.value)
        echart_net.options["series"] = series

        wts = graph.get_graph_weights()
        hist, edges = np.histogram(np.log1p(wts), bins=50)

        echart_weight_stats.options["series"] = [
            {"name": "Weights", "type": "bar", "data": hist.tolist()}
        ]
        echart_weight_stats.options["xAxis"] = {
            "type": "category",
            "data": edges[:-1].tolist(),
        }
        echart_weight_stats.options["yAxis"] = {"type": "log"}
        echart_weight_stats.options["tooltip"] = {"trigger": "axis"}
        echart_weight_stats.options["grid"] = {"containLabel": True}
        echart_weight_stats.options["animation"] = True
        echart_weight_stats.options["title"] = {
            "text": "Log Histogram of Graph Weights"
        }
        echart_weight_stats.update()
        slider.enable()
        button.enable()

    async def handle_slider(value):
        print(f"Slider value changed to {value}")
        series = graph.create_Egraph(value)
        echart_net.options["series"] = series
        echart_net.update()


ui.run()
