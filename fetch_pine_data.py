#!/usr/bin/env python3
"""
Quick start script for fetching PINE-related OECD SDMX data.

Usage:
    python fetch_pine_data.py
    python fetch_pine_data.py --flow_id DSD_CAPMF@DF_CAPMF --list_flows
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src", "pipeline"))

from pine_etl import main


if __name__ == "__main__":
    main()

