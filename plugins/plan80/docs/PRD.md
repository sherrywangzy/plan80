# PRD: Plan80

**Status:** v0.1, in build  
**Owner:** Sherry Wang  
**Last updated:** 2026-10-16

## 1. Problem

Working professionals juggling a full-time job, school, health, family and a side income
plan their week on calendars that assume 100% of their time is free. Two things go wrong:

1. **Everything is "priority 1."** Goals compete with each other, and the one that slips is
   usually the one that matters most long-term (health, a degree deadline).
2. **There's no plan for a bad week.** A sick kid or a deadline ends the week, and the
   calendar has no idea what to drop.

Note: I'm the first user and the test case. I'm building this for myself first, then
writing it up so other people can use it.

## 2. Users

- **Primary:** mid-career tech professionals (late 30s to 50s) with a job, a degree or
  course load, and a family, who want time for growth without burning out.
- **Me (first user):** AI PM and part-time MIDS student with a weight-loss goal, a
  practice trading routine, a YouTube and GitHub launch, and two kids' worth of school
  logistics.

## 3. Goals and non-goals

**Goals**

- G1. Produce a week that fits. The week must place every top-priority commitment without
  exceeding the time available, and it must say clearly what was dropped and why.
- G2. Never drop health. Health is tier 1, and a clash with a higher-tier constraint is
  treated as a configuration error, not something to resolve quietly.
- G3. Handle sick weeks as a mode. Keep work, family and health; drop goals; add rest.
- G4. Keep the work calendar private. Personal blocks appear there only as "Personal hold."
- G5. Keep the planner trustworthy. Every rule has an automated eval, and the eval suite
  runs in CI.

**Non-goals (v1)**

- Writing to calendars directly (Google/Outlook connectors come in v2, with user approval).
- Tracking whether you actually did the workout (v2: weekly review from logged results).
- Financial advice or any trading signals. Trading is only time-boxed practice.
- Multi-user accounts or a hosted web app.

## 4. Priority rules

The user sets tiers in the config. Lower number wins.

| Tier | Meaning | Examples | Dropped when over capacity? |
| --- | --- | --- | --- |
| 0 | **Constraints.** Fixed reality, not goals. | Work hours, school runs, family time, sleep, me time, buffer | Never |
| 1 | **Top priority, non-negotiable.** | Health: lunch workouts | Never. A clash is a config error. |
| 2 | Goal with a daily habit | Market practice (1 h before work) | Yes, first among goals |
| 3 | Goal with a hard deadline | School: weekend deep day, weekday evening | Yes, but only after tier 4 |
| 4 | Growth and soft launch | YouTube, GitHub | Yes, first |

**Tie-breaking.** When two blocks overlap, the higher tier is kept. The dropped block is
listed in the notes with its reason, so nothing disappears silently.

**Open concern (flagged for the user).** School is tier 3 but has a hard deadline and is
currently behind. The planner enforces the ranking you set, and it shows school hours
against target every week. If school falls below target for two weeks, the planner
recommends a school checkpoint. It doesn't override the ranking on its own.

## 5. Functional requirements

| ID | Requirement | Priority |
| --- | --- | --- |
| F1 | Load a week config (JSON) with areas, tiers, colors and recurring blocks | P0 |
| F2 | Expand recurring blocks into dated events for a given Monday | P0 |
| F3 | Resolve overlaps by tier; raise an error on tier 0/1 clashes | P0 |
| F4 | Report every dropped block with its reason | P0 |
| F5 | Sick mode: drop tier 2–4 on sick days, shorten health to a 20-min walk, add a rest block in the first free hour after 18:00 | P0 |
| F6 | Check weekly hour targets and warn when under 90% | P0 |
| F7 | Render a color-coded week view (HTML, responsive, light and dark) | P0 |
| F8 | Emit one .ics per calendar, with work-calendar privacy | P0 |
| F9 | Retrieve planning rules by question (RAG) so the agent answers from the user's own rules | P1 |
| F10 | Run an eval suite covering scheduling rules, sick mode, privacy and retrieval | P0 |
| F11 | Ensure every week has at least one buffer block | P1 |
| F12 | Read a personal config from `private/`, which is gitignored and never published | P0 |

## 6. Non-functional requirements

