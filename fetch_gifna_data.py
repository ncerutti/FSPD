#!/usr/bin/env python3
"""
Quick start script for fetching GIFNA data assets.

Usage:
    python fetch_gifna_data.py
    python fetch_gifna_data.py --skip_boundaries --no_csv
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src", "pipeline"))

from gifna_etl import main


if __name__ == "__main__":
    main()

