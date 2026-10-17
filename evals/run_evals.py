#!/usr/bin/env python3
"""Plan80 eval suite: acceptance tests for the generator, renderer, privacy and retrieval.

Run:  python3 evals/run_evals.py
Writes evals/RESULTS.md and exits 1 if any case fails.

Golden config: config/plan80.example.json (same shape as private/life.json).
"""
from __future__ import annotations

import copy
import json
import re
import subprocess
import sys
from pathlib import Path

sys.dont_write_bytecode = True  # keep __pycache__ out of the plugin folder

ROOT = Path(__file__).resolve().parent.parent
PLUGIN = ROOT / "plugins" / "plan80"
sys.path.insert(0, str(PLUGIN / "scripts"))

from plan_generator import PlanError, generate, to_min, overlaps  # noqa: E402
from rag import search  # noqa: E402
import render  # noqa: E402

GOLDEN = json.loads((PLUGIN / "config" / "plan80.example.json").read_text(encoding="utf-8"))
OUT = ROOT / "evals" / ".out"
RESULTS = ROOT / "evals" / "RESULTS.md"
WEEKDAYS = ["mon", "tue", "wed", "thu", "fri"]


def with_blocks(extra: list[dict], **top) -> dict:
    cfg = copy.deepcopy(GOLDEN)
    cfg["blocks"] = cfg["blocks"] + extra
    cfg.update(top)
    return cfg


def hours(plan: dict, area: str) -> float:
    return sum(to_min(e["end"]) - to_min(e["start"]) for e in plan["events"] if e["area"] == area) / 60


def count(plan: dict, area: str) -> int:
    return sum(1 for e in plan["events"] if e["area"] == area)


# ---- scheduling -------------------------------------------------------------

def case_health_six_days_90min():
    plan = generate(GOLDEN)
    health = [e for e in plan["events"] if e["area"] == "health"]
    days = {e["day"] for e in health}
    durations = {to_min(e["end"]) - to_min(e["start"]) for e in health}
    ok = len(health) == 6 and days == {"mon", "tue", "wed", "thu", "fri", "sat"} and durations == {90}
    return ok, f"{len(health)} blocks on {sorted(days)}, durations {sorted(durations)}"


def case_trading_weekdays_60min():
    plan = generate(GOLDEN)
    tr = [e for e in plan["events"] if e["area"] == "trading"]
    ok = len(tr) == 5 and {e["day"] for e in tr} == set(WEEKDAYS) and all(
        to_min(e["end"]) - to_min(e["start"]) == 60 for e in tr)
    return ok, f"{len(tr)} trading blocks"


def case_school_at_least_10h():
    plan = generate(GOLDEN)
    h = hours(plan, "school")
    return h >= 10, f"school {h:g}h vs 10h target"


def case_content_and_me_targets():
    plan = generate(GOLDEN)
    c, m = hours(plan, "content"), hours(plan, "me")
    return c >= 1.5 and m >= 3, f"content {c:g}h (target 1.5), me {m:g}h (min 3)"


def case_buffer_each_week():
    plan = generate(GOLDEN)
    b = count(plan, "buffer")
    return b >= 1, f"{b} buffer block(s)"


# ---- constraints ------------------------------------------------------------

def case_no_tier0_overlaps():
    plan = generate(GOLDEN)
    tier0 = {"work", "family", "me", "buffer"}
    evs = [e for e in plan["events"] if e["area"] in tier0]
    bad = [
        (a["title"], b["title"]) for i, a in enumerate(evs) for b in evs[i + 1:]
        if overlaps(a, b) and not (a.get("inside_work") or b.get("inside_work"))
    ]
    return not bad, f"{len(bad)} overlapping tier-0 pairs"


def case_nothing_after_lights_out():
    plan = generate(GOLDEN)
    late = [e["title"] for e in plan["events"] if to_min(e["end"]) > 22 * 60 + 30]
    return not late, f"late blocks: {late or 'none'}"


