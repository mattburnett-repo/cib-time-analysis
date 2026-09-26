from __future__ import annotations

from typing import NamedTuple

# DATASETS: path + column names for each supported CSV.


class DatasetSpec(NamedTuple):
    csv_name: str
    time_col_name: str
    user_col_name: str
    content_col_name: str


DATASETS: list[DatasetSpec] = [
    DatasetSpec(
        "csv_data/data/bsky_vax_2024.csv",
        "createdAt",
        "authorProfile.handle",
        "text",
    ),
    DatasetSpec(
        "csv_data/data/truth_vax_2024-2025.csv",
        "created_at",
        "account.username",
        "content_cleaned",
    ),
    DatasetSpec(
        "csv_data/24010 Confirmed Russia Troll Tweets/toprowsremoved - confirmed_russia_troll_tweets.csv",
        "Date tweet sent",
        "Twitter screenname",
        "Tweet text",
    ),
]

DATASET_OPTIONS = {
    0: "Bluesky Vax",
    1: "Truth Social Vax",
    2: "Twitter Russia",
}

DATASET_HELP = {
    0: "Bluesky vaccination discussion posts (smallest dataset — fastest to build).",
    1: "Truth Social vaccination discussion posts (large dataset — slower to build).",
    2: "Confirmed Russia-linked troll tweets (large dataset — slower to build).",
}

METHOD_OPTIONS = {
    0: "Sliding Window",
    1: "Action Driven Overlapping Window",
    2: "Time Overlap",
    3: "Dynamic Time Warping",
}

METHOD_HELP = {
    0: "Compare activity in fixed time windows that slide across the timeline. Usually the fastest method.",
    1: "ADO: windows are centered on each user's posts, then overlaps with other users are scored.",
    2: "Score user pairs by how much their active posting periods overlap after smoothing.",
    3: "DTW: align posting-time patterns even if they are shifted or stretched. Often the slowest method.",
}

# NiceGUI stepper values — must match ui.step(...) labels.
STEP_CONFIGURE = "Configure"
STEP_BUILD = "Build graph"
STEP_WEIGHTS = "Weight distribution"
STEP_EXPLORE = "Explore network"
STEP_INSPECT = "Compare users"

# Delay before rebuilding charts so the stepper panel has a real layout size.
STEP_SYNC_DELAY = 0.15

TOOLTIP_CSS = """
.q-tooltip {
    font-size: 1rem !important;
    line-height: 1.45 !important;
    max-width: 28rem;
    padding: 0.55rem 0.8rem !important;
}
"""

APP_TITLE = "CIBMT Time Analysis"
