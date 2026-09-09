#!/usr/bin/env python3
"""Compatibility launcher for the existing python_ruff.py command."""

import sys

from python_ruff import main

if __name__ == "__main__":
    sys.exit(main())