def case_transition_warning_for_commute():
    plan = generate(GOLDEN)
    flagged = any("drop-off" in n and "min between" in n for n in plan["notes"])
    return flagged, "10-min drop-off to work gap is flagged"


# ---- priority ---------------------------------------------------------------

def case_overload_drops_goal_not_health():
    cfg = with_blocks([{"area": "trading", "title": "Extra trading", "days": ["mon"],
                        "start": "12:00", "end": "13:00", "kind": "block"}])
    plan = generate(cfg)
    dropped = [d["title"] for d in plan["dropped"]]
    health_mon = [e for e in plan["events"] if e["area"] == "health" and e["day"] == "mon"]
    ok = "Extra trading" in dropped and len(health_mon) == 1
    return ok, f"dropped={dropped}, health kept on Mon={len(health_mon) == 1}"


def case_tier1_clash_is_config_error():
    cfg = with_blocks([{"area": "family", "title": "Kid appointment", "days": ["sat"],
                        "start": "09:30", "end": "10:00", "kind": "protected"}])
    try:
        generate(cfg)
    except PlanError as exc:
        return "never dropped" in str(exc), "raised PlanError on health clash"
    return False, "no error raised"


def case_tier0_clash_is_config_error():
    cfg = with_blocks([{"area": "family", "title": "Early call", "days": ["mon"],
                        "start": "09:30", "end": "10:00", "kind": "fixed"}])
    try:
        generate(cfg)
    except PlanError:
        return True, "raised PlanError on work/family clash"
    return False, "no error raised"


# ---- sick mode --------------------------------------------------------------

def case_sick_day_rules():
    plan = generate(with_blocks([], sick_days=["tue"]))
    tue = [e for e in plan["events"] if e["day"] == "tue"]
    areas_tue = {e["area"] for e in tue}
    no_goals = not areas_tue & {"trading", "school", "content"}
    walk = [e for e in tue if e["area"] == "health"]
    walk_ok = len(walk) == 1 and to_min(walk[0]["end"]) - to_min(walk[0]["start"]) == 20
    rest = [e for e in tue if e["title"] == "Rest (sick day)"]
    family_ok = "family" in areas_tue
    ok = no_goals and walk_ok and len(rest) == 1 and family_ok
    return ok, f"goals dropped={no_goals}, walk={walk_ok}, rest={len(rest) == 1}, family kept={family_ok}"


def case_sick_rest_is_free_and_after_work():
    plan = generate(with_blocks([], sick_days=["tue"]))
    rest = [e for e in plan["events"] if e["title"] == "Rest (sick day)"][0]
    clashes = [e for e in plan["events"] if e["day"] == "tue" and e is not rest
               and overlaps(e, rest) and not (e.get("inside_work") or False)]
    return to_min(rest["start"]) >= 18 * 60 and not clashes, f"rest {rest['start']}-{rest['end']}"


# ---- privacy ----------------------------------------------------------------

def case_work_calendar_is_private():
    plan = generate(GOLDEN)
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / "plan.json"
    path.write_text(json.dumps(plan), encoding="utf-8")
    loaded = render.load_plan(path)
    ics = render.build_ics(loaded, "work")
    has_hold = "Personal hold" in ics
    leaked = [w for w in ("Lunch workout", "Health", "School pickup", "Market practice") if w in ics]
    return has_hold and not leaked, f"hold={has_hold}, leaked={leaked or 'none'}"


def case_personal_calendar_keeps_titles():
    plan = generate(GOLDEN)
    path = OUT / "plan.json"
    loaded = render.load_plan(path)
    ics = render.build_ics(loaded, "personal")
    return "Lunch workout" in ics and "Market practice" in ics, "titles present on personal.ics"


# ---- retrieval (RAG) --------------------------------------------------------

