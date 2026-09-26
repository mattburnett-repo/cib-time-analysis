#!/bin/bash
cd "$(dirname "$0")"
git fetch origin
git log --oneline main..origin/main
git pull origin main
git log -3 --oneline