- **Zero dependencies.** Python 3.9+ standard library only. Anyone can run it.
- **Deterministic core.** The same config always produces the same plan. That's what makes
  evals meaningful.
- **Privacy by default.** Personal schedules, health details and trading routines live in
  `private/`, which is gitignored and excluded from release zips. The work calendar never
  receives personal titles.
- **No network calls.** The planner runs offline. The agent may use a connector only when
  the user asks.
- **Speed.** Generating and rendering a week takes under 1 second on a laptop.
- **Accessibility.** Color is never the only cue: each block shows its area name and
  calendar letter, and the page passes basic contrast in both themes.

## 7. RAG: answering from the user's own rules

The agent can answer questions such as "my kid is sick, what do I cut?" by retrieving the
relevant section of the planning rules, instead of relying on the model's memory.

- **Corpus:** `references/*.md` and `docs/PRD.md`, split into sections on `## ` headings.
- **Retrieval:** BM25 with query expansion (synonym groups such as sick/ill/fever). It runs
  offline, with no embedding API, so it's cheap, deterministic and testable.
- **Output:** the top 3 sections with scores. The agent quotes the section and cites it.
- **Why not embeddings in v1:** the corpus is small, and keyword retrieval with an
  evaluated synonym list is good enough. The eval suite will show when that stops being
  true. Embeddings are a v2 option only if retrieval evals fall below target.

**Retrieval targets:** at least 4 of 5 eval questions return the expected section in the
top 3.

## 8. Evals

Evals are the acceptance tests for the planner. They run in CI and locally.

| Area | What's checked |
| --- | --- |
| Scheduling | Health blocks: 6 per week, each 90 min. Trading: 5 weekdays, 60 min each. School: at least 10 h per week. |
| Constraints | No overlaps between tier 0 blocks. Nothing after lights-out. At least one buffer per week. |
| Priority | Overload drops the lower tier only. Health survives. Tier 0/1 clashes raise an error. |
| Sick mode | Goals dropped on the sick day. Health becomes a walk. Rest block added. Family kept. |
| Privacy | `work.ics` contains "Personal hold" and never the health or trading titles. |
| Retrieval | 5 questions, each expecting a specific section in the top 3. |

**Targets:** 100% pass on scheduling, constraints, priority, sick mode and privacy.
At least 4 of 5 on retrieval. Results are committed in `evals/RESULTS.md`.

## 9. Success metrics

- **Product:** the eval suite passes on every commit. The personal plan fits its targets
  for 4 consecutive weeks.
- **Personal:** health blocks completed per week (target 6 of 6). Behind-deadline count
  for school goes to zero. Late nights (after 23:00) drop to 0 per week.
- **Portfolio:** the repo gets stars and newsletter signups after the first video. The
  architecture and evals are visible to hiring managers reviewing the work.

## 10. Milestones

| Milestone | Scope | Exit criteria |
| --- | --- | --- |
| M0 | PRD and architecture | This doc and ARCHITECTURE.md reviewed |
| M1 | Generator, priority resolver, renderer | Scheduling and priority evals pass |
| M2 | Sick mode, privacy, .ics | Sick and privacy evals pass |
| M3 | RAG retrieval, eval suite, CI | Retrieval evals at 4 of 5 or better; CI green |
| M4 | Public release, demo video | Repo public; first video recorded with fake data |
| M5 (v2) | Calendar connectors, weekly review from logs | Opt-in writes, with approval for each change |

## 11. Risks

| Risk | Mitigation |
| --- | --- |
| The plan is too tight to live with | 20% slack is built in. Weekly review adjusts targets. |
| Personal data leaks into the public repo | `private/` is gitignored, excluded from zips, and CI checks for it. |
| Trading looks like financial advice | Scope is time-boxed practice only. The README says so. |
| Tight morning transitions (trading ends at 08:00, drop-off at 08:20) | The planner flags any transition under 15 min in the notes. |
| Saturday health block is an assumption | Labeled as an assumption in the config; the user confirms. |
| Retrieval returns the wrong section | Evals catch it; synonyms are updated and tested. |

## 12. Open questions

1. Is Saturday's 90-minute health block right, or should it sit on a weekday?
2. Is school start time 08:20 or later? That sets whether the 07:00 trading slot fits
   before drop-off.
3. Should the school checkpoint trigger at two weeks below target, or one?
