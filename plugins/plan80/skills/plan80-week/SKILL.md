---
name: plan80-week
description: Plan a realistic week with Plan80. Protects health first, fits school, daily practice, family and rest by priority, then opens a color-coded week view and calendar files. Use when the user asks to plan next week, build or replan their week, set up Plan80 for the first time, or asks what their week looks like.
---

# Plan80: plan the week

Plan only 80% of free time. Health is tier 1 and never dropped. Goals are fitted by
priority. Family, sleep and work are fixed. The user never has to run a command or open a
file by hand: this skill runs everything and opens the result.

Plugin folder: `${CLAUDE_PLUGIN_ROOT}`. If that variable isn't set, use the folder that
contains this skill's `scripts/` directory (two levels above this skill).
User data folder: `~/Plan80/` (created on first run, never inside the plugin, so updates
don't erase it).

## 1. First run: set up the user's week

If `~/Plan80/life.json` doesn't exist:
1. Create `~/Plan80/` and copy `${CLAUDE_PLUGIN_ROOT}/config/plan80.example.json` to
   `~/Plan80/life.json`.
2. Walk through the blocks one area at a time, in plain language: work hours, school
   runs, health, practice, school sessions, family time, me time, rest. Ask only about
   what's unclear. Don't dump the whole file.
3. Mark every time you had to guess in the config `notes`, so the user can confirm it.

## 2. Each week

1. Work out the upcoming Monday (today's date decides it) and set `week_of`.
2. Ask one question: **"Anything changed this week? Sick days, deadlines, travel, appointments?"**
   Add sick days to `sick_days` (see `plan80-sick-day`).
   If the Google Calendar connector is connected, list this week's events and ask which
   are fixed appointments. Add those to `appointments` (date, start, end, title). Never
   copy other events. Setup guide: github.com/sherrywangzy/plan80 (folder `examples/google-calendar`).
   Public holidays come from `holidays` in the config (`country`, plus any `ics_files`).
   On a holiday, work blocks are removed with the reason in the notes.
3. Generate and open the week, in one step:
   ```bash
   python3 "${CLAUDE_PLUGIN_ROOT}/scripts/plan_generator.py" ~/Plan80/life.json -o ~/Plan80/plan.json
   python3 "${CLAUDE_PLUGIN_ROOT}/scripts/render.py" ~/Plan80/plan.json --out ~/Plan80/out --open
   ```
4. If the generator raises a tier 0 or tier 1 clash error, the config is wrong. Fix it with
   the user. Never drop health to make the plan run.

## 3. Present the result (plain language)

- Say the week is open in the browser. If it didn't open, give the file path
  `~/Plan80/out/week.html` and say the user can click it.
- Lead with health: how many sessions, and whether they fit.
- Then school hours against target and any dropped blocks, each with its reason.
- Then the notes: tight transitions, assumptions to confirm, targets short.
- Close with the one thing to protect this week.
- Mention the calendar files in `~/Plan80/out/` (`work.ics`, `personal.ics`,
  `family.ics`). Say: "double-click each one to add it to that calendar." The work file
  shows personal blocks only as "Personal hold."

## Principles

- Be honest about overload. If two or more goals are under target, say so and offer one
  specific cut. Don't add blocks to hide the gap.
- Don't give trading advice. Practice is a time-boxed block; the tool plans time, not
  positions.
- Don't ask the user to run commands, edit JSON, or open folders. Those are your jobs.
