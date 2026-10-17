#!/usr/bin/env python3
"""Render a Plan80 plan.json into a visual week (HTML) and one .ics per calendar.

Usage:
    python3 render.py plan.json --out ./out

Zero dependencies: Python 3.9+ standard library only.
"""

from __future__ import annotations

import argparse
import hashlib
import webbrowser
import html
import json
import sys
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

CALENDARS = ("work", "personal", "family")
KINDS = ("fixed", "protected", "block", "buffer")
DAY_START_MIN = 6 * 60      # grid starts 6:00
DAY_END_MIN = 23 * 60       # grid ends 23:00
PX_PER_MIN = 0.9


# ---------------------------------------------------------------- loading


class PlanError(Exception):
    pass


def parse_dt(value: str, field: str) -> datetime:
    try:
        return datetime.strptime(value, "%Y-%m-%dT%H:%M")
    except (TypeError, ValueError):
        raise PlanError(f"{field}: expected YYYY-MM-DDTHH:MM, got {value!r}")


def load_plan(path: Path) -> dict:
    plan = json.loads(path.read_text(encoding="utf-8"))
    areas = plan.get("areas") or {}
    if not areas:
        raise PlanError("plan has no 'areas'")
    week_of = date.fromisoformat(plan["week_of"])
    events = []
    for i, ev in enumerate(plan.get("events", [])):
        where = f"events[{i}] ({ev.get('title', '?')})"
        if ev.get("area") not in areas:
            raise PlanError(f"{where}: unknown area {ev.get('area')!r}")
        if ev.get("calendar") not in CALENDARS:
            raise PlanError(f"{where}: calendar must be one of {CALENDARS}")
        if ev.get("kind", "block") not in KINDS:
            raise PlanError(f"{where}: kind must be one of {KINDS}")
        start = parse_dt(ev.get("start"), f"{where}.start")
        end = parse_dt(ev.get("end"), f"{where}.end")
        if end <= start:
            raise PlanError(f"{where}: end is not after start")
        if start.date() != end.date():
            raise PlanError(f"{where}: events must start and end on the same day")
        events.append({**ev, "kind": ev.get("kind", "block"), "_start": start, "_end": end})
    events.sort(key=lambda e: (e["_start"], e["_end"]))
    plan["_week_of"] = week_of
    plan["_events"] = events
    return plan


# ---------------------------------------------------------------- checks


