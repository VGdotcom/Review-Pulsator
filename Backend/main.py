#!/usr/bin/env python3
"""
Root entry point for Review Pulsator CLI Orchestrator.
Allows running the pipeline directly via `python main.py --help` or `python main.py --dry-run`.
"""
import sys
from review_pulsator.cli import main

if __name__ == "__main__":
    sys.exit(main())
