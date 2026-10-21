"""Posting-time similarity graphs.

Action Driven Overlapping Window walks posts in time order. Each window is a
slice that only moves forward, and a count of who is inside that slice is
updated as posts enter and leave. That replaces a full-table scan per post.

Time Overlap builds one timeline per account above the minimum post count.
The timeline is binned at the configured time step: a bin is how many distinct
seconds in that step had a post, the same result as ``get_tvec`` after it
coarsens a per-second vector. Pair scores are one matrix product of those
timelines after the same moving sum as ``np.convolve(..., mode="same")``.
"""

import time
from collections.abc import Sequence
from contextlib import contextmanager

import networkx as nx
import numpy as np
import pandas as pd
from dateutil import parser

from modules.timeseries_gui_config import PHASE_BUILDING, DatasetSpec

DEFAULT_MIN_POSTS = 20
MIN_OVERLAP = 1e-5
PROGRESS_EVERY_N_POSTS = 100
PROGRESS_EVERY_N_USERS = 10
READ_PROGRESS_EVERY = 2000


def read_csv(csv_name, time_col_name, user_col_name, content_col_name, progress=None):
    csv_df = pd.read_csv(csv_name)
    csv_df = csv_df.dropna(subset=[user_col_name, time_col_name, content_col_name])
    time_data = []
    n_rows = len(csv_df)

    for i, row in enumerate(csv_df[time_col_name]):
        # use dateutil parser to convert date string into utc timestamp
        timestamp = time.mktime(parser.parse(row).timetuple())
        time_data.append(timestamp)
        if (
            progress is not None
            and n_rows
            and (i % READ_PROGRESS_EVERY == 0 or i + 1 == n_rows)
        ):
            progress.value = (i + 1) / n_rows
    time_data = np.array(time_data)

    # create a column with seconds relative to first post in the file
    csv_df["rel_timestamp"] = time_data - np.min(time_data)

    csv_df = csv_df.sort_values("rel_timestamp")
    return csv_df, time_data


def _as_dataset(data_set: DatasetSpec | Sequence[str]) -> DatasetSpec:
    if isinstance(data_set, DatasetSpec):
        return data_set
    return DatasetSpec(*data_set)


def _load_dataset(data_set: DatasetSpec | Sequence[str], progress=None, phase=None):
    """Normalize dataset config and load the CSV once for an analysis method."""
    dataset = _as_dataset(data_set)
    csv_df, time_data = read_csv(*dataset, progress=progress)
    if phase is not None:
        phase.value = PHASE_BUILDING
        if progress is not None:
            progress.value = 0.0
    return dataset, csv_df, time_data


@contextmanager
def _timed():
    start_time = time.time()
    yield
    print(f"Time taken: {time.time() - start_time:.2f} seconds")


def ado_window(data_set, managed_progress_value, win_size=2, t_step=60, phase=None):
    """Score each post against the other accounts active in the following window.

    ``left`` and ``right`` index the sorted posts. ``in_window`` holds how many
    posts each account has between those indexes. Edge weight is that count;
    norm_weight divides it by the number of posts in the slice.
    """
    dataset, csv_df, _time_data = _load_dataset(data_set, managed_progress_value, phase)
    user_col_name = dataset.user_col_name
    A = nx.Graph()
    dt = int(win_size * t_step)
    # Posts are sorted by time. Each window is a slice that only moves forward.
    times = csv_df["rel_timestamp"].to_numpy()
    users = csv_df[user_col_name].to_numpy()
    n_posts = len(times)
    in_window: dict = {}
    left = 0
    right = 0

    with _timed():
        for ipost in range(n_posts):
            if ipost % PROGRESS_EVERY_N_POSTS == 0:
                print(f"Processing post {ipost+1}/{n_posts}")
                managed_progress_value.value = (ipost + 1) / n_posts

            post_time = times[ipost]
            stop = post_time + dt
            while right < n_posts and times[right] <= stop:
                arriving = users[right]
                in_window[arriving] = in_window.get(arriving, 0) + 1
                right += 1
            while left < ipost and times[left] < post_time:
                leaving = users[left]
                in_window[leaving] -= 1
                if in_window[leaving] == 0:
                    del in_window[leaving]
                left += 1

            num_posts = right - left
            user = users[ipost]
            for other_user, w in in_window.items():
                if other_user == user:
                    continue
                if A.get_edge_data(user, other_user) is None:
                    A.add_edge(user, other_user, weight=w, norm_weight=w / num_posts)
                else:
                    A[user][other_user]["weight"] += w
                    A[user][other_user]["norm_weight"] += w / num_posts

    return A


