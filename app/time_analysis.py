import time
from collections.abc import Sequence
from contextlib import contextmanager

import networkx as nx
import numpy as np
import pandas as pd
from dateutil import parser
from dtw import dtw

from modules.timeseries_gui_config import DatasetSpec

DEFAULT_MIN_POSTS = 20
MIN_OVERLAP = 1e-5
DTW_ZERO_DISTANCE = 1e-12
PROGRESS_EVERY_N_POSTS = 100
PROGRESS_EVERY_N_USERS = 10


def read_csv(csv_name, time_col_name, user_col_name, content_col_name):
    csv_df = pd.read_csv(csv_name)
    csv_df = csv_df.dropna(subset=[user_col_name, time_col_name, content_col_name])
    time_data = []

    for row in csv_df[time_col_name]:
        # use dateutil parser to convert date string into utc timestamp
        timestamp = time.mktime(parser.parse(row).timetuple())
        time_data.append(timestamp)
    time_data = np.array(time_data)

    # create a column with seconds relative to first post in the file
    csv_df["rel_timestamp"] = time_data - np.min(time_data)

    csv_df = csv_df.sort_values("rel_timestamp")
    return csv_df, time_data


def _as_dataset(data_set: DatasetSpec | Sequence[str]) -> DatasetSpec:
    if isinstance(data_set, DatasetSpec):
        return data_set
    return DatasetSpec(*data_set)


def _load_dataset(data_set: DatasetSpec | Sequence[str]):
    """Normalize dataset config and load the CSV once for an analysis method."""
    dataset = _as_dataset(data_set)
    csv_df, time_data = read_csv(*dataset)
    return dataset, csv_df, time_data


@contextmanager
def _timed():
    start_time = time.time()
    yield
    print(f"Time taken: {time.time() - start_time:.2f} seconds")


def _precompute_user_nodes(
    graph: nx.Graph,
    csv_df,
    user_col_name: str,
    *,
    t_step: int,
    min_posts: int,
    progress,
) -> list:
    """Add nodes with precomputed tvecs; skip users below min_posts."""
    users = np.unique(csv_df[user_col_name])
    for iuser, user in enumerate(users):
        if iuser % PROGRESS_EVERY_N_USERS == 0:
            print(f"Processing user {iuser}/{len(users)}")
            progress.value = iuser / len(users)
        tvec, nump = get_tvec(user, csv_df, user_col_name, t_step)
        if nump <= min_posts:
            continue
        graph.add_node(user, tvec=tvec, num_posts=nump)
    return list(graph.nodes)


def ado_window(data_set, managed_progress_value, win_size=2, t_step=60):
    dataset, csv_df, _time_data = _load_dataset(data_set)
    user_col_name = dataset.user_col_name
    A = nx.Graph()
    dt = int(win_size * t_step)

    with _timed():
        for ipost in range(len(csv_df["rel_timestamp"])):
            if ipost % PROGRESS_EVERY_N_POSTS == 0:
                print(f"Processing post {ipost+1}/{len(csv_df['rel_timestamp'])}")
                managed_progress_value.value = (ipost + 1) / len(
                    csv_df["rel_timestamp"]
                )

            post_time = csv_df["rel_timestamp"].iloc[ipost]
            user = csv_df[user_col_name].iloc[ipost]
            stop = post_time + dt
            data = csv_df[
                (csv_df["rel_timestamp"] >= post_time)
                & (csv_df["rel_timestamp"] <= stop)
            ]
            num_posts = data.shape[0]
            win_users = np.unique(data[user_col_name])

            for other_user in win_users:
                if other_user == user:
                    continue
                w = len(data[data[user_col_name] == other_user])
                if A.get_edge_data(user, other_user) is None:
                    A.add_edge(user, other_user, weight=w, norm_weight=w / num_posts)
                else:
                    A[user][other_user]["weight"] += w
                    A[user][other_user]["norm_weight"] += w / num_posts

    return A


