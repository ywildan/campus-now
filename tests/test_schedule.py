#!/usr/bin/env python3
"""
Tests for the Campus Now schedule engine.

Tests simulate specific timestamps and verify that current-class detection,
next-class detection, and countdown logic behave correctly across days,
including the Monday->Tuesday transition, weekend handling, and the
Sunday->Monday wrap-around.
"""

import json
import os
import sys
import tempfile
from datetime import datetime, timezone

# Make the project root importable
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from schedule import (
    ScheduleEngine,
    ScheduleError,
    DAY_NAMES,
    _time_to_minutes,
    format_duration,
    parse_datetime_override,
)

try:
    from zoneinfo import ZoneInfo
except ImportError:
    from backports.zoneinfo import ZoneInfo  # type: ignore


TZ = ZoneInfo("Asia/Jakarta")

SAMPLE_SCHEDULE = {
    "timezone": "Asia/Jakarta",
    "days": {
        "monday": [
            {
                "subject": "Pengantar Bisnis",
                "code": "002046",
                "sks": 3,
                "lecturer": "Masculine Muhammad Muqorobin, S.E., M.Si.",
                "class": "01",
                "start": "15:10",
                "end": "17:40",
                "room": "A.3b.4",
            }
        ],
        "tuesday": [
            {
                "subject": "Bahasa Inggris",
                "code": "001006",
                "sks": 2,
                "lecturer": "Gilang Fadhilia Arvianti, S.S., M.Hum.",
                "class": "02",
                "start": "10:00",
                "end": "11:40",
                "room": "A.4b.7 (Lab. Komputer)",
            },
            {
                "subject": "Budaya dan Karakter Tidar",
                "code": "001016",
                "sks": 2,
                "lecturer": "Endang Kartini Panggiarti, S.E., M.Si.",
                "class": "01",
                "start": "13:40",
                "end": "15:20",
                "room": "A.3b.1",
            },
        ],
        "wednesday": [
            {
                "subject": "Ketentuan Umum Perpajakan",
                "code": "106001",
                "sks": 2,
                "lecturer": "Afif Musthafa, S.Ak., M.Ak.",
                "class": "01",
                "start": "07:00",
                "end": "08:40",
                "room": "A.3b.5",
            },
            {
                "subject": "Bahasa Indonesia",
                "code": "001003",
                "sks": 2,
                "lecturer": "Sri Wulandari, S.S., M.Hum.",
                "class": "01",
                "start": "10:40",
                "end": "12:20",
                "room": "A.3b.2",
            },
            {
                "subject": "Pengantar Akuntansi",
                "code": "002047",
                "sks": 3,
                "lecturer": "Retnosari, S.Pd., M.Si.",
                "class": "01",
                "start": "12:30",
                "end": "15:00",
                "room": "A.3b.6",
            },
        ],
        "thursday": [
            {
                "subject": "Matematika Bisnis",
                "code": "002044",
                "sks": 3,
                "lecturer": "Yulida Army Nurcahya, M.Acc.",
                "class": "01",
                "start": "07:00",
                "end": "09:30",
                "room": "A.3b.2",
            },
            {
                "subject": "Pengantar Teori Ekonomi",
                "code": "002048",
                "sks": 3,
                "lecturer": "Endang Kartini Panggiarti, S.E., M.Si.",
                "class": "01",
                "start": "09:40",
                "end": "12:10",
                "room": "A.3b.1",
            },
        ],
        "friday": [],
        "saturday": [],
        "sunday": [],
    },
}


def make_engine(schedule=None):
    """Create a ScheduleEngine backed by a temp file."""
    if schedule is None:
        schedule = SAMPLE_SCHEDULE
    fd, path = tempfile.mkstemp(suffix=".json")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump(schedule, f)
    return ScheduleEngine(path)


def make_dt(weekday_iso: int, hour: int, minute: int = 0) -> datetime:
    """Create a tz-aware datetime on a specific ISO weekday (0=Mon, 6=Sun).

    Picks the nearest calendar date to today with the desired weekday.
    """
    today = datetime.now(TZ)
    today_idx = today.weekday()
    delta_days = (weekday_iso - today_idx) % 7
    target_date = today.date() + __import__("datetime").timedelta(days=delta_days)
    return datetime(
        target_date.year, target_date.month, target_date.day,
        hour, minute, tzinfo=TZ,
    )


# --------------------------------------------------------------------------- #
# Tests
# --------------------------------------------------------------------------- #