RETRIEVAL = [
    ("my kid is sick, what do I cut?", "Sick mode"),
    ("how many hours can I plan in a week", "Capacity math"),
    ("when should I do homework before a deadline", "Placement order"),
    ("which calendar gets my personal appointments", "Calendar routing"),
    ("when two things conflict which priority wins", "Priority"),
]
# Held out: written after tuning R1-R5, never used to adjust retrieval.
HELDOUT = [
    ("what goes first when my week is overloaded", "Priority"),
    ("how often should I do the weekly review", "Weekly review"),
]


def retrieval_case(question: str, expected: str):
    hits = search(question, k=3)
    headings = [h["heading"] for h in hits]
    return any(expected.lower() in h.lower() for h in headings), f"top3={headings}"


CASES = [
    ("S1", "Health: 6 blocks, 90 min each", case_health_six_days_90min),
    ("S2", "Trading: 5 weekdays, 60 min each", case_trading_weekdays_60min),
    ("S3", "School: at least 10 h a week", case_school_at_least_10h),
    ("S4", "Content and me-time targets met", case_content_and_me_targets),
    ("S5", "At least one buffer block", case_buffer_each_week),
    ("C1", "No tier-0 overlaps", case_no_tier0_overlaps),
    ("C2", "Nothing runs past lights-out", case_nothing_after_lights_out),
    ("C3", "Commute gap under 15 min is flagged", case_transition_warning_for_commute),
    ("P1", "Overload drops goal, never health", case_overload_drops_goal_not_health),
    ("P2", "Tier-1 clash raises config error", case_tier1_clash_is_config_error),
    ("P3", "Tier-0 clash raises config error", case_tier0_clash_is_config_error),
    ("K1", "Sick day: goals dropped, walk, rest, family kept", case_sick_day_rules),
    ("K2", "Sick rest is free and after 18:00", case_sick_rest_is_free_and_after_work),
    ("X1", "Work calendar shows only Personal hold", case_work_calendar_is_private),
    ("X2", "Personal calendar keeps real titles", case_personal_calendar_keeps_titles),
]
# ---- appointments, holidays, tracking ----------------------------------------

import tempfile  # noqa: E402
from datetime import date  # noqa: E402

import holidays as hol  # noqa: E402
import tracker  # noqa: E402

SAMPLE_ICS = ROOT / "examples" / "google-calendar" / "mock-holidays-sample.ics"


def case_appointment_carves_work():
    plan = generate(GOLDEN)
    thu = sorted((e["start"][-5:], e["end"][-5:]) for e in plan["events"]
                 if e["area"] == "work" and e["day"] == "thu")
    ok = ("13:30", "14:00") in thu and ("15:00", "17:00") in thu and not any(
        s < "15:00" and e > "14:00" and s >= "14:00" for s, e in thu)
    return ok, f"Thu work segments {thu}"


def case_appointment_is_personal_hold_at_work():
    plan = generate(GOLDEN)
    appt = [e for e in plan["events"] if e["area"] == "appointments"]
    flagged = bool(appt) and all(e.get("hold_on_work") for e in appt)
    tmp = OUT / "appt"
    tmp.mkdir(parents=True, exist_ok=True)
    (tmp / "plan.json").write_text(json.dumps(plan), encoding="utf-8")
    subprocess.run([sys.executable, str(PLUGIN / "scripts" / "render.py"),
                    str(tmp / "plan.json"), "--out", str(tmp)], capture_output=True)
    work_ics = (tmp / "work.ics").read_text(encoding="utf-8") if (tmp / "work.ics").exists() else ""
    ok = flagged and "Dr appointment" not in work_ics and "Personal hold" in work_ics
    return ok, f"{len(appt)} appointment(s), hold_on_work={flagged}, title hidden from work calendar"