def minutes(ev: dict) -> int:
    return int((ev["_end"] - ev["_start"]).total_seconds() // 60)


def find_conflicts(events: list[dict]) -> list[str]:
    """Overlaps are conflicts, except a block tagged inside_work inside a work event."""
    out = []
    by_day = defaultdict(list)
    for ev in events:
        by_day[ev["_start"].date()].append(ev)
    for day, evs in sorted(by_day.items()):
        for i, a in enumerate(evs):
            for b in evs[i + 1:]:
                if b["_start"] >= a["_end"]:
                    continue
                pair = (a, b)
                if any(x.get("inside_work") for x in pair) and any(x["area"] == "work" for x in pair):
                    continue
                out.append(
                    f"{day:%a %b %d}: '{a['title']}' {a['_start']:%H:%M}-{a['_end']:%H:%M} "
                    f"overlaps '{b['title']}' {b['_start']:%H:%M}-{b['_end']:%H:%M}"
                )
    return out


def area_hours(events: list[dict]) -> dict[str, float]:
    totals: dict[str, float] = defaultdict(float)
    for ev in events:
        if ev.get("inside_work") and ev["area"] != "work":
            pass  # counts for its own area; work hours are not reduced (it's a lunch break)
        totals[ev["area"]] += minutes(ev) / 60
    return dict(totals)


def capacity_warnings(plan: dict, hours: dict[str, float]) -> list[str]:
    out = []
    for key, area in plan["areas"].items():
        h = hours.get(key, 0.0)
        label = area.get("label", key)
        tgt, lo, hi = area.get("target_hours"), area.get("min_hours"), area.get("max_hours")
        if lo is not None and h < lo:
            out.append(f"{label}: {h:.1f}h is below the minimum of {lo}h")
        if hi is not None and h > hi:
            out.append(f"{label}: {h:.1f}h is over the cap of {hi}h")
        if tgt and h < tgt * 0.75:
            out.append(f"{label}: {h:.1f}h planned vs {tgt}h target")
    # late nights
    for ev in plan["_events"]:
        if ev["kind"] in ("block",) and ev["_end"].hour * 60 + ev["_end"].minute > 22 * 60 + 30:
            out.append(f"'{ev['title']}' on {ev['_start']:%a} runs past 22:30")
    return out


# ---------------------------------------------------------------- ics


VTIMEZONE_LA = """BEGIN:VTIMEZONE
TZID:America/Los_Angeles
BEGIN:DAYLIGHT
TZOFFSETFROM:-0800
TZOFFSETTO:-0700
TZNAME:PDT
DTSTART:19700308T020000
RRULE:FREQ=YEARLY;BYMONTH=3;BYDAY=2SU
END:DAYLIGHT
BEGIN:STANDARD
TZOFFSETFROM:-0700
TZOFFSETTO:-0800
TZNAME:PST
DTSTART:19701101T020000
RRULE:FREQ=YEARLY;BYMONTH=11;BYDAY=1SU
END:STANDARD
END:VTIMEZONE"""


def ics_escape(text: str) -> str:
    return (
        str(text).replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,").replace("\n", "\\n")
    )


def fold(line: str) -> str:
    """Fold to 75 octets per RFC 5545."""
    raw = line.encode("utf-8")
    if len(raw) <= 75:
        return line
    parts, cur = [], b""
    for ch in line:
        b = ch.encode("utf-8")
        limit = 75 if not parts else 74
        if len(cur) + len(b) > limit:
            parts.append(cur.decode("utf-8"))
            cur = b""
        cur += b
    parts.append(cur.decode("utf-8"))
    return "\r\n ".join(parts)


def uid_for(ev: dict, calendar: str, suffix: str = "") -> str:
    key = f"{calendar}|{ev['title']}|{ev['_start']:%Y%m%dT%H%M}|{suffix}"
    return hashlib.sha1(key.encode()).hexdigest()[:20] + "@plan80"


def build_ics(plan: dict, calendar: str) -> str:
    tz = plan.get("timezone", "America/Los_Angeles")
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//plan80//EN",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        f"X-WR-CALNAME:{ics_escape(calendar.title())} - {ics_escape(plan.get('title', 'Week plan'))}",
        f"X-WR-TIMEZONE:{tz}",
    ]
    if tz == "America/Los_Angeles":
        lines += VTIMEZONE_LA.split("\n")

    def add(ev: dict, title: str, description: str, uid: str, transp: str = "OPAQUE") -> None:
        lines.extend([
            "BEGIN:VEVENT",
            f"UID:{uid}",
            f"DTSTAMP:{stamp}",
            f"DTSTART;TZID={tz}:{ev['_start']:%Y%m%dT%H%M%S}",
            f"DTEND;TZID={tz}:{ev['_end']:%Y%m%dT%H%M%S}",
            f"SUMMARY:{ics_escape(title)}",
        ])
        if description:
            lines.append(f"DESCRIPTION:{ics_escape(description)}")
        lines.extend([f"TRANSP:{transp}", "END:VEVENT"])

    areas = plan["areas"]
    for ev in plan["_events"]:
        if ev["calendar"] == calendar:
            label = areas[ev["area"]].get("label", ev["area"])
            desc = " | ".join(x for x in (label, ev.get("note", "")) if x)
            transp = "TRANSPARENT" if ev["kind"] == "buffer" else "OPAQUE"
            add(ev, ev["title"], desc, uid_for(ev, calendar), transp)
        elif calendar == "work" and ev.get("hold_on_work"):
            # Privacy: never leak the real title into the work calendar.
            add(ev, "Personal hold", "", uid_for(ev, calendar, "hold"))
    lines.append("END:VCALENDAR")
    return "\r\n".join(fold(l) for l in lines) + "\r\n"


# ---------------------------------------------------------------- html


