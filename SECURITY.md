# Security policy

## Reporting a vulnerability

Please **don't open a public issue** for security problems. Use GitHub's private
reporting: go to the **Security** tab and click **Report a vulnerability**.
I'll reply within 7 days.

## Scope

Plan80 runs locally. It reads a week config and writes HTML and .ics files. It makes
no network calls and has no runtime dependencies. Evals run in CI with no secrets.

## Keeping your data private

- `private/` (your real schedule, health and trading routine), `plan.json` and `out/`
  are gitignored. CI fails if any personal config is committed.
- Release zips exclude `private/`. Don't attach your config to issues or screenshots.
- Demos and screenshots must use placeholder data.
