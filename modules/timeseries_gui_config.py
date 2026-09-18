# DATASETS contains tuples of (csv_name, time_col_name, user_col_name, content_col_name)
# for each dataset.
DATASETS = [
    ("csv_data/data/bsky_vax_2024.csv", "createdAt", "authorProfile.handle", "text"),
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
