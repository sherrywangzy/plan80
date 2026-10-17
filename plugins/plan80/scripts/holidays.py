#!/usr/bin/env python3
"""Public holidays for Plan80. Stdlib only, fully offline.

Two sources:
  1. US federal holidays, computed from the rules, with observed-date shifts
     (a Saturday holiday moves to Friday, a Sunday holiday moves to Monday).
  2. Any country, through an .ics file. Get one from Google Calendar (add the
     country's public holiday calendar, then Settings -> Export), or from
     timeanddate.com. List the file in config "holidays.ics_files".

Known limit: an observed holiday that falls across a year boundary (for example New
Year's Day on a Saturday, observed on 31 December) is not moved into the previous year.
"""
from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path


def _nth_weekday(year: int, month: int, weekday: int, n: int) -> date:
    """weekday: Monday=0 .. Sunday=6. n: 1-based occurrence."""
    first = date(year, month, 1)
    shift = (weekday - first.weekday()) % 7
    return first + timedelta(days=shift + 7 * (n - 1))


def _last_weekday(year: int, month: int, weekday: int) -> date:
    last = date(year + (month == 12), month % 12 + 1, 1) - timedelta(days=1)
    return last - timedelta(days=(last.weekday() - weekday) % 7)


def _observed(d: date) -> date:
    if d.weekday() == 5:  # Saturday -> Friday
        return d - timedelta(days=1)
    if d.weekday() == 6:  # Sunday -> Monday
        return d + timedelta(days=1)
    return d


def us_federal(year: int) -> dict[date, str]:
    out: dict[date, str] = {}
    fixed = {
        date(year, 1, 1): "New Year's Day",
        date(year, 6, 19): "Juneteenth",
        date(year, 7, 4): "Independence Day",
        date(year, 11, 11): "Veterans Day",
        date(year, 12, 25): "Christmas Day",
    }
    for day, name in fixed.items():
        out[_observed(day)] = name
    out[_nth_weekday(year, 1, 0, 3)] = "Martin Luther King Jr. Day"
    out[_nth_weekday(year, 2, 0, 3)] = "Presidents' Day"
    out[_last_weekday(year, 5, 0)] = "Memorial Day"
    out[_nth_weekday(year, 9, 0, 1)] = "Labor Day"
    out[_nth_weekday(year, 10, 0, 2)] = "Columbus Day"
    out[_nth_weekday(year, 11, 3, 4)] = "Thanksgiving Day"
    return out


def from_ics(path: str | Path) -> dict[date, str]:
    """Read all-day events from an .ics file as {date: name}."""
    text = Path(path).expanduser().read_text(encoding="utf-8", errors="replace")
    text = text.replace("\r\n ", "").replace("\n ", "")  # RFC 5545 line unfolding
    out: dict[date, str] = {}
    for block in text.split("BEGIN:VEVENT")[1:]:
        start = name = None
        for line in block.splitlines():
            if line.startswith("DTSTART"):
                value = line.split(":", 1)[1].strip()
                start = date(int(value[0:4]), int(value[4:6]), int(value[6:8]))
            elif line.startswith("SUMMARY"):
                name = line.split(":", 1)[1].strip().replace("\\,", ",")
        if start:
            out[start] = name or "Public holiday"
    return out


def holidays_for(cfg: dict, years: set[int]) -> dict[date, str]:
    """Combine the configured sources for the given years."""
    out: dict[date, str] = {}
    if cfg.get("country", "").upper() == "US":
        for year in years:
            out.update(us_federal(year))
    for path in cfg.get("ics_files", []):
        out.update({d: n for d, n in from_ics(path).items() if d.year in years})
    return out
