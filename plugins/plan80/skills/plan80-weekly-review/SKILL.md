---
name: plan80-weekly-review
description: Run the Plan80 weekly review, usually on Sunday. Compares planned hours with targets, asks what got done and what got pushed, and proposes small changes to the week. Use when the user asks for a weekly review, a Sunday check-in, to see how the week went, or to adjust targets that keep missing.
---

# Plan80: weekly review

A 15–30 minute check-in. Compare plan with reality, look for patterns, then change as
little as possible. A target nobody hits is a guilt generator, not a plan.

Plugin folder: `${CLAUDE_PLUGIN_ROOT}`. If that variable isn't set, use the folder that
contains this skill's `scripts/` directory (two levels above this skill).
User config: `~/Plan80/life.json`. Current plan: `~/Plan80/plan.json`.

## Steps

1. Read `~/Plan80/plan.json` and list planned hours by area against target: health (9h),
   trading (5h), school (10h), YouTube/GitHub (1.5h), me time (3h minimum).
2. Ask three questions, one at a time:
   1. Which planned blocks did you actually do? (For health, ask about each workout.)
   2. What got pushed, and why? Sick, overran, too tired, or unexpected?
   3. Does any target feel unrealistic for this season of life?
3. Decide what to change, using these rules:
   - **Health** is never reduced. If it keeps missing, change the time of day or the
     format (for example a shorter workout), not the count.
   - **School:** if school is below target for two weeks in a row, recommend a school
     checkpoint: a fixed meeting with the course deadlines this week.
   - **Targets** change only after the same gap repeats three weeks in a row.
   - Change at most two things per review.
4. Confirm each change with the user before editing `~/Plan80/life.json`.
5. After confirmed edits, regenerate and open the week with `plan80-week`'s commands.

## Close the review

Finish with one sentence on the single thing that will matter most next week, and nothing
else. Don't summarize every block.