def sliding_window(data_set, managed_progress_value, win_size=2, t_step=60, phase=None):
    dataset, csv_df, _time_data = _load_dataset(data_set, managed_progress_value, phase)
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
    """Activity vector for one account.

    Marks each second that has a post, then sums those marks into bins of
    ``t_step`` seconds. ``time_overlap`` matches this binning in
    ``_activity_matrix`` and does not build this per-second vector per account.
    """
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


def _moving_sum_same(values: np.ndarray, window: int) -> np.ndarray:
    """Match np.convolve(row, np.ones(window), mode='same') along the last axis."""
    values = np.asarray(values, dtype=float)
    if window <= 1:
        return values.copy()
    n_bins = values.shape[-1]
    cumulative = np.empty(values.shape[:-1] + (n_bins + 1,), dtype=float)
    cumulative[..., 0] = 0.0
    np.cumsum(values, axis=-1, out=cumulative[..., 1:])
    offset = (window - 1) // 2
    index = np.arange(n_bins)
    right = np.clip(index + offset + 1, 0, n_bins)
    left = np.clip(index + offset + 1 - window, 0, n_bins)
    return cumulative[..., right] - cumulative[..., left]


def _activity_matrix(df, user_col_name, t_step, min_posts):
    """Binned timelines for accounts with more than min_posts posts.

    Counts posts once, then builds a vector only for accounts that will become
    nodes. Each bin is ``t_step`` seconds and counts distinct seconds with a
    post, matching ``get_tvec`` after coarsening.
    """
    if df.empty:
        return [], np.empty((0, 0)), np.empty(0)
    step = max(1, int(t_step))
    t_end = int(np.max(df["rel_timestamp"])) + 1
    n_bins = t_end if step == 1 else int(np.ceil(t_end / step))
    counts = df.groupby(user_col_name, sort=True).size()
    kept = counts[counts > min_posts]
    grouped = df.groupby(user_col_name, sort=True)["rel_timestamp"]
    names = []
    rows = []
    posts = []
    for user, num_posts in kept.items():
        seconds = np.unique(grouped.get_group(user).to_numpy(dtype=int))
        if step == 1:
            timeline = np.zeros(n_bins)
            timeline[seconds] = 1.0
        else:
            timeline = np.bincount(seconds // step, minlength=n_bins).astype(float)
        names.append(user)
        rows.append(timeline)
        posts.append(float(num_posts))
    if not rows:
        return [], np.empty((0, n_bins)), np.empty(0)
    return names, np.vstack(rows), np.asarray(posts, dtype=float)


def time_overlap(
    data_set,
    managed_progress_value,
    win_size=2,
    t_step=60,
    min_posts=DEFAULT_MIN_POSTS,
    phase=None,
):
    """Connect accounts whose binned activity overlaps.

    Uses ``_activity_matrix`` for the timelines. Each batch of accounts is
    smoothed with ``_moving_sum_same`` and multiplied by every timeline.
    Weight and norm_weight are that score when it exceeds ``MIN_OVERLAP``.
    """
    dataset, csv_df, _time_data = _load_dataset(data_set, managed_progress_value, phase)
    user_col_name = dataset.user_col_name
    dt = int(win_size * t_step)
    H = nx.Graph()
    names, timelines, num_posts = _activity_matrix(
        csv_df, user_col_name, t_step, min_posts
    )
    if not names:
        managed_progress_value.value = 1.0
        return H
    H.add_nodes_from(names)

    n_users = len(names)
    chunk = 64
    with _timed():
        for start in range(0, n_users, chunk):
            stop = min(start + chunk, n_users)
            print(f"Processing user {start}/{n_users}")
            smoothed = num_posts[start:stop, None] * _moving_sum_same(
                timelines[start:stop], dt
            )
            scores = smoothed @ timelines.T
            for local, i in enumerate(range(start, stop)):
                for j in range(i + 1, n_users):
                    overlap = float(scores[local, j])
                    if overlap > MIN_OVERLAP:
                        H.add_edge(
                            names[i],
                            names[j],
                            weight=overlap,
                            norm_weight=overlap,
                        )
            managed_progress_value.value = stop / n_users

    return H


METHODS = [
    sliding_window,
    ado_window,
    time_overlap,
]
