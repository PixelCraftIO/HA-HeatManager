"""Tests for the pure schedule logic."""

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from custom_components.heatmanager.schedule import (
    next_change,
    next_target,
    normalize_week,
    parse_time,
    profile_target,
)

TZ = ZoneInfo("Europe/Berlin")
# 2026-11-16 is a Monday
MONDAY = datetime(2026, 11, 16, 0, 0, tzinfo=TZ)

PROFILE = {
    "base_temp": 17.0,
    "week": normalize_week(
        {
            "monday": [
                {"from": "06:00", "to": "07:30", "temp": 20},
                {"from": "14:00", "to": "20:30", "temp": 21},
            ],
            "saturday": [{"from": "22:00", "to": "24:00", "temp": 19}],
        }
    ),
}


def at(day_offset: int, hour: int, minute: int = 0) -> datetime:
    return MONDAY.replace(day=MONDAY.day + day_offset, hour=hour, minute=minute)


def test_parse_time() -> None:
    assert parse_time("06:30") == 390
    assert parse_time("24:00") == 1440
    assert parse_time("7:05:00") == 425
    for bad in ("25:00", "12:61", "abc"):
        with pytest.raises(ValueError):
            parse_time(bad)


def test_normalize_week_fills_all_days_and_sorts() -> None:
    week = normalize_week(
        {"monday": [{"from": "18:00", "to": "00:00", "temp": 21}, {"from": "06:00", "to": "07:00", "temp": 20}]}
    )
    assert set(week) == {"monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"}
    assert week["monday"][0]["from"] == "06:00"
    assert week["monday"][1]["to"] == "24:00"


@pytest.mark.parametrize(
    "week",
    [
        {"monday": [{"from": "06:00", "to": "08:00", "temp": 20}, {"from": "07:00", "to": "09:00", "temp": 20}]},
        {"monday": [{"from": "08:00", "to": "07:00", "temp": 20}]},
        {"monday": [{"from": "08:00", "to": "09:00", "temp": 50}]},
        {"funday": []},
    ],
)
def test_normalize_week_rejects_invalid(week) -> None:
    with pytest.raises(ValueError):
        normalize_week(week)


def test_profile_target() -> None:
    assert profile_target(PROFILE, at(0, 5, 59)) == (17.0, False)
    assert profile_target(PROFILE, at(0, 6, 0)) == (20.0, True)
    assert profile_target(PROFILE, at(0, 7, 30)) == (17.0, False)
    assert profile_target(PROFILE, at(0, 15)) == (21.0, True)
    assert profile_target(PROFILE, at(5, 23, 59)) == (19.0, True)
    assert profile_target(PROFILE, at(1, 12)) == (17.0, False)


def test_next_change() -> None:
    assert next_change(PROFILE, at(0, 5)) == at(0, 6)
    assert next_change(PROFILE, at(0, 6)) == at(0, 7, 30)
    assert next_change(PROFILE, at(0, 21)) == at(5, 22)
    # end of Saturday block is Sunday midnight
    assert next_change(PROFILE, at(5, 22, 30)) == at(6, 0)


def test_next_change_empty_profile() -> None:
    assert next_change({"base_temp": 17, "week": normalize_week({})}, at(0, 5)) is None


def test_next_target_skips_boundaries_without_change() -> None:
    profile = {
        "base_temp": 17.0,
        "week": normalize_week(
            {"monday": [{"from": "06:00", "to": "08:00", "temp": 20}, {"from": "08:00", "to": "10:00", "temp": 20}]}
        ),
    }
    assert next_target(profile, at(0, 7)) == (at(0, 10), 17.0)