def test_monday_1400_next_pengantar_bisnis():
    """Monday 14:00 -> no current class, next = Pengantar Bisnis."""
    engine = make_engine()
    dt = make_dt(0, 14, 0)  # Monday 14:00
    current = engine.current_class(dt)
    nxt = engine.next_class_with_day(dt)
    assert current is None, f"Expected no current class, got {current}"
    assert nxt is not None
    cls, day_key = nxt
    assert cls["subject"] == "Pengantar Bisnis"
    assert day_key == "monday"
    print("PASS: Monday 14:00 -> next = Pengantar Bisnis")


def test_monday_1600_current_pengantar_bisnis():
    """Monday 16:00 -> current = Pengantar Bisnis."""
    engine = make_engine()
    dt = make_dt(0, 16, 0)
    current = engine.current_class(dt)
    assert current is not None
    assert current["subject"] == "Pengantar Bisnis"
    remaining = engine.minutes_remaining(dt)
    # 17:40 - 16:00 = 100 minutes
    assert remaining == 100, f"Expected 100 min remaining, got {remaining}"
    progress = engine.class_progress(dt)
    # (16:00 - 15:10) / (17:40 - 15:10) = 50 / 150 = 0.333
    assert abs(progress - 50 / 150) < 0.01, f"Progress {progress} != 0.333"
    print("PASS: Monday 16:00 -> current = Pengantar Bisnis")


def test_monday_1800_no_more_classes_next_bahasa_inggris():
    """Monday 18:00 -> no current class, next = Bahasa Inggris (Tuesday)."""
    engine = make_engine()
    dt = make_dt(0, 18, 0)
    current = engine.current_class(dt)
    assert current is None
    nxt = engine.next_class_with_day(dt)
    assert nxt is not None
    cls, day_key = nxt
    assert cls["subject"] == "Bahasa Inggris"
    assert day_key == "tuesday"
    print("PASS: Monday 18:00 -> next = Bahasa Inggris (Tuesday)")


def test_tuesday_1030_current_bahasa_inggris():
    """Tuesday 10:30 -> current = Bahasa Inggris."""
    engine = make_engine()
    dt = make_dt(1, 10, 30)
    current = engine.current_class(dt)
    assert current is not None
    assert current["subject"] == "Bahasa Inggris"
    print("PASS: Tuesday 10:30 -> current = Bahasa Inggris")


def test_tuesday_1200_next_budaya_tidar():
    """Tuesday 12:00 -> no current, next = Budaya dan Karakter Tidar."""
    engine = make_engine()
    dt = make_dt(1, 12, 0)
    current = engine.current_class(dt)
    assert current is None
    nxt = engine.next_class_with_day(dt)
    assert nxt is not None
    cls, day_key = nxt
    assert cls["subject"] == "Budaya dan Karakter Tidar"
    assert day_key == "tuesday"
    print("PASS: Tuesday 12:00 -> next = Budaya dan Karakter Tidar")


def test_wednesday_0730_current_ketentuan_umum_perpajakan():
    """Wednesday 07:30 -> current = Ketentuan Umum Perpajakan."""
    engine = make_engine()
    dt = make_dt(2, 7, 30)
    current = engine.current_class(dt)
    assert current is not None
    assert current["subject"] == "Ketentuan Umum Perpajakan"
    print("PASS: Wednesday 07:30 -> current = Ketentuan Umum Perpajakan")


def test_wednesday_1225_next_pengantar_akuntansi_5min():
    """Wednesday 12:25 -> next = Pengantar Akuntansi, starts in ~5 min."""
    engine = make_engine()
    dt = make_dt(2, 12, 25)
    current = engine.current_class(dt)
    assert current is None
    nxt = engine.next_class_with_day(dt)
    assert nxt is not None
    cls, day_key = nxt
    assert cls["subject"] == "Pengantar Akuntansi"
    mins = engine.minutes_until_next(dt)
    # 12:30 - 12:25 = 5 minutes
    assert mins == 5, f"Expected 5 min until next, got {mins}"
    print("PASS: Wednesday 12:25 -> next = Pengantar Akuntansi in 5m")


def test_wednesday_1300_current_pengantar_akuntansi():
    """Wednesday 13:00 -> current = Pengantar Akuntansi."""
    engine = make_engine()
    dt = make_dt(2, 13, 0)
    current = engine.current_class(dt)
    assert current is not None
    assert current["subject"] == "Pengantar Akuntansi"
    print("PASS: Wednesday 13:00 -> current = Pengantar Akuntansi")


