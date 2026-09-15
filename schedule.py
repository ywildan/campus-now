#!/usr/bin/env python3
"""
Campus Now - Lightweight real-time university schedule assistant.

Central schedule engine. All scheduling logic lives here so that the CLI,
web server, and desktop integration scripts share one source of truth.

Usage:
    python3 schedule.py now        # current class status
    python3 schedule.py next       # next class (today or future)
    python3 schedule.py today      # all classes today
    python3 schedule.py tomorrow   # all classes tomorrow
    python3 schedule.py week       # all classes this week (Mon-Fri)
    python3 schedule.py json       # full JSON status dump

The engine is timezone-aware (Asia/Jakarta by default, configurable in
schedule.json).  It can also be imported as a module for use by server.py
and integration scripts.
"""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timedelta, timezone
from typing import Any

try:
    from zoneinfo import ZoneInfo
except ImportError:  # pragma: no cover - Python 3.8 fallback
    from backports.zoneinfo import ZoneInfo  # type: ignore[no-redef]


# --------------------------------------------------------------------------- #
# Constants
# --------------------------------------------------------------------------- #

VALID_DAYS = [
    "monday", "tuesday", "wednesday", "thursday",
    "friday", "saturday", "sunday",
]

DAY_NAMES = {
    "monday": "Monday", "tuesday": "Tuesday", "wednesday": "Wednesday",
    "thursday": "Thursday", "friday": "Friday", "saturday": "Saturday",
    "sunday": "Sunday",
}

SHORT_DAY_NAMES = {
    "monday": "Mon", "tuesday": "Tue", "wednesday": "Wed",
    "thursday": "Thu", "friday": "Fri", "saturday": "Sat", "sunday": "Sun",
}

DEFAULT_TZ = "Asia/Jakarta"
DEFAULT_SCHEDULE_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "schedule.json"
)


# --------------------------------------------------------------------------- #
# Schedule loading & validation
# --------------------------------------------------------------------------- #

class ScheduleError(Exception):
    """Raised when schedule.json contains invalid data."""


