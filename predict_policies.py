#!/usr/bin/env python3
"""
Quick start script for making predictions with trained model.

Usage:
    python predict_policies.py --input data/new_policies.csv --output data/predictions.csv
"""
import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src', 'models'))

from predict import main

if __name__ == '__main__':
    main()
