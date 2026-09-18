import time

import networkx as nx
import numpy as np
import pandas as pd
from dateutil import parser
from dtw import dtw


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


def ado_window(data_set, managed_progress_value, win_size=2, t_step=60):
    csv_name = data_set[0]
    time_col_name = data_set[1]
    user_col_name = data_set[2]
    content_col_name = data_set[3]
    csv_df, time_data = read_csv(
        csv_name, time_col_name, user_col_name, content_col_name
    )
    A = nx.Graph()

    dt = int(win_size * t_step)  # window size in seconds

    start_time = time.time()

    for ipost in range(len(csv_df["rel_timestamp"])):
        if ipost % 100 == 0:
            print(f"Processing post {ipost+1}/{len(csv_df['rel_timestamp'])}")
            managed_progress_value.value = (ipost + 1) / len(csv_df["rel_timestamp"])

        post_time = csv_df["rel_timestamp"].iloc[ipost]
        user = csv_df[user_col_name].iloc[ipost]

        stop = post_time + dt

        data = csv_df[
            (csv_df["rel_timestamp"] >= post_time) & (csv_df["rel_timestamp"] <= stop)
        ]

        num_posts = data.shape[0]

        win_users = np.unique(data[user_col_name])

        for ii in range(len(win_users)):
            other_user = win_users[ii]
            if other_user == user:
                continue
            w = len(data[data[user_col_name] == other_user])
            if A.get_edge_data(user, other_user) is None:
                A.add_edge(user, other_user, weight=w, norm_weight=w / num_posts)
            else:
                A[user][other_user]["weight"] += w
                A[user][other_user]["norm_weight"] += w / num_posts

    end_time = time.time()
    print(f"Time taken: {end_time - start_time:.2f} seconds")
    return A


def sliding_window(data_set, managed_progress_value, win_size=2, t_step=60):
    csv_name = data_set[0]
    time_col_name = data_set[1]
    user_col_name = data_set[2]
    content_col_name = data_set[3]
    csv_df, time_data = read_csv(
        csv_name, time_col_name, user_col_name, content_col_name
    )

    # sliding algorithm, make groups through sliding windows
    # time window in seconds
    # using networkx to create and visulaize graphs

    G = nx.Graph()
    # t_step = 60 # step size in seconds

    # dt = 2 * t_step # window size in seconds
    dt = int(win_size * t_step)  # window size in seconds
    last_step = int((csv_df["rel_timestamp"].max()) / t_step) + 1

    start_time = time.time()

    for iwin in range(last_step):

        if iwin % 100 == 0:
            # print(f"Processing window {iwin+1}/{last_step}")
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

    end_time = time.time()
    print(f"Time taken: {end_time - start_time:.2f} seconds")
    return G


def get_user_tvec(
    user, csv_name, time_col_name, user_col_name, content_col_name, t_step=1
):
    csv_df, time_data = read_csv(
        csv_name, time_col_name, user_col_name, content_col_name
    )
    return get_tvec(user, csv_df, user_col_name, t_step)


def get_user_content(user, csv_name, time_col_name, user_col_name, content_col_name):
    csv_df, time_data = read_csv(
        csv_name, time_col_name, user_col_name, content_col_name
    )
    return (
        csv_df[csv_df[user_col_name] == user][content_col_name].to_numpy(),
        csv_df[csv_df[user_col_name] == user][time_col_name].to_numpy(),
    )


def get_tvec(user, df, user_col_name, t_step=1):
    post_times = df[df[user_col_name] == user]["rel_timestamp"].to_numpy(dtype=int)
    num_posts = len(post_times)
    t_end = int(np.max(df["rel_timestamp"])) + 1
    tvec = np.zeros(t_end)
    tvec[post_times] = 1
    # coarsen the signal if necessary (sums over dec_factor time bins(seconds))
    if t_step > 1:
        new_len = int(np.ceil(t_end / t_step) * t_step)
        new_vec = np.zeros(new_len)
        new_vec[: len(tvec)] = tvec
        tvec = np.sum(new_vec.reshape(-1, t_step), axis=1)
    return tvec, num_posts


