from types import SimpleNamespace

import pytest


@pytest.fixture
def progress():
    """Stand-in for multiprocessing.Manager().Value used by analysis methods."""
    return SimpleNamespace(value=0.0)


@pytest.fixture
def sample_csv(tmp_path):
    """Tiny CSV with three users posting close together in time."""
    path = tmp_path / "sample.csv"
    path.write_text(
        "\n".join(
            [
                "created_at,account.username,content_cleaned",
                "2024-01-01 00:00:00,alice,first",
                "2024-01-01 00:00:20,bob,second",
                "2024-01-01 00:00:40,alice,third",
                "2024-01-01 00:01:00,carol,fourth",
                "2024-01-01 00:01:20,bob,fifth",
                "2024-01-01 00:02:00,carol,sixth",
                "",
            ]
        ),
        encoding="utf-8",
    )
    return (
        str(path),
        "created_at",
        "account.username",
        "content_cleaned",
    )