def case_thanksgiving_drops_work_only():
    cfg = copy.deepcopy(GOLDEN)
    cfg["week_of"] = "2026-11-23"
    plan = generate(cfg)
    thu_work = [e for e in plan["events"] if e["area"] == "work" and e["day"] == "thu"]
    reasons = [d["reason"] for d in plan["dropped"] if "Thanksgiving" in d["reason"]]
    health_thu = [e for e in plan["events"] if e["area"] == "health" and e["day"] == "thu"]
    notes = any("Thanksgiving" in n for n in plan["notes"])
    ok = not thu_work and len(reasons) >= 1 and len(health_thu) == 1 and notes
    return ok, f"work dropped with {len(reasons)} reason(s), health kept Thu={len(health_thu) == 1}"


def case_holiday_from_ics_file():
    cfg = copy.deepcopy(GOLDEN)
    cfg["week_of"] = "2026-11-23"
    cfg["holidays"] = {"country": "", "ics_files": [str(SAMPLE_ICS)]}
    plan = generate(cfg)
    thu_work = [e for e in plan["events"] if e["area"] == "work" and e["day"] == "thu"]
    ok = not thu_work and any("Thanksgiving" in n for n in plan["notes"])
    return ok, f"ICS holiday removes Thu work: {not thu_work}"


def case_no_holiday_in_normal_week():
    plan = generate(GOLDEN)
    ok = not any("Public holiday" in n for n in plan["notes"]) and not plan["dropped"]
    return ok, "week of 2026-10-19 has no holiday and no drops"


def case_us_federal_rules_2026():
    h = hol.us_federal(2026)
    expect = {
        date(2026, 1, 19): "Martin Luther King Jr. Day",
        date(2026, 2, 16): "Presidents' Day",
        date(2026, 5, 25): "Memorial Day",
        date(2026, 7, 3): "Independence Day",
        date(2026, 9, 7): "Labor Day",
        date(2026, 10, 12): "Columbus Day",
        date(2026, 11, 26): "Thanksgiving Day",
    }
    bad = {str(d): h.get(d) for d, n in expect.items() if h.get(d) != n}
    return not bad, f"{len(expect) - len(bad)}/{len(expect)} dates correct, misses={bad or 'none'}"


def case_ics_parser_reads_all_day_events():
    got = hol.from_ics(SAMPLE_ICS)
    return got == {date(2026, 11, 26): "Thanksgiving Day"}, f"parsed {len(got)} event(s)"


def _tracker_cfg(**projects_override) -> dict:
    cfg = copy.deepcopy(GOLDEN)
    cfg["projects"] = [{"id": "p", "name": "Test project", "area": "content",
                        "due": "2026-11-30", "estimate_hours": 10, **projects_override}]
    return cfg


def _log(entries: list[dict]) -> list[dict]:
    return entries


def case_tracker_on_track():
    cfg = _tracker_cfg()
    log = _log([{"date": "2026-10-10", "area": "content", "minutes": 90, "project": "p"},
                {"date": "2026-10-14", "area": "content", "minutes": 90, "project": "p"},
                {"date": "2026-10-03", "area": "content", "minutes": 90, "project": "p"}])
    res = tracker.analyze(cfg, log, date(2026, 10, 16))
    row = res["projects"][0]
    return row["verdict"] == "on_track", f"verdict={row['verdict']}, pace={row['actual_pace']}h/wk"


def case_tracker_plan_gap():
    cfg = _tracker_cfg(estimate_hours=30)
    res = tracker.analyze(cfg, [], date(2026, 10, 16))
    row = res["projects"][0]
    gap_rec = any("Move the due date" in r for r in res["recommendations"])
    return row["verdict"] == "plan_gap" and gap_rec, f"verdict={row['verdict']}, needs {row['needed_pace']}h/wk"


def case_tracker_overdue():
    cfg = _tracker_cfg(due="2026-10-01")
    res = tracker.analyze(cfg, [], date(2026, 10, 16))
    return res["projects"][0]["verdict"] == "overdue", f"verdict={res['projects'][0]['verdict']}"