def time_overlap(data_set, managed_progress_value, win_size=2, t_step=60, min_posts=20):
    # try time series overlap
    # decimate to per minute (factor of 60)
    # dec_factor = 60
    csv_name = data_set[0]
    time_col_name = data_set[1]
    user_col_name = data_set[2]
    content_col_name = data_set[3]
    csv_df, time_data = read_csv(
        csv_name, time_col_name, user_col_name, content_col_name
    )

    # ignore users that don't post much (arbritrary)``
    # min_posts = 20

    # time window in number of time bins (after decimation)
    dt = int(win_size * t_step)
    H = nx.Graph()

    # rectangular window. Also consider triangular or gaussian windows
    win = np.ones(int(dt))

    users = np.unique(csv_df[user_col_name])
    min_overlap = 0.00001

    start_time = time.time()
    # this step calculates the time series vectors ahead of time and adds to the graph.
    # this speeds up the method considerably, however it does use more memory.
    # for users with low memory system, this may not work
    for iuser, user in enumerate(users):
        if iuser % 10 == 0:
            print(f"Processing user {iuser}/{len(users)}")
            managed_progress_value.value = iuser / len(users)
        tvec, nump = get_tvec(user, csv_df, user_col_name, t_step)
        if nump <= min_posts:
            continue
        ### here we normalize based on number of posts. There may be better way to normalize to account for
        ### users who post often
        # tvec = tvec/np.sum(tvec)
        # print(f'sum is {np.sum(tvec)}')
        H.add_node(user, tvec=tvec, num_posts=nump)

    users = list(H.nodes)

    for ii in range(len(users)):

        if ii % 10 == 0:
            print(f"Processing user {ii}/{len(users)}")
            managed_progress_value.value = ii / len(users)
        iuser = users[ii]

        tvec = H.nodes[iuser]["tvec"]
        nump = H.nodes[iuser]["num_posts"]

        win_tvec = nump * np.convolve(tvec, win, mode="same")

        for jj in range(ii + 1, len(users)):
            juser = users[jj]
            tvec = H.nodes[juser]["tvec"]
            overlap = np.dot(win_tvec, tvec)
            if overlap > min_overlap:
                H.add_edge(iuser, juser, weight=overlap, norm_weight=overlap)

    end_time = time.time()
    print(f"Time taken: {end_time - start_time:.2f} seconds")
    return H


def dynamic_time_window(
    data_set, managed_progress_value, win_size=2, t_step=60, min_posts=20
):
    # try time series overlap
    # decimate to per minute (factor of 60)
    # using the dtaidistance package from ref 6
    csv_name = data_set[0]
    time_col_name = data_set[1]
    user_col_name = data_set[2]
    content_col_name = data_set[3]
    csv_df, time_data = read_csv(
        csv_name, time_col_name, user_col_name, content_col_name
    )
    # dec_factor = 60

    # min_posts = 20
    # this method will take forever if we do not use a window to limit the dtw algorithm
    dt = int(win_size * t_step)  # window size in seconds

    D = nx.Graph()
    users = np.unique(csv_df[user_col_name])

    start_time = time.time()
    # this step calculates the time series vectors ahead of time and adds to the graph.
    # this speeds up the method considerably, however it does use more memory.
    # for users with low memory system, this may not work
    for iuser, user in enumerate(users):
        tvec, nump = get_tvec(user, csv_df, user_col_name, t_step)

        if iuser % 10 == 0:
            print(f"Processing user {iuser}/{len(users)}")
            managed_progress_value.value = iuser / len(users)
        if nump <= min_posts:
            continue
        D.add_node(user, tvec=tvec, num_posts=nump)

    users = list(D.nodes)

    for ii in range(len(users)):

        if ii % 10 == 0:
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
                w = 1e-12
            D.add_edge(iuser, juser, norm_weight=1 / w, weight=1 / w)

    end_time = time.time()
    print(f"Time taken: {end_time - start_time:.2f} seconds")
    return D


METHODS = [
    sliding_window,
    ado_window,
    time_overlap,
    dynamic_time_window,
]
