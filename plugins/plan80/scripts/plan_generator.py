#!/usr/bin/env python3
"""Plan80 generator: week config (JSON) -> plan.json for render.py.

Stdlib only. Deterministic, so every rule can be tested in evals/.

Priority tiers (lower number wins):
  0  constraints: work, family, sleep, me time, appointments, buffer. Never dropped.
  1  health. Never dropped. A clash is a config error.
  2  goals with a daily habit (trading practice)
  3  goals with a hard deadline (school)
  4  growth (YouTube, GitHub)

Rules applied in order:
  - Public holidays remove work blocks on that date.
  - Appointments carve work blocks: work is split around the appointment, not dropped.
  - Overlaps: the higher tier is kept and the lower tier is dropped, with a reason.
    A clash involving tier 0 or 1 raises PlanError, because the config is wrong.

Usage:
    python3 scripts/plan_generator.py ~/Plan80/life.json -o ~/Plan80/plan.json
"""
from __future__ import annotations

import argparse
import copy
import json
import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from holidays import holidays_for  # noqa: E402

DAYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
SICK_DROPPABLE_AREAS = {"trading", "school", "content"}
SICK_WALK_MIN = 20
SICK_REST_MIN = 60
REST_WINDOW = ("18:00", "22:30")
TARGET_WARN_RATIO = 0.9
TRANSITION_MIN = 15


class PlanError(Exception):
    """The config is invalid. Fix it before generating a plan."""


def to_min(value: str) -> int:
    """Accepts 'HH:MM' or 'YYYY-MM-DDTHH:MM' (the renderer's format)."""
    h, m = value.split("T")[-1].split(":")
    return int(h) * 60 + int(m)


def to_hhmm(mins: int) -> str:
    return f"{mins // 60:02d}:{mins % 60:02d}"


def overlaps(a: dict, b: dict) -> bool:
    return (
        a["date"] == b["date"]
        and to_min(a["start"]) < to_min(b["end"])
        and to_min(b["start"]) < to_min(a["end"])
    )


def allowed_overlap(a: dict, b: dict) -> bool:
    """A lunch workout may sit inside a work block, since it's a break from work."""
    return bool(
        (a.get("inside_work") and b["area"] == "work")
        or (b.get("inside_work") and a["area"] == "work")
    )


def expand(cfg: dict) -> list[dict]:
    """Turn recurring block templates into dated events, applying sick-day rules."""
    week_of = date.fromisoformat(cfg["week_of"])
    sick = set(cfg.get("sick_days", []))
    events = []
    for block in cfg["blocks"]:
        area = cfg["areas"].get(block["area"])
        if area is None:
            raise PlanError(f"block '{block['title']}' uses unknown area '{block['area']}'")
        for day in block["days"]:
            if day not in DAYS:
                raise PlanError(f"block '{block['title']}' has unknown day '{day}'")
            if to_min(block["end"]) <= to_min(block["start"]):
                raise PlanError(f"block '{block['title']}' ends before it starts")
            ev = {
                "title": block["title"],
                "area": block["area"],
                "tier": area["tier"],
                "calendar": area["calendar"],
                "kind": block.get("kind", "block"),
                "day": day,
                "date": (week_of + timedelta(days=DAYS.index(day))).isoformat(),
                "start": block["start"],
                "end": block["end"],
            }
            for key in ("note", "inside_work", "hold_on_work"):
                if key in block:
                    ev[key] = block[key]
            if day in sick:
                if block["area"] in SICK_DROPPABLE_AREAS:
                    ev["dropped_reason"] = "sick day"
                elif block.get("sick_walk"):
                    ev["title"] = "Easy walk (sick day)"
                    ev["end"] = to_hhmm(to_min(block["start"]) + SICK_WALK_MIN)
            events.append(ev)
    return events


def expand_appointments(cfg: dict) -> list[dict]:
    """Dated appointments. They are fixed, personal, and show as 'Personal hold' at work."""
    out = []
    for ap in cfg.get("appointments", []):
        area = cfg["areas"].get("appointments")
        if area is None:
            raise PlanError("config has appointments but no 'appointments' area")
        d = date.fromisoformat(ap["date"])
        if to_min(ap["end"]) <= to_min(ap["start"]):
            raise PlanError(f"appointment '{ap['title']}' ends before it starts")
        out.append({
            "title": ap["title"],
            "area": "appointments",
            "tier": area["tier"],
            "calendar": area["calendar"],
            "kind": "fixed",
            "day": DAYS[d.weekday()],
            "date": d.isoformat(),
            "start": ap["start"],
            "end": ap["end"],
            "hold_on_work": True,
        })
    return out


