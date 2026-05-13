#!/usr/bin/env python3
"""
Quick start script for fetching FAPDA data.

Usage:
    python fetch_fapda_data.py
    python fetch_fapda_data.py --resource decisions --limit 1000
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src", "pipeline"))

from fapda_etl import main


if __name__ == "__main__":
    main()

