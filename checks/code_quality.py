#!/usr/bin/env python3
"""Compatibility launcher for the existing code_quality.py command."""

import sys

from code_quality import main

if __name__ == "__main__":
    sys.exit(main())
