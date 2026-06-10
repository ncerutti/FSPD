#!/usr/bin/env python3
"""
Quick start script for fetching record-level OECD PINE data.

Usage:
    python3 fetch_pine_data.py
    python3 fetch_pine_data.py --include_ertr
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src", "pipeline"))

from pine_etl import main


if __name__ == "__main__":
    main()

