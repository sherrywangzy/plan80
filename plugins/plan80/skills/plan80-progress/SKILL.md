---
name: plan80-progress
description: Check Plan80 progress over the last 1-2 weeks. Shows weekly hours against target, whether each project is on track for its due date, and recommends whether next week's plan is reasonable. Use when the user asks if they're on track, how their week went, whether a deadline is realistic, or before planning next week.
---

# Plan80: progress and next-week check

This skill reads the log from `plan80-log` and the projects in the config, then answers
three questions: Am I on track? When will this project finish at my current pace? Is next
week's plan realistic? It never changes the plan on its own. Changes are made only after the
user agrees.

Plugin folder: `${CLAUDE_PLUGIN_ROOT}`. If that variable isn't set, use the folder that
contains this skill's `scripts/` directory (two levels above this skill).

## 1. Run the check

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/tracker.py" status --config ~/Plan80/life.json --window 14
```

Use `--window 7` for a single week. For testing, add `--today YYYY-MM-DD`.

The report lists:
- **Areas**: hours a week over the window, against each target.
- **Projects**: one verdict each.
  - `on track`: the recent pace meets what the due date needs.
  - `behind`: the plan has room, but the actual pace is short. Protect the next block.
  - `plan gap`: even the planned hours can't reach the due date. Move the date or add hours.
  - `overdue`: past the due date with work left. Set a new date.
  - `done`: all estimated hours logged.
- **Forecast finish**: when the project finishes at the recent pace.
- **For next week**: recommendations from the same rules.

## 2. Explain it in plain language

- Lead with the project that's most at risk and its date. Give the forecast finish and
  the pace needed, in hours a week.
- Then areas below 70% of target.
- Say whether next week's plan is reasonable. "Reasonable" means every project's needed
  pace fits its planned area, and health is at or near target.
- If the window had too little logged to judge, say so and ask the user to log more before
  trusting the forecast. Don't forecast from one session.

## 3. Offer changes, don't make them

Offer at most two specific changes and wait for the answer:

- Move a due date to the forecast finish, or to the planned finish if it's a plan gap.
- Add hours to the project's area target or add a block for it.
- For a goal area under 70%, lower its target to the actual pace.
- For school, book a checkpoint with the instructor or advisor. Never remove school time
  without asking.

When the user agrees, edit `~/Plan80/life.json` and run `plan80-week` to regenerate the
week.

## Rules that never change

- **Health is never reduced.** If health is under target, the recommendation is to keep
  the number of sessions and change the time or length. Never remove a session to make the
  numbers work.
- **School is never cut automatically.** Under-target school time gets a checkpoint, not a
  reduction.
- **The tool shows time, not results.** Don't comment on trading returns, grades, or fitness
  outcomes. Speak only about hours, deadlines and pace.
- **Don't invent a forecast.** If nothing is logged for a project, say the forecast needs
  sessions first.
