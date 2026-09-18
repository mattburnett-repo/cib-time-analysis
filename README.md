# CIB Time Analysis

Local NiceGUI app for building and inspecting user networks from posting-time data.

This project is based on time analysis code authored by [John Biddle](https://github.com/johnbiddle). It is primarily UI enhancements, based on John's work.

## Clone

```bash
git clone https://github.com/mattburnett-repo/cib-time-analysis.git
cd CIB_TimeAnalysis
```

## First-time setup

Requires Python 3. Then:

```bash
./setup.sh
```

This creates `.venv` and installs dependencies from `requirements.txt`.

## Start

```bash
./start.sh
```

Open the URL shown in the terminal (default: http://localhost:8080).

## Codespaces

**You can run the time analysis code in your browser, using GitHub Codespaces**

You need a GitHub account with Codespaces enabled.

1. Click **Code → Codespaces → Create codespace on main** (it's the green 'Code' button, upper right). First launch can take a few minutes while it sets up.
2. In the Codespace terminal, run: `./start.sh`
3. If the app doesn’t open, use **Ports → 8080**.


## Datasets (`csv_data/`)

The app expects CSV files under `csv_data/` (see `modules/timeseries_gui_config.py`).

**Truth Social Vax is not in the GitHub repo.**  
`csv_data/data/truth_vax_2024-2025.csv` is about **129 MB**, which exceeds GitHub’s **100 MB** per-file limit, so pushes that include it are rejected. Keep that file on your machine (or obtain it from the project maintainers / your data source) and place it at:

```text
csv_data/data/truth_vax_2024-2025.csv
```

Without it, the **Truth Social Vax** dataset option will fail when you try to build a graph. Bluesky and other smaller files may still be present in the repo depending on what was committed.

## Layout

| Path                               | Role                                                       |
| ---------------------------------- | ---------------------------------------------------------- |
| `app/time_gui_main.py`             | NiceGUI page: builds widgets and binds `StepperController` |
| `app/time_analysis.py`             | Core similarity / graph-building algorithms                |
| `modules/my_graph.py`              | Session graph cache (`MyGraph`) and weight cutting         |
| `modules/chart_utils.py`           | ECharts defaults, click JS, edge/node payload helpers      |
| `modules/stepper.py`               | Step navigation and panel sync (`StepperController`)       |
| `modules/session.py`               | Typed `StepperContext` passed into `bind()`                |
| `modules/timeseries_gui_config.py` | Dataset / method labels and CSV column maps                |
| `tests/`                           | Pytest suite (`./runtests.sh`)                             |

## Tests

```bash
./runtests.sh
```

Covers `time_analysis`, chart/graph helpers, `StepperController` (mocked UI), and entrypoint smoke checks.
