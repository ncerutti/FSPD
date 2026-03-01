#!/usr/bin/env python3
"""
Quick start script for training FSPD classification model.

Usage:
    python train_model.py
    python train_model.py --epochs 5 --batch_size 32
"""
import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src', 'models'))

from train import main

if __name__ == '__main__':
    main()
