# Planning rules

## 1. Capacity math (do this before placing anything)

For each day: `awake = wake -> bedtime`. Subtract fixed and protected events.
What's left is **free time**. Sum it for the week.

- **Plannable** = free time x `capacity_target` (default 0.80).
- The remaining ~20% is unscheduled slack: transitions, chores, the email that took
  an hour. Do not fill it.
- The **flex buffer** comes out of plannable time, not slack.

If the sum of `target_hours` across areas > plannable, the week is over-committed.
Say so, then trim in this order: youtube -> invest -> school extras -> health extras.
Never trim: family protected time, me-time minimum, sleep.

## 2. Placement order

1. Sleep boundaries
2. Fixed (work hours, class sessions, appointments, kid appointments)
3. Protected (school runs, family dinner and bedtime, weekend family minimum)
4. Flex buffer
5. Deadline work, placed backwards from the deadline:
   pre-watch lectures go 1-2 days before the live session, homework finishes
   at least one evening before it's due
6. Habits (same time every week)
7. Growth (YouTube, investing study)
8. Me time (at least `min_hours`; best on Friday evening or a weekend evening)

## 3. Energy matching

- Deep work (YouTube building, homework) goes in the **first** evening block after
  bedtime routines, not at 10pm.
- Max **one** deep evening block per weeknight. The other weeknight blocks stay light
  (lecture watching, review, me time).
- Exercise goes in the morning or at lunch. Evening exercise slots get skipped first.
- Investing is time-boxed. One mid-week check + one weekly review beats daily checking.

## 4. Sick mode

Triggered by "I'm sick", "kid is sick", "we're all sick", or by days marked sick.

For sick days:
- Keep: work hours (if working), kid logistics, meals.
- After work: **rest**. Mark it as a `buffer` block titled "Rest (sick)".
- Live session: keep it, or replace it with "Watch recording" on the first well day.
- Move deadline work to the nearest well evening before the deadline. If it doesn't fit,
  say which assignment is at risk so the user can ask for an extension early.
- Drop in `defer_order`. YouTube and investing simply skip a week. That's fine; say it
  plainly and without guilt.
- Health habits: replace workouts with a short walk only if the user feels up to it.

Budget: plan around `sick_days_per_month` (default 3). If the month has already used them,
the next plan should run lighter (capacity_target - 0.10) for one week.

## 5. Calendar routing

| Area | Calendar | Work-calendar hold? |
| --- | --- | --- |
| Work | work | n/a |
| Family protected time, kid appointments | family | only if it overlaps 8:30-17:30 or the user asks |
| School, health, investing, YouTube, me time | personal | no |
| Personal appointments during work hours | personal | yes, as "Personal hold" |

## 6. Weekly review (Sunday, 15-30 min)

Ask three questions, then re-plan:
1. What got done vs planned (per area)?
2. What got pushed, and why? (sick, overrun, energy, unexpected)
3. Is any target unrealistic for this season of life?

Adjust the targets in `~/Plan80/life.json` when a gap repeats three weeks in a row.
A target nobody hits is a guilt generator, not a plan.