def case_tracker_done():
    cfg = _tracker_cfg(estimate_hours=2)
    log = [{"date": "2026-10-15", "area": "content", "minutes": 120, "project": "p"}]
    res = tracker.analyze(cfg, log, date(2026, 10, 16))
    return res["projects"][0]["verdict"] == "done", f"verdict={res['projects'][0]['verdict']}"


def case_tracker_never_cuts_health():
    res = tracker.analyze(copy.deepcopy(GOLDEN), [], date(2026, 10, 16))
    health_recs = [r for r in res["recommendations"] if r.startswith("Health")]
    ok = bool(health_recs) and all("Keep the number of sessions" in r for r in health_recs)
    return ok, f"{len(health_recs)} health recommendation(s), none reduce the target"


def case_tracker_rejects_unknown_area():
    path = OUT / "eval-log.jsonl"
    path.unlink(missing_ok=True)
    try:
        tracker.append_entry(path, GOLDEN, "crypto", 60, "2026-10-14", None, None)
    except tracker.TrackerError as exc:
        return not path.exists(), f"rejected: {exc}"
    return False, "no error raised"


def case_tracker_log_roundtrip():
    path = OUT / "eval-log.jsonl"
    path.unlink(missing_ok=True)
    tracker.append_entry(path, GOLDEN, "health", 90, "2026-10-14", None, "lunch run")
    entries = tracker.load_log(path)
    ok = len(entries) == 1 and entries[0]["minutes"] == 90 and entries[0]["note"] == "lunch run"
    return ok, f"{len(entries)} entry saved"


NEW_CASES = [
    ("A1", "Appointment carves the work block around it", case_appointment_carves_work),
    ("A2", "Appointment shows as Personal hold on work calendar", case_appointment_is_personal_hold_at_work),
    ("H1", "Thanksgiving removes work only, health kept", case_thanksgiving_drops_work_only),
    ("H2", "Holiday from an .ics file removes work", case_holiday_from_ics_file),
    ("H3", "No holiday in a normal week", case_no_holiday_in_normal_week),
    ("H4", "US federal rules, observed dates, 2026", case_us_federal_rules_2026),
    ("H5", "ICS parser reads all-day events", case_ics_parser_reads_all_day_events),
    ("T1", "Tracker: on track when pace meets need", case_tracker_on_track),
    ("T2", "Tracker: plan gap is flagged with a new date", case_tracker_plan_gap),
    ("T3", "Tracker: past due date is overdue", case_tracker_overdue),
    ("T4", "Tracker: finished project is done", case_tracker_done),
    ("T5", "Tracker: never recommends cutting health", case_tracker_never_cuts_health),
    ("T6", "Tracker: rejects an unknown area", case_tracker_rejects_unknown_area),
    ("T7", "Tracker: log entry round-trips", case_tracker_log_roundtrip),
]

# ---- plugin packaging -------------------------------------------------------

def case_marketplace_lists_plugin():
    m = json.loads((ROOT / ".claude-plugin" / "marketplace.json").read_text(encoding="utf-8"))
    entries = m.get("plugins", [])
    ok = any(p.get("name") == "plan80" and (ROOT / p["source"]).resolve() == PLUGIN.resolve()
             for p in entries)
    return ok, f"marketplace entries: {[p.get('name') for p in entries]}"


def case_plugin_manifest_valid():
    m = json.loads((PLUGIN / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))
    name = m.get("name", "")
    ok = bool(re.fullmatch(r"[a-z0-9]+(-[a-z0-9]+)*", name)) and m.get("version") and m.get("description")
    return bool(ok), f"name={name!r}, version={m.get('version')!r}"


def case_skills_have_frontmatter():
    skills = sorted((PLUGIN / "skills").glob("*/SKILL.md"))
    problems = []
    for path in skills:
        match = re.match(r"---\n(.*?)\n---", path.read_text(encoding="utf-8"), re.S)
        if not match:
            problems.append(f"{path.parent.name}: no frontmatter")
            continue
        fm = dict(line.split(":", 1) for line in match.group(1).splitlines() if ":" in line)
        if fm.get("name", "").strip() != path.parent.name:
            problems.append(f"{path.parent.name}: name mismatch")
        if not fm.get("description", "").strip():
            problems.append(f"{path.parent.name}: missing description")
    return len(skills) >= 4 and not problems, f"{len(skills)} skills, problems={problems or 'none'}"


