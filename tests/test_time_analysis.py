import networkx as nx
import numpy as np
import pytest

import app.time_analysis as time_analysis
from app.time_analysis import METHODS
from modules.timeseries_gui_config import (
    DATASET_HELP,
    DATASET_OPTIONS,
    DATASETS,
    METHOD_HELP,
    METHOD_OPTIONS,
)


def test_gui_config_keys_align_with_datasets_and_methods():
    assert len(DATASETS) == len(DATASET_OPTIONS) == len(DATASET_HELP)
    assert set(DATASET_OPTIONS) == set(DATASET_HELP) == set(range(len(DATASETS)))
    assert len(METHODS) == len(METHOD_OPTIONS) == len(METHOD_HELP)
    assert set(METHOD_OPTIONS) == set(METHOD_HELP) == set(range(len(METHODS)))
    assert METHODS == [
        time_analysis.sliding_window,
        time_analysis.ado_window,
        time_analysis.time_overlap,
        time_analysis.dynamic_time_window,
    ]


def test_read_csv_adds_relative_timestamps_and_sorts(sample_csv):
    csv_df, time_data = time_analysis.read_csv(*sample_csv)

    assert len(csv_df) == 6
    assert len(time_data) == 6
    assert "rel_timestamp" in csv_df.columns
    assert csv_df["rel_timestamp"].iloc[0] == 0
    assert list(csv_df["rel_timestamp"]) == sorted(csv_df["rel_timestamp"])


def test_read_csv_drops_incomplete_rows(tmp_path):
    path = tmp_path / "sparse.csv"
    path.write_text(
        "\n".join(
            [
                "created_at,account.username,content_cleaned",
                "2024-01-01 00:00:00,alice,ok",
                "2024-01-01 00:00:10,,missing-user",
                "2024-01-01 00:00:20,bob,",
                "",
            ]
        ),
        encoding="utf-8",
    )
    csv_df, _ = time_analysis.read_csv(
        str(path), "created_at", "account.username", "content_cleaned"
    )
    assert len(csv_df) == 1
    assert csv_df["account.username"].iloc[0] == "alice"


def test_get_tvec_marks_post_times():
    import pandas as pd

    df = pd.DataFrame(
        {
            "account.username": ["alice", "bob", "alice"],
            "rel_timestamp": [0, 1, 3],
        }
    )
    tvec, num_posts = time_analysis.get_tvec("alice", df, "account.username", t_step=1)

    assert num_posts == 2
    assert tvec.tolist() == [1, 0, 0, 1]


def test_get_tvec_coarsens_with_step():
    import pandas as pd

    df = pd.DataFrame(
        {
            "account.username": ["alice", "alice", "alice"],
            "rel_timestamp": [0, 1, 2],
        }
    )
    tvec, num_posts = time_analysis.get_tvec("alice", df, "account.username", t_step=2)

    assert num_posts == 3
    assert tvec.tolist() == [2, 1]


def test_get_user_content_and_tvec(sample_csv):
    contents, times = time_analysis.get_user_content("alice", *sample_csv)
    assert list(contents) == ["first", "third"]
    assert len(times) == 2

    tvec, num_posts = time_analysis.get_user_tvec("alice", *sample_csv, t_step=20)
    assert num_posts == 2
    assert isinstance(tvec, np.ndarray)
    assert tvec.sum() == 2


def test_sliding_window_builds_edges(sample_csv, progress):
    graph = time_analysis.sliding_window(sample_csv, progress, win_size=2, t_step=20)

    assert isinstance(graph, nx.Graph)
    assert graph.number_of_nodes() >= 2
    assert graph.number_of_edges() >= 1
    for _, _, data in graph.edges(data=True):
        assert "weight" in data
        assert "norm_weight" in data
        assert data["weight"] > 0
        assert data["norm_weight"] > 0
    assert 0.0 < progress.value <= 1.0


def test_ado_window_builds_edges(sample_csv, progress):
    graph = time_analysis.ado_window(sample_csv, progress, win_size=2, t_step=20)

    assert isinstance(graph, nx.Graph)
    assert graph.number_of_edges() >= 1
    assert progress.value > 0


def test_time_overlap_with_low_min_posts(sample_csv, progress):
    # Wide window so sparse sample posts still produce measurable overlap.
    graph = time_analysis.time_overlap(
        sample_csv, progress, win_size=120, t_step=1, min_posts=1
    )

    assert isinstance(graph, nx.Graph)
    assert set(graph.nodes) == {"alice", "bob", "carol"}
    assert graph.number_of_edges() >= 1


def test_dynamic_time_window_with_low_min_posts(sample_csv, progress):
    graph = time_analysis.dynamic_time_window(
        sample_csv, progress, win_size=2, t_step=1, min_posts=1
    )

    assert isinstance(graph, nx.Graph)
    assert graph.number_of_nodes() == 3
    assert graph.number_of_edges() >= 1
    for _, _, data in graph.edges(data=True):
        assert data["norm_weight"] > 0
