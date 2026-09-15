#!/usr/bin/env python3
"""
Campus Now web server.

Serves the static web UI and exposes JSON API endpoints.
Uses only the Python standard library (http.server, json, os).

Endpoints:
    GET /api/status  - current class, next class, state
    GET /api/today   - today's classes
    GET /api/week    - all classes Mon-Fri

Run:
    python3 server.py [port]

Default port: 8080
"""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime
from http.server import HTTPServer, SimpleHTTPRequestHandler
from urllib.parse import urlparse

# Make sure we can import schedule.py alongside
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from schedule import (
    ScheduleEngine,
    ScheduleError,
    DAY_NAMES,
    DAY_NAMES as _DAY_NAMES,
    SHORT_DAY_NAMES,
    format_duration,
    VALID_DAYS,
)

try:
    from zoneinfo import ZoneInfo
except ImportError:
    from backports.zoneinfo import ZoneInfo  # type: ignore

WEB_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "web")
DEFAULT_PORT = 8080


class CampusNowHandler(SimpleHTTPRequestHandler):
    """HTTP handler that serves static files and API endpoints."""

    # Serve static files from the web/ directory
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=WEB_DIR, **kwargs)

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path

        if path == "/api/status":
            self._handle_api_status()
        elif path == "/api/today":
            self._handle_api_today()
        elif path == "/api/week":
            self._handle_api_week()
        elif path == "/api/next":
            self._handle_api_next()
        else:
            # Fall back to static file serving
            super().do_GET()

    # -- API handlers -------------------------------------------------- #

    def _get_engine(self) -> ScheduleEngine | None:
        try:
            return ScheduleEngine()
        except ScheduleError as exc:
            self._send_json({"error": str(exc)}, 500)
            return None

    def _handle_api_status(self):
        engine = self._get_engine()
        if engine is None:
            return
        dt = engine.now()
        current = engine.current_class(dt)
        nxt = engine.next_class_with_day(dt)

        status: dict = {
            "state": "now" if current else "next",
            "current": None,
            "next": None,
            "today": [],
            "classes_finished": False,
            "datetime": dt.isoformat(),
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
                "short_day": SHORT_DAY_NAMES[day_key],
                "start": cls["start"],
                "end": cls["end"],
                "room": cls["room"],
                "minutes_until": mins,
            }

        today_classes = engine.today_classes()
        status["classes_finished"] = engine.classes_finished_today(dt)
        for cls in today_classes:
            status["today"].append({
                "subject": cls["subject"],
                "start": cls["start"],
                "end": cls["end"],
                "room": cls["room"],
                "lecturer": cls.get("lecturer"),
                "code": cls.get("code"),
                "sks": cls.get("sks"),
            })

        self._send_json(status)

    def _handle_api_today(self):
        engine = self._get_engine()
        if engine is None:
            return
        dt = engine.now()
        today = engine.today_classes()
        current = engine.current_class(dt)
        nxt = engine.next_class_with_day(dt)

        # Find the next class specifically today
        next_today = engine.next_class_today(dt)
        next_today_data = None
        if next_today:
            next_today_data = {
                "subject": next_today["subject"],
                "start": next_today["start"],
                "end": next_today["end"],
                "room": next_today["room"],
            }

        result = {
            "day": DAY_NAMES[engine.today_key()],
            "classes": [
                {
                    "subject": c["subject"],
                    "code": c.get("code"),
                    "sks": c.get("sks"),
                    "lecturer": c.get("lecturer"),
                    "start": c["start"],
                    "end": c["end"],
                    "room": c["room"],
                    "is_current": current is not None and c["subject"] == current["subject"],
                }
                for c in today
            ],
            "current": current["subject"] if current else None,
            "next_today": next_today_data,
            "classes_finished": engine.classes_finished_today(dt),
        }
        self._send_json(result)

    def _handle_api_week(self):
        engine = self._get_engine()
        if engine is None:
            return
        week = engine.week_classes()
        week_data = {}
        for day_key in VALID_DAYS:
            classes = week.get(day_key, [])
            week_data[DAY_NAMES[day_key]] = [
                {
                    "subject": c["subject"],
                    "start": c["start"],
                    "end": c["end"],
                    "room": c["room"],
                    "lecturer": c.get("lecturer"),
                    "code": c.get("code"),
                    "sks": c.get("sks"),
                }
                for c in classes
            ]
        self._send_json({"week": week_data})

    def _handle_api_next(self):
        engine = self._get_engine()
        if engine is None:
            return
        dt = engine.now()
        nxt = engine.next_class_with_day(dt)
        if nxt is None:
            self._send_json({"next": None})
            return
        cls, day_key = nxt
        mins = engine.minutes_until_next(dt)
        result = {
            "subject": cls["subject"],
            "code": cls.get("code"),
            "sks": cls.get("sks"),
            "lecturer": cls.get("lecturer"),
            "day": day_key,
            "day_name": DAY_NAMES[day_key],
            "short_day": SHORT_DAY_NAMES[day_key],
            "start": cls["start"],
            "end": cls["end"],
            "room": cls["room"],
            "minutes_until": mins,
            "formatted_until": format_duration(mins) if mins else None,
        }
        self._send_json(result)

    # -- helpers ------------------------------------------------------- #

    def _send_json(self, data: dict, status: int = 200):
        body = json.dumps(data, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt, *args):
        # Quiet logging to avoid stderr spam
        pass


def main():
    port = int(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_PORT
    print(f"Campus Now server listening on http://0.0.0.0:{port}")
    server = HTTPServer(("0.0.0.0", port), CampusNowHandler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down...")
        server.shutdown()


if __name__ == "__main__":
    main()