def carve_work(events: list[dict], appts: list[dict]) -> list[dict]:
    """Split work blocks around appointments. A block fully covered is dropped with a reason."""
    out = []
    for ev in events:
        if ev["area"] != "work" or ev.get("dropped_reason"):
            out.append(ev)
            continue
        segments = [(to_min(ev["start"]), to_min(ev["end"]))]
        for ap in appts:
            if ap["date"] != ev["date"]:
                continue
            a0, a1 = to_min(ap["start"]), to_min(ap["end"])
            nxt = []
            for s, e in segments:
                if a1 <= s or e <= a0:
                    nxt.append((s, e))
                    continue
                if s < a0:
                    nxt.append((s, a0))
                if a1 < e:
                    nxt.append((a1, e))
            segments = nxt
        if not segments:
            dropped = dict(ev, dropped_reason="replaced by an appointment")
            out.append(dropped)
            continue
        for s, e in segments:
            piece = dict(ev, start=to_hhmm(s), end=to_hhmm(e))
            out.append(piece)
    return out


def find_gap(busy: list[tuple[int, int]], lo: int, hi: int, need: int) -> int | None:
    """Return the start of the first free gap of at least `need` minutes inside [lo, hi]."""
    cursor = lo
    for start, end in sorted(busy):
        if end <= cursor:
            continue
        if min(start, hi) - cursor >= need:
            return cursor
        cursor = max(cursor, end)
        if cursor >= hi:
            return None
    return cursor if hi - cursor >= need else None


def add_sick_rest(cfg: dict, kept: list[dict], notes: list[str]) -> list[dict]:
    """On each sick day, add one rest block in the first free hour after 18:00."""
    week_of = date.fromisoformat(cfg["week_of"])
    buffer_area = cfg["areas"]["buffer"]
    out = list(kept)
    for day in cfg.get("sick_days", []):
        d = (week_of + timedelta(days=DAYS.index(day))).isoformat()
        busy = [(to_min(e["start"]), to_min(e["end"])) for e in out if e["date"] == d]
        start = find_gap(busy, to_min(REST_WINDOW[0]), to_min(REST_WINDOW[1]), SICK_REST_MIN)
        if start is None:
            notes.append(f"{day.title()}: no free hour for rest. Clear one block by hand.")
            continue
        out.append({
            "title": "Rest (sick day)",
            "area": "buffer",
            "tier": buffer_area["tier"],
            "calendar": buffer_area["calendar"],
            "kind": "buffer",
            "day": day,
            "date": d,
            "start": to_hhmm(start),
            "end": to_hhmm(start + SICK_REST_MIN),
        })
    return out


def resolve(events: list[dict]) -> tuple[list[dict], list[dict]]:
    """Keep blocks by tier. Return (kept, dropped)."""
    dropped = [e for e in events if e.get("dropped_reason")]
    candidates = sorted(
        (e for e in events if not e.get("dropped_reason")),
        key=lambda e: (e["tier"], e["date"], to_min(e["start"])),
    )
    kept: list[dict] = []
    for ev in candidates:
        clashes = [k for k in kept if overlaps(ev, k) and not allowed_overlap(ev, k)]
        if not clashes:
            kept.append(ev)
            continue
        other = clashes[0]
        if ev["tier"] <= 1:
            raise PlanError(
                f"{ev['date']} {ev['start']}-{ev['end']}: '{ev['title']}' (tier {ev['tier']}) "
                f"clashes with '{other['title']}'. Tier 0 and 1 blocks are never dropped, "
                f"so fix the config."
            )
        ev["dropped_reason"] = f"overlaps '{other['title']}' (tier {other['tier']})"
        dropped.append(ev)
    return kept, dropped


def hours_by_area(events: list[dict]) -> dict[str, float]:
    totals: dict[str, float] = {}
    for e in events:
        mins = to_min(e["end"]) - to_min(e["start"])
        totals[e["area"]] = totals.get(e["area"], 0.0) + mins / 60
    return totals


