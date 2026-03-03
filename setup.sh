#!/bin/bash
set -e

echo ">>> Running uv sync..."
uv sync

echo ">>> Installing Playwright browsers..."
uv run playwright install

echo ">>> Running main.py..."
uv run main.py
