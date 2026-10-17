# Google Calendar with Plan80

Plan80 plans your week, and Google Calendar holds your real appointments. This guide
connects the two, so a doctor's visit on Thursday shows up in the plan and takes that
time out of your work block.

Plan80 never sees your Google password. You sign in to Google yourself, through the
Google Calendar connector in Claude. Plan80 only receives the events you choose to bring in.

## What you get

- Your appointments are read from Google Calendar for the week you're planning.
- Each appointment goes into `appointments` in `~/Plan80/life.json`.
- The generator splits any work block around the appointment. Nothing else moves.
- On the work calendar (`work.ics`), the appointment shows as **Personal hold**, with no title.
  On your personal calendar it keeps its real name.

## Step 1: Connect Google Calendar (once)

1. In Claude, open **Settings → Connectors**.
2. Find **Google Calendar** and choose **Connect**.
3. Sign in with **your own** Google account, and allow read access to your calendar.
   Use the account where your personal appointments live.
4. Check the connection: ask Claude, "List my Google Calendar events for next Monday."

If you use a work Google account, check your employer's rules first. Many companies don't
allow personal calendars to be connected to outside tools.

## Step 2: Bring appointments into the plan

When you plan a week, Plan80 asks whether anything fixed is on the calendar. If the
connector is on, it lists the week's events and asks you which ones are fixed, such as a
doctor, a dentist, or a school pickup. For each one, Plan80 adds an entry like this:

```json
"appointments": [
  { "title": "Dr appointment", "date": "2026-10-22", "start": "14:00", "end": "15:00" }
]
```

Put only fixed times in `appointments`. Flexible things belong in `blocks`.

## Step 3: Example

The example config has a mock appointment on a work day, Thursday, October 22, 2026:

```json
{ "title": "Dr appointment (mock)", "date": "2026-10-22", "start": "14:00", "end": "15:00" }
```

Thursday's work block (13:30–17:00) is split into 13:30–14:00 and 15:00–17:00. The
appointment takes the hour in between. Your lunch workout (12:00–13:30) isn't affected.

The file `mock-dr-appointment.ics` in this folder is the same appointment as an .ics file,
for testing an import into Google Calendar. Delete it once you use your own.

## Step 4: Check the result

Ask Plan80 to plan the week. The notes should show the split, and `work.ics` should show
"Personal hold" at 14:00 on Thursday, with no doctor's name.

## Privacy

- Google sign-in happens in Google's own page, not in Plan80.
- Plan80 stores appointment titles only in `~/Plan80/life.json`, on your computer.
- The plugin and the public repo contain only the mock example. CI blocks personal config
  from being committed.
- To disconnect, remove Google Calendar in Settings → Connectors.
