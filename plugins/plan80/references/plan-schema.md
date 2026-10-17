# plan.json schema

```json
{
  "title": "Week of Oct 12",
  "week_of": "2026-10-12",
  "timezone": "America/Los_Angeles",
  "mode": "normal",
  "areas": {
    "work":   { "label": "Work",   "color": "#3B6FD4", "target_hours": null },
    "school": { "label": "School", "color": "#7A5CC7", "target_hours": 8 }
  },
  "events": [
    {
      "title": "Pre-watch lecture",
      "area": "school",
      "calendar": "personal",
      "kind": "block",
      "start": "2026-10-13T20:30",
      "end": "2026-10-13T22:00",
      "note": "Week 7 recordings",
      "hold_on_work": false,
      "sick": false
    }
  ],
  "notes": ["Optional lines shown under the week view"]
}
```

## Fields

- `mode`: `"normal"` or `"sick"` (shown as a banner).
- `areas`: every `area` used by an event must be defined here. `target_hours` (or
  `min_hours`, `max_hours`) drive the hours-vs-target bars. Omit them for areas with
  no target.
- `events[].calendar`: `work` | `personal` | `family`. Decides which .ics it goes in.
- `events[].kind`:
  - `fixed`: can't move (work hours, class, appointments)
  - `protected`: could move but shouldn't (family time, school runs)
  - `block`: planned focus time
  - `buffer`: flex, recovery, rest
- `events[].hold_on_work`: also add a generic busy "Personal hold" to work.ics.
- Times are local, `YYYY-MM-DDTHH:MM`, no offset. Events must start and end on the same day.
- Overlaps are reported as conflicts, except a `fixed` work block may contain a block
  explicitly tagged `"inside_work": true` (for example a lunch walk).