def test_thursday_0800_current_matematika_bisnis():
    """Thursday 08:00 -> current = Matematika Bisnis."""
    engine = make_engine()
    dt = make_dt(3, 8, 0)
    current = engine.current_class(dt)
    assert current is not None
    assert current["subject"] == "Matematika Bisnis"
    print("PASS: Thursday 08:00 -> current = Matematika Bisnis")


def test_thursday_0935_next_pengantar_teori_ekonomi_5min():
    """Thursday 09:35 -> next = Pengantar Teori Ekonomi, starts in 5 min."""
    engine = make_engine()
    dt = make_dt(3, 9, 35)
    current = engine.current_class(dt)
    assert current is None
    nxt = engine.next_class_with_day(dt)
    assert nxt is not None
    cls, day_key = nxt
    assert cls["subject"] == "Pengantar Teori Ekonomi"
    mins = engine.minutes_until_next(dt)
    # 09:40 - 09:35 = 5 minutes
    assert mins == 5, f"Expected 5 min until next, got {mins}"
    print("PASS: Thursday 09:35 -> next = Pengantar Teori Ekonomi in 5m")


def test_thursday_1300_no_more_classes_next_monday():
    """Thursday 13:00 -> no current, next = Pengantar Bisnis (Monday)."""
    engine = make_engine()
    dt = make_dt(3, 13, 0)
    current = engine.current_class(dt)
    assert current is None
    nxt = engine.next_class_with_day(dt)
    assert nxt is not None
    cls, day_key = nxt
    assert cls["subject"] == "Pengantar Bisnis"
    assert day_key == "monday"
    print("PASS: Thursday 13:00 -> next = Pengantar Bisnis (Mon)")


def test_friday_no_classes_next_monday():
    """Friday (any time) -> no classes today, next = Pengantar Bisnis (Mon)."""
    engine = make_engine()
    dt = make_dt(4, 10, 0)  # Friday 10:00
    today_classes = engine.today_classes(dt)
    assert len(today_classes) == 0
    current = engine.current_class(dt)
    assert current is None
    nxt = engine.next_class_with_day(dt)
    assert nxt is not None
    cls, day_key = nxt
    assert cls["subject"] == "Pengantar Bisnis"
    assert day_key == "monday"
    print("PASS: Friday -> no classes, next = Pengantar Bisnis (Mon)")


def test_sunday_no_classes_next_monday():
    """Sunday (any time) -> no classes today, next = Pengantar Bisnis (Mon)."""
    engine = make_engine()
    dt = make_dt(6, 10, 0)  # Sunday 10:00
    today_classes = engine.today_classes(dt)
    assert len(today_classes) == 0
    current = engine.current_class(dt)
    assert current is None
    nxt = engine.next_class_with_day(dt)
    assert nxt is not None
    cls, day_key = nxt
    assert cls["subject"] == "Pengantar Bisnis"
    assert day_key == "monday"
    print("PASS: Sunday -> next = Pengantar Bisnis (Mon)")


def test_classes_finished_today():
    """After the last class, classes_finished_today should be True."""
    engine = make_engine()
    dt = make_dt(0, 18, 0)  # Monday 18:00, after class ends
    assert engine.classes_finished_today(dt) is True
    dt2 = make_dt(0, 16, 0)  # Monday 16:00, during class
    assert engine.classes_finished_today(dt2) is False
    print("PASS: classes_finished_today correctly reports state")


def test_progress_during_class():
    """Progress should be between 0 and 1 during a class."""
    engine = make_engine()
    dt = make_dt(0, 16, 0)  # 50 min into a 150-min class
    progress = engine.class_progress(dt)
    assert progress is not None
    assert 0.0 < progress < 1.0
    print(f"PASS: progress during class = {progress}")


def test_progress_at_start_of_class():
    """Progress should be ~0 at the exact start of a class."""
    engine = make_engine()
    dt = make_dt(0, 15, 10)
    progress = engine.class_progress(dt)
    assert progress is not None
    assert abs(progress - 0.0) < 0.01
    print(f"PASS: progress at start = {progress}")


def test_progress_at_end_of_class():
    """Progress should be ~1.0 just before the class ends."""
    engine = make_engine()
    dt = make_dt(0, 17, 39)
    progress = engine.class_progress(dt)
    assert progress is not None
    assert abs(progress - 1.0) < 0.01
    print(f"PASS: progress at end = {progress}")


def test_format_duration():
    """Test format_duration helper."""
    assert format_duration(0) == "0m"
    assert format_duration(5) == "5m"
    assert format_duration(60) == "1h"
    assert format_duration(90) == "1h 30m"
    assert format_duration(125) == "2h 5m"
    print("PASS: format_duration")