def build_notes(cfg: dict, kept: list[dict], dropped: list[dict], hours: dict[str, float],
                holidays: dict[date, str]) -> list[str]:
    notes: list[str] = []
    for d, name in sorted(holidays.items()):
        notes.append(f"Public holiday {d:%a %b %d}: {name}. Work blocks removed.")
    for ev in dropped:
        notes.append(f"Dropped {ev['day'].title()} '{ev['title']}' ({ev['dropped_reason']}).")
    for key, area in cfg["areas"].items():
        target = area.get("target_hours")
        if target and hours.get(key, 0.0) < target * TARGET_WARN_RATIO:
            notes.append(f"{area['label']}: {hours.get(key, 0.0):g}h planned, target {target:g}h.")
        floor = area.get("min_hours")
        if floor and hours.get(key, 0.0) < floor:
            notes.append(f"{area['label']}: below the {floor:g}h minimum.")
    lights_out = to_min(cfg.get("sleep", {}).get("lights_out", "22:30"))
    for e in kept:
        if to_min(e["end"]) > lights_out:
            notes.append(f"'{e['title']}' on {e['day'].title()} runs past lights-out.")
    by_day: dict[str, list[dict]] = {}
    for e in kept:
        by_day.setdefault(e["date"], []).append(e)
    for evs in by_day.values():
        evs = sorted(evs, key=lambda e: to_min(e["start"]))
        for a, b in zip(evs, evs[1:]):
            gap = to_min(b["start"]) - to_min(a["end"])
            back_to_back = gap == 0 or allowed_overlap(a, b)
            if 0 < gap < TRANSITION_MIN and not back_to_back and a["area"] != b["area"]:
                notes.append(f"{a['day'].title()}: only {gap} min between '{a['title']}' and '{b['title']}'.")
    notes.extend(cfg.get("notes", []))
    return notes


def generate(cfg: dict) -> dict:
    """Config dict -> plan dict (the schema render.py reads, plus `dropped` and `hours`)."""
    cfg = copy.deepcopy(cfg)
    week_of = date.fromisoformat(cfg["week_of"])
    week_dates = {(week_of + timedelta(days=i)).isoformat() for i in range(7)}
    holidays = {
        d: name for d, name in holidays_for(cfg.get("holidays", {}), {week_of.year}).items()
        if d.isoformat() in week_dates
    }

    appts = expand_appointments(cfg)
    events = carve_work(expand(cfg), appts)
    for ev in events:
        if ev["area"] == "work" and ev["date"] in {d.isoformat() for d in holidays} and not ev.get("dropped_reason"):
            ev["dropped_reason"] = f"public holiday: {holidays[date.fromisoformat(ev['date'])]}"

    kept, dropped = resolve(events + appts)
    sick_notes: list[str] = []
    if cfg.get("sick_days"):
        kept = add_sick_rest(cfg, kept, sick_notes)
    kept.sort(key=lambda e: (e["date"], to_min(e["start"])))
    hours = hours_by_area(kept)
    notes = sick_notes + build_notes(
        cfg, kept, dropped, hours,
        {d: n for d, n in holidays.items()},
    )

    areas = {}
    for key, area in cfg["areas"].items():
        areas[key] = dict(area)

    return {
        "title": cfg.get("title", "Plan80 week"),
        "week_of": cfg["week_of"],
        "timezone": cfg.get("timezone", "America/Los_Angeles"),
        "mode": "sick" if cfg.get("sick_days") else "normal",
        "areas": areas,
        "events": [
            {
                **{k: v for k, v in e.items() if k not in ("tier", "dropped_reason", "start", "end")},
                "start": f"{e['date']}T{e['start'][-5:]}",
                "end": f"{e['date']}T{e['end'][-5:]}",
            }
            for e in kept
        ],
        "notes": notes,
        "dropped": [
            {"title": e["title"], "area": e["area"], "date": e["date"], "reason": e["dropped_reason"]}
            for e in dropped
        ],
        "hours": {k: round(v, 2) for k, v in hours.items()},
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("config", type=Path)
    ap.add_argument("-o", "--out", type=Path, default=Path("plan.json"))
    args = ap.parse_args()
    try:
        cfg = json.loads(args.config.read_text(encoding="utf-8"))
        plan = generate(cfg)
    except (PlanError, KeyError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    args.out.write_text(json.dumps(plan, indent=2), encoding="utf-8")
    print(f"wrote {args.out}: {len(plan['events'])} events, {len(plan['dropped'])} dropped")
    for note in plan["notes"]:
        print(f" - {note}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