def sliding_window(data_set, managed_progress_value, win_size=2, t_step=60):
    dataset, csv_df, _time_data = _load_dataset(data_set)
    user_col_name = dataset.user_col_name
    G = nx.Graph()
    dt = int(win_size * t_step)
    last_step = int((csv_df["rel_timestamp"].max()) / t_step) + 1

    with _timed():
        for iwin in range(last_step):
            if iwin % PROGRESS_EVERY_N_POSTS == 0:
                managed_progress_value.value = (iwin + 1) / last_step
            start = iwin * t_step
            stop = start + dt
            data = csv_df[
                (csv_df["rel_timestamp"] >= start) & (csv_df["rel_timestamp"] <= stop)
            ]
            num_posts = data.shape[0]
            win_users = np.unique(data[user_col_name])

            for ii in range(len(win_users)):
                iuser = win_users[ii]
                for jj in range(ii + 1, len(win_users)):
                    juser = win_users[jj]
                    if G.get_edge_data(iuser, juser) is None:
                        G.add_edge(iuser, juser, weight=1, norm_weight=1.0 / num_posts)
                    else:
                        G[iuser][juser]["weight"] += 1
                        G[iuser][juser]["norm_weight"] += 1.0 / num_posts

    return G


def get_user_tvec(
    user, csv_name, time_col_name, user_col_name, content_col_name, t_step=1
):
    csv_df, _time_data = read_csv(
        csv_name, time_col_name, user_col_name, content_col_name
    )
    return get_tvec(user, csv_df, user_col_name, t_step)


def content_for_user(user, df, user_col_name, content_col_name, time_col_name):
    """Extract post text + timestamps for one user from an already-loaded frame."""
    user_rows = df[df[user_col_name] == user]
    return (
        user_rows[content_col_name].to_numpy(),
        user_rows[time_col_name].to_numpy(),
    )


def _mask_within_dt(
    times: np.ndarray, other_times: np.ndarray, dt: float
) -> np.ndarray:
    """True where each time has at least one other_time within dt (inclusive)."""
    if len(times) == 0:
        return np.array([], dtype=bool)
    if len(other_times) == 0:
        return np.zeros(len(times), dtype=bool)

    other = np.sort(other_times.astype(float, copy=False))
    mask = np.zeros(len(times), dtype=bool)
    for i, t in enumerate(times.astype(float, copy=False)):
        j = np.searchsorted(other, t)
        if j < len(other) and other[j] - t <= dt:
            mask[i] = True
        elif j > 0 and t - other[j - 1] <= dt:
            mask[i] = True
    return mask


def overlapping_content_for_users(
    user0,
    user1,
    df,
    user_col_name,
    content_col_name,
    time_col_name,
    dt,
):
    """Posts from either user that fall within dt of at least one post by the other.

    Returns a list of (user, content, display_time) sorted by relative timestamp.
    """
    rows0 = df[df[user_col_name] == user0]
    rows1 = df[df[user_col_name] == user1]
    rel0 = rows0["rel_timestamp"].to_numpy(dtype=float)
    rel1 = rows1["rel_timestamp"].to_numpy(dtype=float)
    mask0 = _mask_within_dt(rel0, rel1, dt)
    mask1 = _mask_within_dt(rel1, rel0, dt)

    items: list[tuple] = []
    for keep, content, stamp, rel in zip(
        mask0,
        rows0[content_col_name].to_numpy(),
        rows0[time_col_name].to_numpy(),
        rel0,
        strict=True,
    ):
        if keep:
            items.append((user0, content, stamp, rel))
    for keep, content, stamp, rel in zip(
        mask1,
        rows1[content_col_name].to_numpy(),
        rows1[time_col_name].to_numpy(),
        rel1,
        strict=True,
    ):
        if keep:
            items.append((user1, content, stamp, rel))

    items.sort(key=lambda row: row[3])
    return [(user, content, stamp) for user, content, stamp, _rel in items]


