#!/usr/bin/env python3
"""Entry point for WSB Tracker CLI.

This module allows running the tracker directly with:
    python main.py [command]

For installed usage, use:
    wsb [command]
    wsb-tracker [command]
"""

from wsb_tracker.cli import app

if __name__ == "__main__":
    app()
