#!/usr/bin/env python3
"""
Campus Now - Notification module.

Sends desktop notifications via notify-send when a class is approaching.
Designed to be called by a systemd user timer (NOT a busy-loop).

Usage:
    python3 notify.py

When run, this checks if any class is starting in 30 minutes or 10 minutes
and sends a notification if it hasn't been sent yet for that class.

To prevent duplicate notifications, a state file is written to
~/.cache/campus-now/notification-state.json

systemd timer setup:
    See README section "Optional notifications".
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from schedule import ScheduleEngine, DAY_NAMES, format_duration

try:
    from zoneinfo import ZoneInfo
    TZ = ZoneInfo("Asia/Jakarta")
except ImportError:
    from backports.zoneinfo import ZoneInfo
    TZ = ZoneInfo("Asia/Jakarta")

STATE_FILE = os.path.expanduser("~/.cache/campus-now/notification-state.json")


def load_state() -> dict:
    if not os.path.exists(STATE_FILE):
        return {}
    try:
        with open(STATE_FILE, "r") as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return {}


def save_state(state: dict) -> None:
    os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
    with open(STATE_FILE, "w") as f:
        json.dump(state, f)


def send_notification(title: str, body: str) -> None:
    """Send a desktop notification using notify-send."""
    try:
        subprocess.run(
            ["notify-send", title, body],
            check=True,
            timeout=5,
            capture_output=True,
        )
    except FileNotFoundError:
        print("notify-send not found. Install libnotify.", file=sys.stderr)
    except subprocess.CalledProcessError as exc:
        print(f"notify-send failed: {exc}", file=sys.stderr)


def check_notifications() -> None:
    """Check for upcoming classes and send notifications if needed."""
    engine = ScheduleEngine()
    dt = engine.now()
    state = load_state()

    nxt = engine.next_class_with_day(dt)
    if nxt is None:
        return

    cls, day_key = nxt
    mins = engine.minutes_until_next(dt)
    if mins is None:
        return

    # Create a unique notification key per class instance
    # Includes the day so that the same class on different days gets fresh notifications
    date_str = dt.strftime("%Y-%m-%d")
    class_key = f"{date_str}_{day_key}_{cls['start']}"

    reminders = [30, 10]

    for reminder_min in reminders:
        if mins == reminder_min:
            reminder_key = f"{class_key}_{reminder_min}"
            if state.get(reminder_key, False):
                continue  # Already notified
            body = f"{cls['subject']}\n{cls['start']} · {cls['room']}"
            send_notification(
                f"Class in {reminder_min} minutes",
                body,
            )
            state[reminder_key] = True
        elif mins < reminder_min:
            # Class is closer than this reminder -- clean up state
            reminder_key = f"{class_key}_{reminder_min}"
            if reminder_key in state:
                del state[reminder_key]

    # Clean up old state (older than 1 day)
    old_keys = [k for k in state if k.split("_")[0] != date_str]
    for k in old_keys:
        del state[k]

    save_state(state)


def main():
    check_notifications()


if __name__ == "__main__":
    main()