def get_user_content(user, csv_name, time_col_name, user_col_name, content_col_name):
    csv_df, _time_data = read_csv(
        csv_name, time_col_name, user_col_name, content_col_name
    )
    return content_for_user(
        user, csv_df, user_col_name, content_col_name, time_col_name
    )


def get_tvec(user, df, user_col_name, t_step=1):
    post_times = df[df[user_col_name] == user]["rel_timestamp"].to_numpy(dtype=int)
    num_posts = len(post_times)
    t_end = int(np.max(df["rel_timestamp"])) + 1
    tvec = np.zeros(t_end)
    tvec[post_times] = 1
    # coarsen the signal if necessary (sums over t_step-sized time bins)
    if t_step > 1:
        new_len = int(np.ceil(t_end / t_step) * t_step)
        new_vec = np.zeros(new_len)
        new_vec[: len(tvec)] = tvec
        tvec = np.sum(new_vec.reshape(-1, t_step), axis=1)
    return tvec, num_posts


def time_overlap(
    data_set,
    managed_progress_value,
    win_size=2,
    t_step=60,
    min_posts=DEFAULT_MIN_POSTS,
):
    dataset, csv_df, _time_data = _load_dataset(data_set)
    user_col_name = dataset.user_col_name
    dt = int(win_size * t_step)
    H = nx.Graph()
    win = np.ones(int(dt))

    with _timed():
        users = _precompute_user_nodes(
            H,
            csv_df,
            user_col_name,
            t_step=t_step,
            min_posts=min_posts,
            progress=managed_progress_value,
        )
        for ii in range(len(users)):
            if ii % PROGRESS_EVERY_N_USERS == 0:
                print(f"Processing user {ii}/{len(users)}")
                managed_progress_value.value = ii / len(users)
            iuser = users[ii]
            tvec = H.nodes[iuser]["tvec"]
            nump = H.nodes[iuser]["num_posts"]
            win_tvec = nump * np.convolve(tvec, win, mode="same")

            for jj in range(ii + 1, len(users)):
                juser = users[jj]
                overlap = np.dot(win_tvec, H.nodes[juser]["tvec"])
                if overlap > MIN_OVERLAP:
                    H.add_edge(iuser, juser, weight=overlap, norm_weight=overlap)

    return H


def dynamic_time_window(
    data_set,
    managed_progress_value,
    win_size=2,
    t_step=60,
    min_posts=DEFAULT_MIN_POSTS,
):
    dataset, csv_df, _time_data = _load_dataset(data_set)
    user_col_name = dataset.user_col_name
    # Window limits DTW search; without it this method is impractically slow.
    dt = int(win_size * t_step)
    D = nx.Graph()

    with _timed():
        users = _precompute_user_nodes(
            D,
            csv_df,
            user_col_name,
            t_step=t_step,
            min_posts=min_posts,
            progress=managed_progress_value,
        )
        for ii in range(len(users)):
            if ii % PROGRESS_EVERY_N_USERS == 0:
                print(f"Processing user {ii}/{len(users)}")
                managed_progress_value.value = ii / len(users)
            iuser = users[ii]
            itvec = D.nodes[iuser]["tvec"]

            for jj in range(ii + 1, len(users)):
                juser = users[jj]
                jtvec = D.nodes[juser]["tvec"]
                alignment = dtw(
                    itvec.astype(float),
                    jtvec.astype(float),
                    window_type="sakoechiba",
                    window_args={"window_size": 2 * dt},
                )
                w = alignment.distance
                if w == 0:
                    w = DTW_ZERO_DISTANCE
                D.add_edge(iuser, juser, norm_weight=1 / w, weight=1 / w)

    return D


METHODS = [
    sliding_window,
    ado_window,
    time_overlap,
    dynamic_time_window,
]
