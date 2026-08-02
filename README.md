# Task Gauge Pro

Task Gauge Pro is a small desktop time-tracking app built with Python and `pywebview`.
It lets you switch between activity categories, track the current session, and review your time with daily, weekly, and Gantt-style views.

## Features

- Category-based timer with a simple visual UI
- Daily tracking with a custom day boundary: `6:00 AM -> next 6:00 AM`
- Weekly stacked bar chart
- Weekly range based on `Saturday -> Friday`
- Session history and daily report export files

## Run

Install the dependency and start the app:

```bash
pip install -r requirements.txt
python timer.py
```

## Data Files

The app stores local data in these files:

- `config.json`
- `daily_report.csv`
- `timer_history.txt`
- `timer_sessions.json`

These are meant to be local working data and are ignored by Git.
