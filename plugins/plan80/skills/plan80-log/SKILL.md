---
name: plan80-log
description: Log a work session against an area or project in Plan80, such as 90 minutes of lunch training, an hour on a school assignment, or a session on the launch. Use when the user says they just worked on something, did a session, or wants to record time for a project.
---

# Plan80: log a session

Logging is one line per session, saved to `~/Plan80/log.jsonl`. The user never edits the
file. Logging takes a few seconds, so keep the conversation short.

Plugin folder: `${CLAUDE_PLUGIN_ROOT}`. If that variable isn't set, use the folder that
contains this skill's `scripts/` directory (two levels above this skill).

## 1. Get three things

1. **Area**: one of the keys in `areas` in `~/Plan80/life.json` (for example `health`,
   `trading`, `school`, `content`, `me`).
2. **Minutes**: how long it took. If the user says "about an hour", use 60.
3. **Project** (optional): an `id` from `projects` in `~/Plan80/life.json`. If the user
   names a project that isn't listed, ask whether to add it, rather than guessing an id.

If the date isn't today, ask for it and pass `--day YYYY-MM-DD`.

## 2. Record it

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/tracker.py" log --config ~/Plan80/life.json \
  --area content --minutes 90 --project plan80-launch --note "script draft"
```

The output says `logged 90 min to content on 2026-10-16`. Repeat the command for each
session. Don't batch sessions into one entry.

## 3. Confirm in one line

Reply with what was saved and the running total for the project, for example:
"Logged 90 min to Plan80 launch. That's 3.5 h of 30 h." To get the total, run
`tracker.py status` and read the project line, or skip the total if the user only wanted
to log.

## Rules

- Log what happened, not what was planned. A planned session the user skipped isn't logged.
- Never invent minutes. If the user is unsure, ask.
- Health and school sessions are logged the same way. Logging them is how the progress
  check (`plan80-progress`) knows whether the plan is working.
- The log holds only time and short notes. Don't write health details into `note`; use
  "lunch training" rather than symptoms or results.
