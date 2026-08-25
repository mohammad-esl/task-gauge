# Task Gauge Pro

Task Gauge Pro is a small desktop time-tracking app built with Python and `pywebview`.
It lets you switch between activity categories, track the current session, and review your time with daily, weekly, and Gantt-style views.

## Features

- Category-based timer with a simple visual UI
- Daily tracking with a custom day boundary: `6:00 AM -> next 6:00 AM`
- Weekly stacked bar chart
- Weekly range based on `Saturday -> Friday`
- Session history and daily report export files
- Single-instance guard so the app can't accidentally run twice and corrupt its data files

## Project Structure

```
Timer_app/
├── run.bat                  # background launcher (no console window)
├── requirements.txt
├── requirements-dev.txt     # adds pytest
├── src/
│   ├── app.py                # entry point: wires up the window + API
│   ├── timer_api.py           # TimerApi — the pywebview JS-API bridge
│   ├── storage.py             # file-backed stores (config/history/sessions/report), cached
│   ├── time_utils.py          # logical-day helpers
│   └── single_instance.py     # PID-based lock so only one copy runs at once
├── static/                  # frontend, served by pywebview
│   ├── index.html
│   ├── style.css
│   └── app.js
├── tests/                   # pytest unit tests
├── data/                    # runtime data, created automatically, git-ignored
│   ├── config.json
│   ├── daily_report.csv
│   ├── timer_history.txt
│   ├── timer_sessions.json
│   └── timer.lock            # single-instance lock
└── docs/
    └── version_log.md
```

## Run

The app is distributed as a built Windows executable — it's no longer run
as a raw Python script. Double-click `run.bat` (or the desktop/Startup
shortcut), which launches `dist/TaskGaugePro/TaskGaugePro.exe` directly.
`data/` next to the exe holds your tracking data and persists across
rebuilds.

### Building the exe from source

```bash
build.bat
```

This uses PyInstaller (from the `TimeTracker` conda env) to rebuild
`dist/TaskGaugePro/TaskGaugePro.exe` from `src/` and `static/`. Your
`data/` folder next to the exe is left untouched by a rebuild.

### Running from source (development only)

```bash
pip install -r requirements.txt
python src/app.py
```

## Tests

```bash
pip install -r requirements-dev.txt
pytest tests/
```

## Data Files

The app stores local data under `data/`, created automatically on first run:

- `config.json`
- `daily_report.csv`
- `timer_history.txt`
- `timer_sessions.json`
- `timer.lock` — used to prevent two instances from running at once

These are local working data and are ignored by Git.
