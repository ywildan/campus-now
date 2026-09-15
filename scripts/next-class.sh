#!/usr/bin/env bash
#
# next-class.sh - Noctalia / Hyprland panel integration script.
#
# Outputs JSON suitable for Noctalia module consumption:
#   {
#     "text": "English · 10:00 · 1h 24m",
#     "tooltip": "Bahasa Inggris\n10:00-11:40\nA.4b.7",
#     "state": "next"
#   }
#
# Usage:
#   ./scripts/next-class.sh
#   ./scripts/next-class.sh --plain   # plain-text text line only
#
# This script delegates all scheduling logic to schedule.py.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

# Use python3 to call the schedule engine's panel output
python3 "$SCRIPT_DIR/campus-now" panel
