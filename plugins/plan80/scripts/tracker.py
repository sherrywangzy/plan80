#!/usr/bin/env python3
"""Plan80 progress tracking: log activity, check projects against due dates, recommend next week.

Stdlib only. The activity log is JSON lines, one entry per session:
    {"date": "2026-10-20", "area": "content", "minutes": 90, "project": "plan80-launch", "note": "script"}

Commands:
    python3 scripts/tracker.py log   --config ~/Plan80/life.json --area content --minutes 90 --project plan80-launch
    python3 scripts/tracker.py status --config ~/Plan80/life.json [--today 2026-10-30] [--window 14]

Verdicts for projects:
    done       all estimated hours logged
    overdue    past the due date with hours remaining
    on_track   recent pace meets what the due date needs
    behind     the plan allows the pace needed, but actual pace is short
    plan_gap   the plan itself cannot reach the due date at the needed pace

Recommendation rules (never reduce health or school automatically):
    health     keep the number of sessions; change the time or length instead
    school     below target: suggest a school checkpoint, never an automatic cut
    other      below 70% of target: lower the target to the actual pace
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import date, timedelta
from pathlib import Path

DEFAULT_LOG = Path("~/Plan80/log.jsonl").expanduser()
ADHERENCE_LOW = 0.7
NEVER_REDUCE = {"health"}
CHECKPOINT = {"school"}


class TrackerError(Exception):
    pass


def load_log(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def append_entry(path: Path, cfg: dict, area: str, minutes: int, day: str | None,
                 project: str | None, note: str | None) -> dict:
    if area not in cfg["areas"]:
        raise TrackerError(f"unknown area '{area}'. Use one of: {', '.join(cfg['areas'])}")
    if minutes <= 0:
        raise TrackerError("minutes must be positive")
    entry_date = date.fromisoformat(day) if day else date.today()
    if project and project not in {p["id"] for p in cfg.get("projects", [])}:
        raise TrackerError(f"unknown project '{project}'")
    entry = {"date": entry_date.isoformat(), "area": area, "minutes": minutes}
    if project:
        entry["project"] = project
    if note:
        entry["note"] = note
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(entry) + "\n")
    return entry


def analyze(cfg: dict, log: list[dict], today: date, window: int = 14) -> dict:
    weeks = window / 7
    start = today - timedelta(days=window)
    recent = [e for e in log if start < date.fromisoformat(e["date"]) <= today]
    areas = cfg["areas"]

    area_rows = []
    for key, area in areas.items():
        target = area.get("target_hours")
        if not target:
            continue
        actual = sum(e["minutes"] for e in recent if e["area"] == key) / 60 / weeks
        area_rows.append({"area": key, "label": area["label"], "target": target,
                          "actual": round(actual, 2), "ratio": round(actual / target, 2)})

    project_rows = []
    for p in cfg.get("projects", []):
        done = sum(e["minutes"] for e in log if e.get("project") == p["id"]) / 60
        remaining = max(0.0, p["estimate_hours"] - done)
        due = date.fromisoformat(p["due"])
        recent_done = sum(e["minutes"] for e in recent if e.get("project") == p["id"]) / 60
        actual_pace = recent_done / weeks
        planned_pace = areas.get(p["area"], {}).get("target_hours", 0) or 0
        row = {"id": p["id"], "name": p["name"], "due": p["due"], "remaining": round(remaining, 2),
               "actual_pace": round(actual_pace, 2), "planned_pace": planned_pace}
        days_left = (due - today).days
        if remaining == 0:
            row.update(verdict="done", needed_pace=0.0)
        elif days_left <= 0:
            row.update(verdict="overdue", needed_pace=None)
        else:
            needed = remaining / (days_left / 7)
            row["needed_pace"] = round(needed, 2)
            if actual_pace >= needed:
                row["verdict"] = "on_track"
            elif planned_pace >= needed:
                row["verdict"] = "behind"
            else:
                row["verdict"] = "plan_gap"
            row["forecast_finish"] = (
                (today + timedelta(days=remaining / actual_pace * 7)).isoformat()
                if actual_pace > 0 else None
            )
            row["planned_finish"] = (
                (today + timedelta(days=remaining / planned_pace * 7)).isoformat()
                if planned_pace > 0 else None
            )
        project_rows.append(row)

    recs = recommend(areas, area_rows, project_rows)
    return {"today": today.isoformat(), "window_days": window, "log_entries": len(recent),
            "areas": area_rows, "projects": project_rows, "recommendations": recs}


def recommend(areas: dict, area_rows: list[dict], project_rows: list[dict]) -> list[str]:
    recs = []
    for row in area_rows:
        key, label = row["area"], row["label"]
        if row["ratio"] >= ADHERENCE_LOW:
            continue
        if key in NEVER_REDUCE:
            recs.append(
                f"{label}: {row['actual']:g}h a week against a {row['target']:g}h target. "
                "Keep the number of sessions; change the time or length instead of dropping it."
            )
        elif key in CHECKPOINT:
            recs.append(
                f"{label}: {row['actual']:g}h a week against {row['target']:g}h. "
                "Book a school checkpoint with this week's deadlines before changing anything else."
            )
        else:
            recs.append(
                f"{label}: {row['actual']:g}h a week against {row['target']:g}h. "
                f"Lower next week's target to about {max(row['actual'], 0.5):g}h, or move the work to a day with room."
            )
    for p in project_rows:
        if p["verdict"] == "plan_gap":
            recs.append(
                f"{p['name']}: needs {p['needed_pace']:g}h a week, but its area only has "
                f"{p['planned_pace']:g}h. Move the due date to {p['planned_finish']}, "
                "or add the missing hours to the plan."
            )
        elif p["verdict"] == "overdue":
            recs.append(f"{p['name']}: past its due date with {p['remaining']:g}h left. Set a new date.")
        elif p["verdict"] == "behind":
            recs.append(
                f"{p['name']}: the plan allows {p['needed_pace']:g}h a week, but you're at "
                f"{p['actual_pace']:g}h. Protect the next block before adding more work."
            )
    if not recs:
        recs.append("Everything is on track. Keep next week's plan as it is.")
    return recs


def format_report(result: dict) -> str:
    lines = [f"Progress as of {result['today']} (last {result['window_days']} days, "
             f"{result['log_entries']} log entries)", ""]
    lines.append("Areas, weekly hours against target:")
    for r in result["areas"]:
        lines.append(f"  {r['label']}: {r['actual']:g}h of {r['target']:g}h ({r['ratio'] * 100:.0f}%)")
    lines.append("")
    lines.append("Projects:")
    for p in result["projects"]:
        if p["verdict"] == "done":
            lines.append(f"  {p['name']}: done")
            continue
        extra = ""
        if p.get("forecast_finish"):
            extra = f", forecast finish {p['forecast_finish']}"
        lines.append(
            f"  {p['name']}: {p['verdict'].replace('_', ' ')}. {p['remaining']:g}h left, "
            f"due {p['due']}{extra}"
        )
    lines.append("")
    lines.append("For next week:")
    lines.extend(f"  - {r}" for r in result["recommendations"])
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    lg = sub.add_parser("log", help="record a work session")
    lg.add_argument("--config", type=Path, required=True)
    lg.add_argument("--log", type=Path, default=DEFAULT_LOG)
    lg.add_argument("--area", required=True)
    lg.add_argument("--minutes", type=int, required=True)
    lg.add_argument("--project")
    lg.add_argument("--note")
    lg.add_argument("--day", help="YYYY-MM-DD (default: today)")

    st = sub.add_parser("status", help="progress, forecast and next-week recommendations")
    st.add_argument("--config", type=Path, required=True)
    st.add_argument("--log", type=Path, default=DEFAULT_LOG)
    st.add_argument("--today", help="YYYY-MM-DD (default: today)")
    st.add_argument("--window", type=int, default=14)

    args = ap.parse_args()
    try:
        cfg = json.loads(args.config.read_text(encoding="utf-8"))
        if args.cmd == "log":
            entry = append_entry(args.log, cfg, args.area, args.minutes, args.day, args.project, args.note)
            print(f"logged {entry['minutes']} min to {entry['area']} on {entry['date']}")
            return 0
        today = date.fromisoformat(args.today) if args.today else date.today()
        result = analyze(cfg, load_log(args.log), today, args.window)
        print(format_report(result))
        return 0
    except (TrackerError, KeyError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