def lanes_for_day(evs: list[dict]) -> list[tuple[dict, int, int]]:
    """Assign side-by-side lanes to overlapping events. Returns (event, lane, lane_count)."""
    result, cluster, cluster_end, lane_ends = [], [], None, []

    def flush():
        n = max((lane for _, lane in cluster), default=-1) + 1
        result.extend((ev, lane, n) for ev, lane in cluster)

    for ev in sorted(evs, key=lambda e: (e["_start"], -minutes(e))):
        if cluster_end is not None and ev["_start"] >= cluster_end:
            flush()
            cluster, lane_ends, cluster_end = [], [], None
        for lane, lane_end in enumerate(lane_ends):
            if ev["_start"] >= lane_end:
                lane_ends[lane] = ev["_end"]
                break
        else:
            lane = len(lane_ends)
            lane_ends.append(ev["_end"])
        cluster.append((ev, lane))
        cluster_end = ev["_end"] if cluster_end is None else max(cluster_end, ev["_end"])
    flush()
    return result


def fmt_h(h: float) -> str:
    return f"{h:.1f}".rstrip("0").rstrip(".") + "h"


def build_html(plan: dict, hours: dict[str, float], conflicts: list[str], warnings: list[str]) -> str:
    e = html.escape
    areas = plan["areas"]
    week_of = plan["_week_of"]
    days = [week_of + timedelta(days=i) for i in range(7)]
    grid_h = (DAY_END_MIN - DAY_START_MIN) * PX_PER_MIN
    sick = plan.get("mode") == "sick"

    by_day = defaultdict(list)
    for ev in plan["_events"]:
        by_day[ev["_start"].date()].append(ev)

    # hour gutter
    gutter = []
    for m in range(DAY_START_MIN, DAY_END_MIN + 1, 60):
        top = (m - DAY_START_MIN) * PX_PER_MIN
        h = m // 60
        label = f"{(h - 1) % 12 + 1}{'a' if h < 12 else 'p'}"
        gutter.append(f'<div class="hr" style="top:{top:.0f}px"><span>{label}</span></div>')

    # day columns
    cols = []
    for d in days:
        blocks = []
        for ev, lane, n in lanes_for_day(by_day.get(d, [])):
            s = ev["_start"].hour * 60 + ev["_start"].minute
            t = ev["_end"].hour * 60 + ev["_end"].minute
            s, t = max(s, DAY_START_MIN), min(t, DAY_END_MIN)
            if t <= s:
                continue
            top = (s - DAY_START_MIN) * PX_PER_MIN
            height = max((t - s) * PX_PER_MIN - 2, 12)
            width = 100 / n
            color = areas[ev["area"]].get("color", "#888")
            short = (t - s) < 40
            cal_tag = {"work": "W", "personal": "P", "family": "F"}[ev["calendar"]]
            hold = ' <span class="hold" title="Also a busy hold on the work calendar">◆</span>' if ev.get("hold_on_work") else ""
            note = f'<div class="note">{e(ev["note"])}</div>' if ev.get("note") and not short else ""
            time_txt = f'{ev["_start"]:%-I:%M}–{ev["_end"]:%-I:%M}'
            blocks.append(
                f'<div class="ev k-{ev["kind"]}{" short" if short else ""}" '
                f'style="top:{top:.0f}px;height:{height:.0f}px;left:calc({lane * width:.3f}% + 2px);'
                f'width:calc({width:.3f}% - 4px);--c:{color}" '
                f'title="{e(ev["title"])} · {time_txt} · {e(areas[ev["area"]].get("label", ev["area"]))} · {ev["calendar"]} calendar">'
                f'<div class="t">{e(ev["title"])}{hold}</div>'
                f'<div class="m">{time_txt} · <b>{cal_tag}</b></div>{note}</div>'
            )
        is_weekend = d.weekday() >= 5
        cols.append(
            f'<div class="col{" wk" if is_weekend else ""}">'
            f'<div class="dh"><span class="dn">{d:%a}</span><span class="dd">{d:%b} {d.day}</span></div>'
            f'<div class="body" style="height:{grid_h:.0f}px">{"".join(blocks)}</div></div>'
        )

    # hours vs target
    rows = []
    for key, area in areas.items():
        h = hours.get(key, 0.0)
        tgt = area.get("target_hours") or area.get("min_hours")
        cap = area.get("max_hours")
        if tgt:
            pct = min(h / tgt, 1.5) / 1.5 * 100
            mark = 1 / 1.5 * 100
            goal_txt = f"{'min ' if area.get('min_hours') and not area.get('target_hours') else ''}{fmt_h(tgt)}"
            if cap:
                goal_txt += f" · cap {fmt_h(cap)}"
            state = "ok" if h >= tgt * 0.9 and (not cap or h <= cap) else "low" if h < tgt * 0.9 else "over"
        else:
            pct, mark, goal_txt, state = None, None, "", "none"
        bar = (
            f'<div class="bar"><div class="fill" style="width:{pct:.1f}%;--c:{area.get("color")}"></div>'
            f'<div class="goal" style="left:{mark:.1f}%"></div></div>' if pct is not None else '<div class="bar empty"></div>'
        )
        rows.append(
            f'<div class="row s-{state}"><span class="sw" style="--c:{area.get("color")}"></span>'
            f'<span class="lbl">{e(area.get("label", key))}</span>{bar}'
            f'<span class="num">{fmt_h(h)}</span><span class="goaltxt">{e(goal_txt)}</span></div>'
        )

    def listing(items, cls, title):
        if not items:
            return ""
        lis = "".join(f"<li>{e(x)}</li>" for x in items)
        return f'<section class="{cls}"><h3>{title}</h3><ul>{lis}</ul></section>'

    notes_html = listing(plan.get("notes", []), "notes", "Notes")
    conflict_html = listing(conflicts, "bad", "Conflicts to fix")
    warn_html = listing(warnings, "warn", "Heads-up")

    total_planned = sum(minutes(ev) for ev in plan["_events"] if ev["kind"] == "block") / 60
    buffer_h = sum(minutes(ev) for ev in plan["_events"] if ev["kind"] == "buffer") / 60
    me_key = next((k for k in areas if k in ("me", "me_time", "rest")), None)
    me_h = hours.get(me_key, 0.0) if me_key else 0.0

    banner = (
        '<div class="banner">Sick mode: work, kids and rest only. Everything else moved or skipped this week.</div>'
        if sick else ""
    )

    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{e(plan.get("title", "Week plan"))}</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,500;9..144,600&family=Inter:wght@400;500;600&display=swap" rel="stylesheet">
