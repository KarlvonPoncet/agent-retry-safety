#!/usr/bin/env python3
"""Regenerate analysis tables and figures from a benchmark JSON artifact."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from analysis.retry_analysis import analyze_file  # noqa: E402

parser = argparse.ArgumentParser()
parser.add_argument("input", help="agent benchmark JSON")
parser.add_argument("output_dir", help="directory for summary.csv and SVG figures")
args = parser.parse_args()
rows = analyze_file(args.input, args.output_dir)
print(f"wrote {len(rows)} summary cells to {args.output_dir}")