def test_time_to_minutes():
    """Test _time_to_minutes helper."""
    assert _time_to_minutes("00:00") == 0
    assert _time_to_minutes("01:30") == 90
    assert _time_to_minutes("12:45") == 765
    assert _time_to_minutes("23:59") == 1439
    print("PASS: _time_to_minutes")


def test_validation_invalid_day():
    """Schedule with invalid day name should raise ScheduleError."""
    bad = {
        "timezone": "Asia/Jakarta",
        "days": {"mondey": [{"subject": "Test", "start": "10:00", "end": "11:00", "room": "A"}]},
    }
    fd, path = tempfile.mkstemp(suffix=".json")
    with os.fdopen(fd, "w") as f:
        json.dump(bad, f)
    try:
        import pytest
        with pytest.raises(ScheduleError):
            ScheduleEngine(path)
    except ImportError:
        raised = False
        try:
            ScheduleEngine(path)
        except ScheduleError:
            raised = True
        assert raised
    os.unlink(path)
    print("PASS: invalid day raises ScheduleError")


def test_validation_missing_subject():
    """Class with missing subject should raise ScheduleError."""
    bad = {
        "timezone": "Asia/Jakarta",
        "days": {"monday": [{"start": "10:00", "end": "11:00", "room": "A"}]},
    }
    fd, path = tempfile.mkstemp(suffix=".json")
    with os.fdopen(fd, "w") as f:
        json.dump(bad, f)
    try:
        raised = False
        try:
            ScheduleEngine(path)
        except ScheduleError:
            raised = True
        assert raised
    finally:
        os.unlink(path)
    print("PASS: missing subject raises ScheduleError")


def test_validation_end_before_start():
    """Class with end < start should raise ScheduleError."""
    bad = {
        "timezone": "Asia/Jakarta",
        "days": {"monday": [{"subject": "Test", "start": "11:00", "end": "10:00", "room": "A"}]},
    }
    fd, path = tempfile.mkstemp(suffix=".json")
    with os.fdopen(fd, "w") as f:
        json.dump(bad, f)
    try:
        raised = False
        try:
            ScheduleEngine(path)
        except ScheduleError:
            raised = True
        assert raised
    finally:
        os.unlink(path)
    print("PASS: end before start raises ScheduleError")


def test_validation_invalid_time():
    """Class with invalid time format should raise ScheduleError."""
    bad = {
        "timezone": "Asia/Jakarta",
        "days": {"monday": [{"subject": "Test", "start": "25:00", "end": "10:00", "room": "A"}]},
    }
    fd, path = tempfile.mkstemp(suffix=".json")
    with os.fdopen(fd, "w") as f:
        json.dump(bad, f)
    try:
        raised = False
        try:
            ScheduleEngine(path)
        except ScheduleError:
            raised = True
        assert raised
    finally:
        os.unlink(path)
    print("PASS: invalid time raises ScheduleError")


def test_today_classes_sorted():
    """Today's classes should be returned sorted by start time."""
    engine = make_engine()
    dt = make_dt(2, 10, 0)  # Wednesday
    classes = engine.classes_for_day("wednesday")
    times = [c["start"] for c in classes]
    assert times == sorted(times)
    print("PASS: classes sorted by start time")


def test_today_date_label():
    """today_key should return correct day."""
    engine = make_engine()
    # Just verify it returns a valid day key
    key = engine.today_key()
    assert key in DAY_NAMES
    print(f"PASS: today_key = {key} ({DAY_NAMES[key]})")


# --------------------------------------------------------------------------- #
# --at override tests
# --------------------------------------------------------------------------- #

def test_at_override_tuesday_1030_current():
    """--at 2026-09-15 10:30 -> current = Bahasa Inggris."""
    engine = make_engine()
    dt = parse_datetime_override("2026-09-15 10:30", TZ)
    current = engine.current_class(dt)
    assert current is not None
    assert current["subject"] == "Bahasa Inggris"
    print("PASS: --at 2026-09-15 10:30 -> current = Bahasa Inggris")


def test_at_override_tuesday_1200_next():
    """--at 2026-09-15 12:00 -> next = Budaya dan Karakter Tidar."""
    engine = make_engine()
    dt = parse_datetime_override("2026-09-15 12:00", TZ)
    current = engine.current_class(dt)
    assert current is None
    nxt = engine.next_class_with_day(dt)
    assert nxt is not None
    cls, day_key = nxt
    assert cls["subject"] == "Budaya dan Karakter Tidar"
    print("PASS: --at 2026-09-15 12:00 -> next = Budaha dan Karakter Tidar")


