---
name: plan80-sick-day
description: Replan the week when someone at home is sick. Keeps work, family and health, drops goals, adds rest, and says what moved and what is at risk. Use when the user says they or a family member is sick, has a fever, or needs a sick-week replan or asks what to cut because of illness.
---

# Plan80: sick-day replan

Sickness is a mode, not a failure. Keep work, family, sleep and health (as an easy walk).
Drop goals first. Add rest. Tell the user exactly what moved.

Plugin folder: `${CLAUDE_PLUGIN_ROOT}`. If that variable isn't set, use the folder that
contains this skill's `scripts/` directory (two levels above this skill).
User config: `~/Plan80/life.json`. If it doesn't exist, run the `plan80-week` setup first.

## Steps

1. Ask, if not already clear: which days, and who is sick (the user or a family member)?
   A sick family member needs the same handling: the planner doesn't need to know who.
2. Add each day (`mon`..`sun`) to `sick_days` in `~/Plan80/life.json`. Don't remove
   anything else.
3. Regenerate and open the week:
   ```bash
   python3 "${CLAUDE_PLUGIN_ROOT}/scripts/plan_generator.py" ~/Plan80/life.json -o ~/Plan80/plan.json
   python3 "${CLAUDE_PLUGIN_ROOT}/scripts/render.py" ~/Plan80/plan.json --out ~/Plan80/out --open
   ```
4. Read the notes. The planner has already:
   - dropped trading, school and YouTube/GitHub on sick days,
   - turned health into a 20-minute walk,
   - added a rest block in the first free hour after 18:00,
   - kept work, family and sleep.

## What to tell the user

- What moved or was dropped, by day, in one short list.
- Any school deadline at risk: name the assignment and suggest asking for an extension now,
  while there's still time to ask.
- Whether the rest block fit. If it didn't, say which block to move by hand.
- Health: "The workout became a walk today. That's the plan working, not missing it."

## Principles

- Don't moralize about missed goals or guilt the user. The plan is supposed to absorb this.
- Don't drop health, even on a sick day. Only the walk stays.
- Keep the message short. A sick parent doesn't need a long report.