def load_schedule(path: str | None = None) -> dict[str, Any]:
    """Load and validate schedule.json.  Returns the parsed dict."""
    if path is None:
        path = os.environ.get("CAMPUS_NOW_SCHEDULE", DEFAULT_SCHEDULE_PATH)

    if not os.path.exists(path):
        raise ScheduleError(f"Schedule file not found: {path}")

    try:
        with open(path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
    except json.JSONDecodeError as exc:
        raise ScheduleError(f"Invalid JSON in {path}: {exc}") from exc

    _validate_schedule(data, path)
    return data


def _validate_schedule(data: dict[str, Any], path: str) -> None:
    """Validate the top-level structure and each class entry."""
    if not isinstance(data, dict):
        raise ScheduleError(f"{path}: root must be a JSON object")

    tz_name = data.get("timezone", DEFAULT_TZ)
    try:
        ZoneInfo(tz_name)
    except Exception as exc:
        raise ScheduleError(f"{path}: invalid timezone '{tz_name}': {exc}") from exc

    days = data.get("days", {})
    if not isinstance(days, dict):
        raise ScheduleError(f"{path}: 'days' must be an object")

    for day_key in days:
        if day_key not in VALID_DAYS:
            raise ScheduleError(
                f"{path}: invalid day '{day_key}'. "
                f"Must be one of: {', '.join(VALID_DAYS)}"
            )
        classes = days[day_key]
        if not isinstance(classes, list):
            raise ScheduleError(
                f"{path}: classes for '{day_key}' must be a list"
            )
        for idx, cls in enumerate(classes):
            _validate_class(cls, path, day_key, idx)


def _validate_class(cls: Any, path: str, day_key: str, idx: int) -> None:
    """Validate a single class entry."""
    if not isinstance(cls, dict):
        raise ScheduleError(
            f"{path}: class #{idx} on {day_key} must be an object"
        )
    if not cls.get("subject"):
        raise ScheduleError(
            f"{path}: class #{idx} on {day_key} has a missing 'subject'"
        )
    if not cls.get("start"):
        raise ScheduleError(
            f"{path}: class #{idx} on {day_key} has a missing 'start' time"
        )
    if not cls.get("end"):
        raise ScheduleError(
            f"{path}: class #{idx} on {day_key} has a missing 'end' time"
        )

    start_h, start_m = _parse_time(cls["start"], path, day_key, idx)
    end_h, end_m = _parse_time(cls["end"], path, day_key, idx)

    start_min = start_h * 60 + start_m
    end_min = end_h * 60 + end_m
    if end_min <= start_min:
        raise ScheduleError(
            f"{path}: class #{idx} on {day_key} "
            f"('{cls['subject']}'): end time {cls['end']} is not after "
            f"start time {cls['start']}"
        )


def _parse_time(time_str: str, path: str, day_key: str, idx: int) -> tuple[int, int]:
    """Parse 'HH:MM' and return (hours, minutes).  Raises ScheduleError."""
    if not isinstance(time_str, str):
        raise ScheduleError(
            f"{path}: class #{idx} on {day_key} has a non-string time value"
        )
    parts = time_str.split(":")
    if len(parts) != 2:
        raise ScheduleError(
            f"{path}: class #{idx} on {day_key} has invalid time format "
            f"'{time_str}' (expected HH:MM)"
        )
    try:
        h = int(parts[0])
        m = int(parts[1])
    except ValueError:
        raise ScheduleError(
            f"{path}: class #{idx} on {day_key} has non-numeric time "
            f"'{time_str}'"
        )
    if not (0 <= h <= 23 and 0 <= m <= 59):
        raise ScheduleError(
            f"{path}: class #{idx} on {day_key} has out-of-range time "
            f"'{time_str}'"
        )
    return h, m


# --------------------------------------------------------------------------- #
# Core engine
# --------------------------------------------------------------------------- #

class ScheduleEngine:
    """Timezone-aware university schedule engine."""

    def __init__(self, schedule_path: str | None = None):
        self.schedule_path = schedule_path or DEFAULT_SCHEDULE_PATH
        self.data = load_schedule(self.schedule_path)
        tz_name = self.data.get("timezone", DEFAULT_TZ)
        self.tz = ZoneInfo(tz_name)
        self.days = self.data["days"]

    # -- public helpers --------------------------------------------------- #

    def now(self) -> datetime:
        """Return the current datetime in the schedule's timezone."""
        return datetime.now(self.tz)

    def today_key(self, dt: datetime | None = None) -> str:
        """Return today's day key (e.g. 'monday')."""
        if dt is None:
            dt = self.now()
        return VALID_DAYS[dt.weekday()]

    def classes_for_day(self, day_key: str) -> list[dict[str, Any]]:
        """Return all classes for a given day key, sorted by start time."""
        raw = self.days.get(day_key, [])
        return sorted(raw, key=lambda c: _time_to_minutes(c["start"]))

    def today_classes(self, dt: datetime | None = None) -> list[dict[str, Any]]:
        """Return today's classes sorted chronologically."""
        if dt is None:
            dt = self.now()
        return self.classes_for_day(self.today_key(dt))

    def _classes_at(self, dt: datetime) -> list[dict[str, Any]]:
        """Return classes for the day of *dt*."""
        day_key = VALID_DAYS[dt.weekday()]
        return self.classes_for_day(day_key)

    # -- core queries ----------------------------------------------------- #

    def current_class(
        self, dt: datetime | None = None
    ) -> dict[str, Any] | None:
        """Return the class happening at *dt*, or None."""
        if dt is None:
            dt = self.now()
        day_classes = self._classes_at(dt)
        target = _time_to_minutes(dt.strftime("%H:%M"))
        for cls in day_classes:
            start_min = _time_to_minutes(cls["start"])
            end_min = _time_to_minutes(cls["end"])
            if start_min <= target < end_min:
                return cls
        return None

    def next_class_today(
        self, dt: datetime | None = None
    ) -> dict[str, Any] | None:
        """Return the next class *today* that hasn't started yet, or None."""
        if dt is None:
            dt = self.now()
        day_classes = self._classes_at(dt)
        target = _time_to_minutes(dt.strftime("%H:%M"))
        for cls in day_classes:
            start_min = _time_to_minutes(cls["start"])
            if start_min > target:
                return cls
        return None

    def next_class(self, dt: datetime | None = None) -> dict[str, Any] | None:
        """Return the next class across today and future days.

        If *dt* is within a class that has already ended today, the search
        starts from *dt*'s minute-of-day so that an already-finished class
        is not returned.
        """
        if dt is None:
            dt = self.now()
        day_classes = self._classes_at(dt)
        target = _time_to_minutes(dt.strftime("%H:%M"))
        for cls in day_classes:
            start_min = _time_to_minutes(cls["start"])
            if start_min > target:
                return cls

        # Look ahead, day by day (up to 7 days).
        for offset in range(1, 8):
            future_dt = dt + timedelta(days=offset)
            future_classes = self._classes_at(future_dt)
            if future_classes:
                return future_classes[0]
        return None

    def next_class_with_day(
        self, dt: datetime | None = None
    ) -> tuple[dict[str, Any], str] | None:
        """Return (class_dict, day_key) for the next upcoming class."""
        if dt is None:
            dt = self.now()
        day_classes = self._classes_at(dt)
        target = _time_to_minutes(dt.strftime("%H:%M"))
        for cls in day_classes:
            start_min = _time_to_minutes(cls["start"])
            if start_min > target:
                day_key = VALID_DAYS[dt.weekday()]
                return cls, day_key

        for offset in range(1, 8):
            future_dt = dt + timedelta(days=offset)
            day_key = VALID_DAYS[future_dt.weekday()]
            future_classes = self._classes_at(future_dt)
            if future_classes:
                return future_classes[0], day_key
        return None

    def classes_finished_today(
        self, dt: datetime | None = None
    ) -> bool:
        """Return True if all of today's classes have ended."""
        if dt is None:
            dt = self.now()
        if self.current_class(dt) is not None:
            return False
        if self.next_class_today(dt) is not None:
            return False
        return True

    # -- time calculations ------------------------------------------------ #

    def minutes_until_next(
        self, dt: datetime | None = None
    ) -> int | None:
        """Return whole minutes until the next class starts (any day)."""
        info = self.next_class_with_day(dt)
        if info is None:
            return None
        cls, day_key = info
        return _minutes_between(dt, cls["start"], day_key)

    def minutes_remaining(
        self, dt: datetime | None = None
    ) -> int | None:
        """Return whole minutes remaining in the current class."""
        if dt is None:
            dt = self.now()
        current = self.current_class(dt)
        if current is None:
            return None
        end_min = _time_to_minutes(current["end"])
        target = _time_to_minutes(dt.strftime("%H:%M"))
        return end_min - target

    def class_progress(
        self, dt: datetime | None = None
    ) -> float | None:
        """Return progress (0.0 - 1.0) of the current class, or None."""
        if dt is None:
            dt = self.now()
        current = self.current_class(dt)
        if current is None:
            return None
        start_min = _time_to_minutes(current["start"])
        end_min = _time_to_minutes(current["end"])
        target = _time_to_minutes(dt.strftime("%H:%M"))
        total = end_min - start_min
        if total <= 0:
            return 0.0
        return round((target - start_min) / total, 4)

    # -- convenience ------------------------------------------------------ #

    def tomorrow_classes(self) -> list[dict[str, Any]]:
        """Return tomorrow's classes."""
        tomorrow_dt = self.now() + timedelta(days=1)
        day_key = VALID_DAYS[tomorrow_dt.weekday()]
        return self.classes_for_day(day_key)

    def week_classes(self, dt: datetime | None = None) -> dict[str, list[dict[str, Any]]]:
        """Return classes for each weekday (Mon-Fri) of the current week."""
        if dt is None:
            dt = self.now()
        result: dict[str, list[dict[str, Any]]] = {}
        week_start = dt - timedelta(days=dt.weekday())  # Monday
        for i in range(7):
            day = week_start + timedelta(days=i)
            day_key = VALID_DAYS[day.weekday()]
            classes = self.classes_for_day(day_key)
            if classes:
                result[day_key] = classes
        return result


# --------------------------------------------------------------------------- #
# Utility functions
# --------------------------------------------------------------------------- #

def _time_to_minutes(time_str: str) -> int:
    """Convert 'HH:MM' to minutes since midnight."""
    h, m = time_str.split(":")
    return int(h) * 60 + int(m)


def _minutes_between(
    dt: datetime, time_str: str, day_key: str
) -> int:
    """Whole minutes from *dt* to *time_str* on *day_key*."""
    target_min = _time_to_minutes(time_str)
    dt_min = _time_to_minutes(dt.strftime("%H:%M"))
    # Days from dt's actual weekday to day_key
    dt_day_idx = dt.weekday()
    target_day_idx = VALID_DAYS.index(day_key)
    day_diff = (target_day_idx - dt_day_idx) % 7
    delta_minutes = (day_diff * 24 * 60 + target_min) - dt_min
    return delta_minutes


def parse_datetime_override(value: str, tz: ZoneInfo | None = None) -> datetime:
    """Parse a datetime string in 'YYYY-MM-DD HH:MM' format.

    Returns a timezone-aware datetime.  If *tz* is None, the engine's
    timezone (from schedule.json) is used.

    Raises ScheduleError for invalid input.
    """
    if tz is None:
        tz = ZoneInfo(DEFAULT_TZ)
    try:
        naive = datetime.strptime(value.strip(), "%Y-%m-%d %H:%M")
    except ValueError:
        raise ScheduleError(
            f"Invalid datetime format: '{value}'. "
            f"Expected 'YYYY-MM-DD HH:MM' (e.g. '2026-09-15 10:30')."
        )
    return naive.replace(tzinfo=tz)


def format_duration(minutes: int) -> str:
    """Format minutes as human-friendly string."""
    if minutes < 0:
        return f"{abs(minutes)}m ago"
    if minutes < 60:
        return f"{minutes}m"
    hours = minutes // 60
    mins = minutes % 60
    if mins == 0:
        return f"{hours}h"
    return f"{hours}h {mins}m"


def get_engine(path: str | None = None) -> ScheduleEngine:
    """Convenience: create a ScheduleEngine (module-level helper)."""
    return ScheduleEngine(path)


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #

def _print_now(engine: ScheduleEngine, override_dt: datetime | None = None) -> None:
    """Handle 'now' subcommand."""
    dt = override_dt if override_dt is not None else engine.now()
    current = engine.current_class(dt)
    nxt = engine.next_class_with_day(dt)

    if current:
        start = current["start"]
        end = current["end"]
        remaining = engine.minutes_remaining(dt)
        progress = engine.class_progress(dt)
        print("CURRENT CLASS")
        print(current["subject"])
        print(f"{start} - {end}")
        print(f"Room: {current['room']}")
        if remaining is not None:
            print(f"\nEnds in {remaining} minutes")
        if progress is not None:
            print(f"Progress: {int(progress * 100)}%")
    else:
        print("No class is currently running.")

    if nxt:
        cls, day_key = nxt
        mins = engine.minutes_until_next(dt)
        print(f"\nNext:")
        print(cls["subject"])
        print(f"{DAY_NAMES[day_key]} {cls['start']}")
        print(cls["room"])
        if mins is not None:
            print(f"Starts in {format_duration(mins)}")


def _print_next(engine: ScheduleEngine, override_dt: datetime | None = None) -> None:
    """Handle 'next' subcommand."""
    dt = override_dt if override_dt is not None else engine.now()
    nxt = engine.next_class_with_day(dt)
    if nxt is None:
        print("No upcoming classes found in the next 7 days.")
        return
    cls, day_key = nxt
    mins = engine.minutes_until_next(dt)
    print(cls["subject"])
    print(f"{day_key} {cls['start']}")
    print(cls["room"])
    if mins is not None:
        print(f"\nStarts in {format_duration(mins)}")


def _print_today(engine: ScheduleEngine, override_dt: datetime | None = None) -> None:
    """Handle 'today' subcommand."""
    dt = override_dt if override_dt is not None else engine.now()
    today = engine.today_classes(dt)
    day_key = engine.today_key(dt)

    if not today:
        print(f"No classes today ({DAY_NAMES[day_key]}).")
    else:
        print(f"Today ({DAY_NAMES[day_key]}):")
        for cls in today:
            print(f"  {cls['start']} - {cls['end']}  {cls['subject']}  ({cls['room']})")


def _print_tomorrow(engine: ScheduleEngine, override_dt: datetime | None = None) -> None:
    """Handle 'tomorrow' subcommand."""
    base = override_dt if override_dt is not None else engine.now()
    tomorrow_dt = base + timedelta(days=1)
    day_key = VALID_DAYS[tomorrow_dt.weekday()]
    tomorrow = engine.classes_for_day(day_key)

    if not tomorrow:
        print(f"No classes tomorrow ({DAY_NAMES[day_key]}).")
    else:
        print(f"Tomorrow ({DAY_NAMES[day_key]}):")
        for cls in tomorrow:
            print(f"  {cls['start']} - {cls['end']}  {cls['subject']}  ({cls['room']})")


def _print_week(engine: ScheduleEngine, override_dt: datetime | None = None) -> None:
    """Handle 'week' subcommand."""
    base = override_dt if override_dt is not None else engine.now()
    week = engine.week_classes(base)
    for day_key in VALID_DAYS[:7]:
        classes = week.get(day_key, [])
        if classes:
            print(f"{DAY_NAMES[day_key]}:")
            for cls in classes:
                print(f"  {cls['start']} - {cls['end']}  {cls['subject']}  ({cls['room']})")
        else:
            print(f"{DAY_NAMES[day_key]}: (no classes)")


def _print_json(engine: ScheduleEngine, override_dt: datetime | None = None) -> None:
    """Handle 'json' subcommand - full status dump."""
    dt = override_dt if override_dt is not None else engine.now()
    current = engine.current_class(dt)
    nxt = engine.next_class_with_day(dt)

    status: dict[str, Any] = {
        "now": dt.isoformat(),
        "state": "now" if current else "next",
        "current": None,
        "next": None,
        "today": [],
        "classes_finished": False,
    }

    if current:
        remaining = engine.minutes_remaining(dt)
        progress = engine.class_progress(dt)
        status["current"] = {
            "subject": current["subject"],
            "code": current.get("code"),
            "sks": current.get("sks"),
            "lecturer": current.get("lecturer"),
            "class": current.get("class"),
            "start": current["start"],
            "end": current["end"],
            "room": current["room"],
            "minutes_remaining": remaining,
            "progress": progress,
        }

    if nxt:
        cls, day_key = nxt
        mins = engine.minutes_until_next(dt)
        status["next"] = {
            "subject": cls["subject"],
            "code": cls.get("code"),
            "sks": cls.get("sks"),
            "lecturer": cls.get("lecturer"),
            "class": cls.get("class"),
            "day": day_key,
            "day_name": DAY_NAMES[day_key],
            "start": cls["start"],
            "end": cls["end"],
            "room": cls["room"],
            "minutes_until": mins,
        }

    today_classes = engine.today_classes(dt)
    status["classes_finished"] = engine.classes_finished_today(dt)
    for cls in today_classes:
        status["today"].append({
            "subject": cls["subject"],
            "start": cls["start"],
            "end": cls["end"],
            "room": cls["room"],
        })

    print(json.dumps(status, indent=2))


def main(argv: list[str] | None = None) -> int:
    """CLI entry point."""
    if argv is None:
        argv = sys.argv[1:]

    if not argv or argv[0] in ("--help", "-h", "help"):
        print(
            "Campus Now schedule engine\n"
            "\n"
            "Usage:\n"
            "  schedule.py now     Show current and next class\n"
            "  schedule.py next    Show next upcoming class\n"
            "  schedule.py today   Show today's classes\n"
            "  schedule.py tomorrow  Show tomorrow's classes\n"
            "  schedule.py week    Show this week's classes\n"
            "  schedule.py json    Full JSON status dump\n"
            "\n"
            "Options:\n"
            "  --at \"YYYY-MM-DD HH:MM\"  Simulate a specific datetime (Asia/Jakarta)\n"
        )
        return 0

    # Parse --at override
    override_dt = None
    args = list(argv)
    at_index = None
    for i, arg in enumerate(args):
        if arg == "--at":
            at_index = i
            break
    cmd = args[0] if args else ""

    try:
        engine = ScheduleEngine()
    except ScheduleError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    if at_index is not None:
        if at_index + 1 >= len(args):
            print("Error: --at requires a datetime argument.", file=sys.stderr)
            print("Format: YYYY-MM-DD HH:MM (e.g. '2026-09-15 10:30')", file=sys.stderr)
            return 1
        at_value = args[at_index + 1]
        try:
            override_dt = parse_datetime_override(at_value, engine.tz)
        except ScheduleError as exc:
            print(f"Error: {exc}", file=sys.stderr)
            return 1

    handlers = {
        "now": _print_now,
        "next": _print_next,
        "today": _print_today,
        "tomorrow": _print_tomorrow,
        "week": _print_week,
        "json": _print_json,
    }

    handler = handlers.get(cmd)
    if handler is None:
        print(f"Unknown command: {cmd}", file=sys.stderr)
        print(f"Run 'schedule.py --help' for usage.", file=sys.stderr)
        return 1

    handler(engine, override_dt)
    return 0


if __name__ == "__main__":
    sys.exit(main())
