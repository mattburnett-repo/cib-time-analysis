#!/bin/bash
cd "$(dirname "$0")"
git pull origin main
git log -3 --oneline
