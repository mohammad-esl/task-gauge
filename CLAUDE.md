# CLAUDE.md

Guidance for Claude Code (or any agent) working in this repository.

## What this is

Task Gauge Pro: a small Windows desktop time-tracking app. Python backend
(`TimerApi` in `src/timer_api.py`) exposed as a `pywebview` `js_api` to a
single-page HTML/JS/CSS frontend (`static/`). No web server, no database —
everything is flat JSON/CSV files under `data/`.

## Environment

- Python interpreter for this project lives in the **`TimeTracker`** conda
  env, not whatever `python`/`pip` resolve to on `PATH`:
  `C:\Users\<user>\.conda\envs\TimeTracker\python.exe`. Use it explicitly for
  running tests or scripts; the default `python` on PATH may be a different
  install without `pytest`/`pywebview`.
- `DATA_DIR` in `src/app.py` is a **hardcoded absolute path** to the
  project's `data/` folder, not relative to the exe or cwd. Both `python
  src/app.py` and the built exe read/write the same real data — there is no
  separate "dev" data directory. Be deliberate before running the app
  interactively; prefer pointing a throwaway `TimerApi(tmp_dir)` at an
  isolated directory for anything exploratory.
- `data/` is entirely git-ignored. Never assume a fresh clone has it —
  `TimerApi.__init__` creates sane defaults on first run.

## Core design invariant: additive, not invasive

The single most important rule in this codebase: **new features must not
change the meaning or output of existing computations.** Concretely:

- Category totals, `daily_report.csv`, week/range reports, and the main
  Gantt view are the trusted historical record. A new feature should read
  from `timer_sessions.json` / the existing report stores, never introduce
  a second source of truth that can drift from them.
- If a feature needs to tag or annotate existing data (e.g. subtasks
  tagging sessions with an optional `subtask_id`), the new field must be
  **purely additive and optional** — nothing existing reads it, so the
  worst-case bug is "a label is wrong or missing," never "totals are wrong."
- When adding a report that overlaps an existing one (e.g. a per-subtask
  Gantt next to the main Gantt), **call and filter the existing report
  function** rather than reimplementing its clipping/live-session/rollover
  logic a second time. Two implementations of the same logic will drift.
- Before merging any change that touches `timer_api.py`, run a manual
  regression check: snapshot `get_gantt_report`/`get_week_report`/
  `get_range_report` output on a copy of real `data/` before and after the
  change, and diff them. They should be byte-identical unless the change
  was explicitly meant to alter those reports.

## Testing

- Test runner: `pytest`, but only installed in the `TimeTracker` conda env.
  Run with the full interpreter path:
  ```
  C:\Users\<user>\.conda\envs\TimeTracker\python.exe -m pytest tests/ -q
  ```
- `tests/conftest.py` adds `src/` to `sys.path` — tests import modules
  directly (`from timer_api import TimerApi`), not as a package.
- Every `TimerApi` test uses `tmp_path` as an isolated data directory —
  never point a test at the real `data/`.
- New backend behavior should get a real test, not just a manual check.
  Time-based tests (e.g. session finalization, mid-session switches)
  should drive `start_time`/`end_ts` with explicit timestamps rather than
  `time.sleep`, and assert with a small tolerance (±1s) rather than exact
  equality.

## Building

- `build.bat` runs PyInstaller from the `TimeTracker` env and wipes/rebuilds
  `dist/TaskGaugePro/` on every run (`--noconfirm`). Anything manually
  placed in `dist/` (e.g. a copied `data/`) is disposable.
- `--add-data "...\static;static"` bundles the **entire** `static/`
  directory — adding a new static file (new page, new script) needs no
  changes to `build.bat`. Don't add per-file `--add-data` entries.
- After any change touching window creation (`app.py`, multi-window
  features), actually launch the built exe once and confirm it opens
  without a console traceback — `sys._MEIPASS` path resolution only gets
  exercised in the frozen build, not `python src/app.py`.

## Frontend conventions

- No build step, no framework — plain HTML/CSS/JS, loaded directly by
  pywebview. Keep it that way; don't introduce a bundler for a small
  single-window (or two-window) app.
- The main wheel is an SVG (`#hit-surface`, `viewBox="0 0 100 100"`) with
  one `<path class="slice">` per category at radius 50, plus HTML
  `<div class="label">` elements positioned by trigonometry at a fixed
  pixel radius (210px) outside the SVG. When adding new visual elements to
  the wheel:
  - Keep changes to the `viewBox` minimal (a few units of margin, not a
    large expansion) — the whole layout is tuned in SVG units, and a big
    viewBox change makes new geometry look strewn/disconnected from the
    dial rather than part of it.
  - New interactive elements should sit either clearly inside the dial's
    own radius or clearly and thinly just outside it — never let them
    visually collide with the center needle or the category slice fill.
  - Prefer **fewer moving parts** over a fancier interaction: a single
    always-visible thin ring with direct click targets held up better in
    practice than a hover-to-expand annular arc with per-segment tooltips.
    When a UI idea needs several iterations to look right, simplify the
    interaction model before adding more positioning math.
  - Test any new wheel UI by actually launching the app and looking at
    it — SVG angle/radius math is easy to get subtly wrong in ways that
    only show up visually, not in a syntax check or a passing test suite.
- Category colors don't exist as a stored property — they're derived at
  render time from position: `chartColors[max(0, categories.indexOf(cat) -
  1) % chartColors.length]`. Reuse this exact formula (don't invent a
  second color scheme) if a new view needs to color by category.

## Git workflow

- Work on a feature branch, not directly on `main`, for anything beyond a
  trivial fix.
- Commit in small, independently-revertible steps (e.g. "add the store +
  its tests" as one commit, "wire it into the API" as another, "add the
  UI" as another) rather than one large commit — this keeps the risky,
  UI-facing changes isolated from the safe, additive backend changes.
- Never use `--no-verify`, force-push, or amend a pushed commit unless
  explicitly asked.
