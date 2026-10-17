# Plan80 eval results

**40/41 passing.** Retrieval: 6/7 (target 4 of 5; R1-R5 tuned, R6-R7 held out). Scheduling, constraints, priority, sick mode and privacy must be 100%.

| ID | Result | Case | Detail |
| --- | --- | --- | --- |
| S1 | PASS | Health: 6 blocks, 90 min each | 6 blocks on ['fri', 'mon', 'sat', 'thu', 'tue', 'wed'], durations [90] |
| S2 | PASS | Trading: 5 weekdays, 60 min each | 5 trading blocks |
| S3 | PASS | School: at least 10 h a week | school 10h vs 10h target |
| S4 | PASS | Content and me-time targets met | content 1.5h (target 1.5), me 3.5h (min 3) |
| S5 | PASS | At least one buffer block | 1 buffer block(s) |
| C1 | PASS | No tier-0 overlaps | 0 overlapping tier-0 pairs |
| C2 | PASS | Nothing runs past lights-out | late blocks: none |
| C3 | PASS | Commute gap under 15 min is flagged | 10-min drop-off to work gap is flagged |
| P1 | PASS | Overload drops goal, never health | dropped=['Extra trading'], health kept on Mon=True |
| P2 | PASS | Tier-1 clash raises config error | raised PlanError on health clash |
| P3 | PASS | Tier-0 clash raises config error | raised PlanError on work/family clash |
| K1 | PASS | Sick day: goals dropped, walk, rest, family kept | goals dropped=True, walk=True, rest=True, family kept=True |
| K2 | PASS | Sick rest is free and after 18:00 | rest 2026-10-20T20:30-2026-10-20T21:30 |
| X1 | PASS | Work calendar shows only Personal hold | hold=True, leaked=none |
| X2 | PASS | Personal calendar keeps real titles | titles present on personal.ics |
| K3 | PASS | Marketplace lists the plugin | marketplace entries: ['plan80'] |
| K4 | PASS | Plugin manifest is valid | name='plan80', version='0.1.0' |
| K5 | PASS | Every skill has matching name and description | 6 skills, problems=none |
| K6 | PASS | Plugin ships no personal data | personal or generated files in plugin: none |
| K7 | PASS | Plan opens itself in the browser | render.py --open flag available |
| A1 | PASS | Appointment carves the work block around it | Thu work segments [('09:00', '12:00'), ('13:30', '14:00'), ('15:00', '17:00')] |
| A2 | PASS | Appointment shows as Personal hold on work calendar | 1 appointment(s), hold_on_work=True, title hidden from work calendar |
| H1 | PASS | Thanksgiving removes work only, health kept | work dropped with 2 reason(s), health kept Thu=True |
| H2 | PASS | Holiday from an .ics file removes work | ICS holiday removes Thu work: True |
| H3 | PASS | No holiday in a normal week | week of 2026-10-19 has no holiday and no drops |
| H4 | PASS | US federal rules, observed dates, 2026 | 7/7 dates correct, misses=none |
| H5 | PASS | ICS parser reads all-day events | parsed 1 event(s) |
| T1 | PASS | Tracker: on track when pace meets need | verdict=on_track, pace=2.25h/wk |
| T2 | PASS | Tracker: plan gap is flagged with a new date | verdict=plan_gap, needs 4.67h/wk |
| T3 | PASS | Tracker: past due date is overdue | verdict=overdue |
| T4 | PASS | Tracker: finished project is done | verdict=done |
| T5 | PASS | Tracker: never recommends cutting health | 1 health recommendation(s), none reduce the target |
| T6 | PASS | Tracker: rejects an unknown area | rejected: unknown area 'crypto'. Use one of: work, family, me, buffer, health, trading, school, content, appointments |
| T7 | PASS | Tracker: log entry round-trips | 1 entry saved |
| R1 | PASS | Retrieve 'Sick mode' for: my kid is sick, what do I cut? | top3=["7. RAG: answering from the user's own rules", '4. Sick mode', '1. Problem'] |
| R2 | PASS | Retrieve 'Capacity math' for: how many hours can I plan in a week | top3=['4. Sick mode', '1. Capacity math (do this before placing anything)', '1. Problem'] |
| R3 | PASS | Retrieve 'Placement order' for: when should I do homework before a deadline | top3=['2. Placement order', '4. Sick mode', '3. Energy matching'] |
| R4 | PASS | Retrieve 'Calendar routing' for: which calendar gets my personal appointments | top3=['5. Calendar routing', 'Fields', '6. Non-functional requirements'] |
| R5 | PASS | Retrieve 'Priority' for: when two things conflict which priority wins | top3=['4. Priority rules', '1. Problem', '5. Functional requirements'] |
| R6 | FAIL | [held-out] Retrieve 'Priority' for: what goes first when my week is overloaded | top3=['3. Energy matching', '9. Success metrics', '1. Problem'] |
| R7 | PASS | [held-out] Retrieve 'Weekly review' for: how often should I do the weekly review | top3=['6. Weekly review (Sunday, 15-30 min)', '3. Energy matching', '10. Milestones'] |
