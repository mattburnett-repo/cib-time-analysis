#!/bin/bash
cd "$(dirname "$0")"
./updateContainer.sh
source .venv/bin/activate
python -m app.time_gui_main