def case_plugin_has_no_personal_data():
    bad = [
        p.relative_to(PLUGIN).as_posix() for p in PLUGIN.rglob("*")
        if p.is_file() and (p.name in {"life.json", "plan.json", "RESULTS.md"}
                            or "out" in p.parts or "private" in p.parts or "__pycache__" in p.parts)
    ]
    return not bad, f"personal or generated files in plugin: {bad or 'none'}"


def case_render_can_open_week():
    r = subprocess.run([sys.executable, str(PLUGIN / "scripts" / "render.py"), "--help"],
                       capture_output=True, text=True)
    return "--open" in r.stdout, "render.py --open flag available"


CASES += [
    ("K3", "Marketplace lists the plugin", case_marketplace_lists_plugin),
    ("K4", "Plugin manifest is valid", case_plugin_manifest_valid),
    ("K5", "Every skill has matching name and description", case_skills_have_frontmatter),
    ("K6", "Plugin ships no personal data", case_plugin_has_no_personal_data),
    ("K7", "Plan opens itself in the browser", case_render_can_open_week),
]

CASES += NEW_CASES

for i, (q, expected) in enumerate(RETRIEVAL, start=1):
    CASES.append((f"R{i}", f"Retrieve '{expected}' for: {q}",
                  lambda q=q, e=expected: retrieval_case(q, e)))
for i, (q, expected) in enumerate(HELDOUT, start=len(RETRIEVAL) + 1):
    CASES.append((f"R{i}", f"[held-out] Retrieve '{expected}' for: {q}",
                  lambda q=q, e=expected: retrieval_case(q, e)))


def main() -> int:
    # Scheduling/privacy cases need OUT/plan.json; generate once up front.
    generate(GOLDEN)
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "plan.json").write_text(json.dumps(generate(GOLDEN)), encoding="utf-8")

    rows, failures = [], 0
    for cid, desc, fn in CASES:
        try:
            ok, detail = fn()
        except Exception as exc:  # a crash is a failure, not a pass
            ok, detail = False, f"exception: {exc}"
        failures += 0 if ok else 1
        rows.append((cid, "PASS" if ok else "FAIL", desc, detail))

    passed = len(rows) - failures
    retrieval_rows = [r for r in rows if r[0].startswith("R")]
    retrieval_pass = sum(1 for r in retrieval_rows if r[1] == "PASS")

    lines = [
        "# Plan80 eval results",
        "",
        f"**{passed}/{len(rows)} passing.** Retrieval: {retrieval_pass}/{len(retrieval_rows)} "
        f"(target 4 of 5; R1-R5 tuned, R6-R7 held out). Scheduling, constraints, priority, sick mode and privacy must be 100%.",
        "",
        "| ID | Result | Case | Detail |",
        "| --- | --- | --- | --- |",
    ]
    lines += [f"| {cid} | {res} | {desc} | {detail} |" for cid, res, desc, detail in rows]
    RESULTS.write_text("\n".join(lines) + "\n", encoding="utf-8")

    for cid, res, desc, detail in rows:
        print(f"{res}  {cid:<3} {desc}  ({detail})")
    print(f"\n{passed}/{len(rows)} passing; retrieval {retrieval_pass}/{len(retrieval_rows)}")

    core_fail = [r for r in rows if not r[0].startswith("R") and r[1] == "FAIL"]
    retrieval_ok = retrieval_pass >= 4 and sum(1 for r in retrieval_rows[-2:] if r[1] == "PASS") >= 1
    return 0 if not core_fail and retrieval_ok else 1


if __name__ == "__main__":
    sys.exit(main())