<style>
:root {{
  --bg:#F6F3EE; --panel:#FFFFFF; --ink:#1E1D1B; --muted:#6E6A64; --line:#E6E1D8; --line2:#F0ECE5;
  --wk:#FBF9F5; --bad:#B4372F; --warn:#9A6B00; --shadow:0 1px 2px rgba(30,29,27,.06),0 4px 16px rgba(30,29,27,.05);
}}
@media (prefers-color-scheme: dark) {{
  :root:not([data-theme="light"]) {{
    --bg:#151513; --panel:#1E1E1B; --ink:#EDEAE4; --muted:#9C978F; --line:#2E2D29; --line2:#262522;
    --wk:#1A1A18; --bad:#E3786F; --warn:#D9A83A; --shadow:none;
  }}
}}
:root[data-theme="dark"] {{
  --bg:#151513; --panel:#1E1E1B; --ink:#EDEAE4; --muted:#9C978F; --line:#2E2D29; --line2:#262522;
  --wk:#1A1A18; --bad:#E3786F; --warn:#D9A83A; --shadow:none;
}}
* {{ box-sizing:border-box; }}
body {{ margin:0; background:var(--bg); color:var(--ink); font:14px/1.45 Inter,system-ui,sans-serif; }}
.wrap {{ max-width:1320px; margin:0 auto; padding:28px 16px 48px; }}
header {{ display:flex; flex-wrap:wrap; align-items:flex-end; justify-content:space-between; gap:16px; margin-bottom:18px; }}
h1 {{ font-family:Fraunces,Georgia,serif; font-weight:600; font-size:34px; letter-spacing:-.01em; margin:0; }}
.sub {{ color:var(--muted); margin-top:4px; }}
.kpis {{ display:flex; gap:10px; flex-wrap:wrap; }}
.kpi {{ background:var(--panel); border:1px solid var(--line); border-radius:12px; padding:8px 14px; min-width:104px; }}
.kpi b {{ display:block; font-family:Fraunces,Georgia,serif; font-size:22px; font-weight:600; }}
.kpi span {{ color:var(--muted); font-size:12px; }}
.banner {{ background:#FCE9E6; color:#7A231C; border:1px solid #F2C6BF; padding:10px 14px; border-radius:10px; margin-bottom:14px; font-weight:500; }}
@media (prefers-color-scheme: dark) {{ :root:not([data-theme="light"]) .banner {{ background:#3A1E1B; color:#F4C1BA; border-color:#5A2C27; }} }}
.layout {{ display:grid; grid-template-columns:minmax(0,1fr) 300px; gap:18px; align-items:start; }}
@media (max-width:1000px) {{ .layout {{ grid-template-columns:1fr; }} }}
.cal {{ background:var(--panel); border:1px solid var(--line); border-radius:16px; box-shadow:var(--shadow); overflow-x:auto; }}
.grid {{ display:grid; grid-template-columns:44px repeat(7, minmax(118px,1fr)); min-width:880px; position:relative; }}
.gut {{ position:relative; margin-top:52px; }}
.hr {{ position:absolute; left:0; right:0; }}
.hr span {{ position:absolute; top:-8px; right:6px; font-size:11px; color:var(--muted); }}
.col {{ border-left:1px solid var(--line); }}
.col.wk .body {{ background:var(--wk); }}
.dh {{ height:52px; display:flex; flex-direction:column; justify-content:center; padding:0 10px; border-bottom:1px solid var(--line); }}
.dn {{ font-weight:600; }}
.dd {{ color:var(--muted); font-size:12px; }}
.body {{ position:relative; background-image:repeating-linear-gradient(to bottom, transparent 0, transparent {60 * PX_PER_MIN - 1:.0f}px, var(--line2) {60 * PX_PER_MIN - 1:.0f}px, var(--line2) {60 * PX_PER_MIN:.0f}px); }}
.ev {{ position:absolute; border-radius:7px; padding:4px 6px; overflow:hidden; font-size:12px; line-height:1.25;
       background:color-mix(in srgb, var(--c) 18%, var(--panel)); border-left:3px solid var(--c); color:var(--ink); }}
.ev.k-fixed {{ background:color-mix(in srgb, var(--c) 30%, var(--panel)); }}
.ev.k-protected {{ background:repeating-linear-gradient(135deg, color-mix(in srgb, var(--c) 20%, var(--panel)) 0 6px, color-mix(in srgb, var(--c) 11%, var(--panel)) 6px 12px); }}
.ev.k-buffer {{ background:transparent; border:1.5px dashed color-mix(in srgb, var(--c) 70%, var(--panel)); }}
.ev .t {{ font-weight:600; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }}
.ev .m {{ color:var(--muted); font-size:11px; }}
.ev .m b {{ font-weight:600; }}
.ev .note {{ color:var(--muted); font-size:11px; margin-top:2px; }}
.ev.short {{ display:flex; gap:6px; align-items:center; padding:1px 6px; }}
.ev.short .m {{ display:none; }}
.hold {{ color:var(--muted); font-size:10px; }}
aside {{ display:flex; flex-direction:column; gap:14px; }}
.card, aside section {{ background:var(--panel); border:1px solid var(--line); border-radius:16px; padding:14px 16px; box-shadow:var(--shadow); }}
h3 {{ margin:0 0 10px; font-size:13px; text-transform:uppercase; letter-spacing:.06em; color:var(--muted); font-weight:600; }}
.row {{ display:grid; grid-template-columns:10px 88px 1fr 40px; gap:8px; align-items:center; padding:5px 0; }}
.row .goaltxt {{ grid-column:2 / -1; color:var(--muted); font-size:11px; margin-top:-4px; }}
.row.s-none .goaltxt {{ display:none; }}
.sw {{ width:10px; height:10px; border-radius:3px; background:var(--c); }}
.lbl {{ font-size:13px; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }}
.bar {{ position:relative; height:8px; background:var(--line2); border-radius:6px; }}
.bar.empty {{ background:none; }}
.fill {{ height:100%; background:var(--c); border-radius:6px; }}
.goal {{ position:absolute; top:-3px; bottom:-3px; width:2px; background:var(--ink); opacity:.55; }}
.num {{ text-align:right; font-variant-numeric:tabular-nums; font-weight:600; font-size:13px; }}
.row.s-low .num {{ color:var(--warn); }}
.row.s-over .num {{ color:var(--bad); }}
ul {{ margin:0; padding-left:18px; }}
li {{ margin:4px 0; }}
section.bad h3 {{ color:var(--bad); }}
section.warn h3 {{ color:var(--warn); }}
.legend {{ display:flex; flex-wrap:wrap; gap:8px 14px; font-size:12px; color:var(--muted); }}
.legend i {{ display:inline-block; width:22px; height:12px; border-radius:3px; vertical-align:-2px; margin-right:5px; --c:#8A8F98; }}
.legend .lf {{ background:color-mix(in srgb, var(--c) 30%, var(--panel)); border-left:3px solid var(--c); }}
.legend .lb {{ background:color-mix(in srgb, var(--c) 18%, var(--panel)); border-left:3px solid var(--c); }}
.legend .lp {{ background:repeating-linear-gradient(135deg, color-mix(in srgb, var(--c) 30%, var(--panel)) 0 4px, color-mix(in srgb, var(--c) 12%, var(--panel)) 4px 8px); }}
.legend .lu {{ border:1.5px dashed var(--c); }}
footer {{ color:var(--muted); font-size:12px; margin-top:16px; }}
</style></head>
<body><div class="wrap">
{banner}
<header>
  <div><h1>{e(plan.get("title", "Week plan"))}</h1>
  <div class="sub">{days[0]:%b} {days[0].day} – {days[-1]:%b} {days[-1].day}, {days[-1].year} · {e(plan.get("timezone", ""))}</div></div>
  <div class="kpis">
    <div class="kpi"><b>{fmt_h(total_planned)}</b><span>focus blocks</span></div>
    <div class="kpi"><b>{fmt_h(me_h)}</b><span>me time</span></div>
    <div class="kpi"><b>{fmt_h(buffer_h)}</b><span>flex buffer</span></div>
    <div class="kpi"><b>{len(conflicts)}</b><span>conflicts</span></div>
  </div>
</header>
<div class="layout">
  <div class="cal"><div class="grid"><div class="gut" style="height:{grid_h:.0f}px">{"".join(gutter)}</div>{"".join(cols)}</div></div>
  <aside>
    <div class="card"><h3>Hours vs target</h3>{"".join(rows)}</div>
    {conflict_html}{warn_html}{notes_html}
    <div class="card"><h3>Legend</h3><div class="legend">
      <span><i class="lf"></i>Fixed</span><span><i class="lb"></i>Focus block</span>
      <span><i class="lp"></i>Protected</span><span><i class="lu"></i>Flex / rest</span>
      <span><b>W</b> / <b>P</b> / <b>F</b> = work / personal / family calendar</span>
      <span>◆ also a private busy hold on work calendar</span>
    </div></div>
  </aside>
</div>
<footer>Generated by Plan80 · import work.ics, personal.ics and family.ics into their calendars.</footer>
</div></body></html>
"""


# ---------------------------------------------------------------- main


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("plan", type=Path)
    ap.add_argument("--out", type=Path, default=Path("out"))
    ap.add_argument("--open", action="store_true", help="open week.html in the default browser")
    args = ap.parse_args()

    try:
        plan = load_plan(args.plan)
    except (PlanError, KeyError, ValueError, json.JSONDecodeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    events = plan["_events"]
    conflicts = find_conflicts(events)
    hours = area_hours(events)
    warnings = capacity_warnings(plan, hours)

    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "week.html").write_text(build_html(plan, hours, conflicts, warnings), encoding="utf-8")
    for cal in CALENDARS:
        (args.out / f"{cal}.ics").write_text(build_ics(plan, cal), encoding="utf-8", newline="")

    if args.open:
        webbrowser.open((args.out / "week.html").resolve().as_uri())
    print(f"wrote {args.out}/week.html and {', '.join(c + '.ics' for c in CALENDARS)}")
    print("hours: " + ", ".join(f"{plan['areas'][k].get('label', k)} {v:.1f}" for k, v in hours.items()))
    for c in conflicts:
        print(f"CONFLICT  {c}")
    for w in warnings:
        print(f"warning   {w}")
    return 1 if conflicts else 0


if __name__ == "__main__":
    sys.exit(main())