def test_at_override_wednesday_0730_current():
    """--at 2026-09-16 07:30 -> current = Ketentuan Umum Perpajakan."""
    engine = make_engine()
    dt = parse_datetime_override("2026-09-16 07:30", TZ)
    current = engine.current_class(dt)
    assert current is not None
    assert current["subject"] == "Ketentuan Umum Perpajakan"
    print("PASS: --at 2026-09-16 07:30 -> current = Ketentuan Umum Perpajakan")


def test_at_override_thursday_0935_next_5min():
    """--at 2026-09-17 09:35 -> next = Pengantar Teori Ekonomi in 5 min."""
    engine = make_engine()
    dt = parse_datetime_override("2026-09-17 09:35", TZ)
    current = engine.current_class(dt)
    assert current is None
    nxt = engine.next_class_with_day(dt)
    assert nxt is not None
    cls, day_key = nxt
    assert cls["subject"] == "Pengantar Teori Ekonomi"
    mins = engine.minutes_until_next(dt)
    assert mins == 5
    print("PASS: --at 2026-09-17 09:35 -> next = Pengantar Teori Ekonomi in 5m")


def test_at_override_thursday_1300_next_monday():
    """--at 2026-09-17 13:00 -> next = Pengantar Bisnis on Monday."""
    engine = make_engine()
    dt = parse_datetime_override("2026-09-17 13:00", TZ)
    current = engine.current_class(dt)
    assert current is None
    nxt = engine.next_class_with_day(dt)
    assert nxt is not None
    cls, day_key = nxt
    assert cls["subject"] == "Pengantar Bisnis"
    assert day_key == "monday"
    print("PASS: --at 2026-09-17 13:00 -> next = Pengantar Bisnis (Mon)")


def test_at_override_invalid_format():
    """parse_datetime_override should raise ScheduleError for bad format."""
    try:
        parse_datetime_override("invalid", TZ)
        assert False, "Should have raised ScheduleError"
    except ScheduleError:
        pass
    print("PASS: invalid --at format raises ScheduleError")


def test_at_override_normal_without_override():
    """Without --at, engine.now() should return real current time (not overridden)."""
    engine = make_engine()
    dt = engine.now()
    # dt should be very close to actual now
    from datetime import datetime as dt_mod
    real_now = dt_mod.now(TZ)
    diff = abs((dt - real_now).total_seconds())
    assert diff < 5, f"Engine now differs from real time by {diff}s"
    print("PASS: without --at, real current time is used")


# --------------------------------------------------------------------------- #
# Runner
# --------------------------------------------------------------------------- #

def run_all():
    tests = [
        test_monday_1400_next_pengantar_bisnis,
        test_monday_1600_current_pengantar_bisnis,
        test_monday_1800_no_more_classes_next_bahasa_inggris,
        test_tuesday_1030_current_bahasa_inggris,
        test_tuesday_1200_next_budaya_tidar,
        test_wednesday_0730_current_ketentuan_umum_perpajakan,
        test_wednesday_1225_next_pengantar_akuntansi_5min,
        test_wednesday_1300_current_pengantar_akuntansi,
        test_thursday_0800_current_matematika_bisnis,
        test_thursday_0935_next_pengantar_teori_ekonomi_5min,
        test_thursday_1300_no_more_classes_next_monday,
        test_friday_no_classes_next_monday,
        test_sunday_no_classes_next_monday,
        test_classes_finished_today,
        test_progress_during_class,
        test_progress_at_start_of_class,
        test_progress_at_end_of_class,
        test_format_duration,
        test_time_to_minutes,
        test_validation_invalid_day,
        test_validation_missing_subject,
        test_validation_end_before_start,
        test_validation_invalid_time,
        test_today_classes_sorted,
        test_today_date_label,
        test_at_override_tuesday_1030_current,
        test_at_override_tuesday_1200_next,
        test_at_override_wednesday_0730_current,
        test_at_override_thursday_0935_next_5min,
        test_at_override_thursday_1300_next_monday,
        test_at_override_invalid_format,
        test_at_override_normal_without_override,
    ]

    passed = 0
    failed = 0
    for test in tests:
        if test is None:
            continue
        try:
            test()
            passed += 1
        except AssertionError as exc:
            failed += 1
            print(f"FAIL: {test.__name__}: {exc}")
        except Exception as exc:
            failed += 1
            print(f"ERROR: {test.__name__}: {exc}")

    print(f"\n{'='*50}")
    print(f"Results: {passed} passed, {failed} failed, {passed + failed} total")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(run_all())
