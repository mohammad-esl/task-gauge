"""File-backed storage for config, history log, sessions, and the daily
CSV report. Each store keeps an in-memory cache so repeated reads (driven
by the UI's 1-second poll) don't re-hit disk unless the underlying file
actually changed."""
import os
import re
import json
import csv
from datetime import datetime, timedelta

import time_utils


class ConfigStore:
    def __init__(self, path):
        self.path = path

    def load(self, default):
        if os.path.exists(self.path):
            try:
                with open(self.path, "r") as f:
                    return json.load(f)
            except Exception:
                pass
        return default

    def save(self, data):
        with open(self.path, "w") as f:
            json.dump(data, f)


class HistoryLog:
    """timer_history.txt: an append-only human-readable log. Also parsed
    back into structured sessions for the Gantt view, cached by mtime."""

    _PATTERN = re.compile(
        r"^(\d{4}-\d{2}-\d{2} \d{2}:\d{2})\s*\|\s*"
        r"(?:\[(?:TASK|BREAK)\]\s*)?"
        r"(.+?)\s*\|\s*Session:\s*"
        r"(\d+)h\s+(\d+)m\s+(\d+)s"
    )

    def __init__(self, path):
        self.path = path
        self._cache = None
        self._cache_mtime = None

    def append(self, line):
        with open(self.path, "a") as f:
            f.write(line)
        self._cache = None  # invalidate; mtime check would also catch this

    def load_sessions(self):
        if not os.path.exists(self.path):
            return []

        mtime = os.path.getmtime(self.path)
        if self._cache is not None and self._cache_mtime == mtime:
            return self._cache

        sessions = []
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                lines = f.readlines()
        except Exception:
            return []

        for line in lines:
            match = self._PATTERN.search(line)
            if not match:
                continue

            end_text, category, h, m, sec = match.groups()
            duration = int(h) * 3600 + int(m) * 60 + int(sec)
            if duration < 1:
                continue

            try:
                end_dt = datetime.strptime(end_text, "%Y-%m-%d %H:%M")
            except Exception:
                continue

            start_dt = end_dt - timedelta(seconds=duration)
            sessions.append({
                "date": end_dt.strftime("%Y-%m-%d"),
                "category": category.strip(),
                "start": start_dt.strftime("%Y-%m-%d %H:%M:%S"),
                "end": end_dt.strftime("%Y-%m-%d %H:%M:%S"),
                "duration": duration,
                "source": "history",
            })

        self._cache = sessions
        self._cache_mtime = mtime
        return sessions


class SessionsStore:
    """timer_sessions.json: structured session records, capped at the most
    recent MAX_SESSIONS so the file doesn't grow forever."""

    MAX_SESSIONS = 5000

    def __init__(self, path):
        self.path = path
        self._cache = None

    def load(self):
        if self._cache is not None:
            return self._cache

        if not os.path.exists(self.path):
            self._cache = []
            return self._cache

        try:
            with open(self.path, "r") as f:
                data = json.load(f)
                self._cache = data if isinstance(data, list) else []
        except Exception:
            self._cache = []

        return self._cache

    def append(self, session):
        sessions = self.load()
        sessions.append(session)
        if len(sessions) > self.MAX_SESSIONS:
            sessions = sessions[-self.MAX_SESSIONS:]

        self._cache = sessions
        with open(self.path, "w") as f:
            json.dump(sessions, f, indent=2)


class DailyReportStore:
    """daily_report.csv: one row per logical day, one column per category.
    Rows are cached in memory between reads; call save() to flush."""

    def __init__(self, path):
        self.path = path
        self._rows = None       # {date_str: row_dict}
        self._fieldnames = None

    def load(self, categories):
        if self._rows is not None:
            return self._rows, self._fieldnames

        rows = []
        fieldnames = ["date"] + list(categories)

        if os.path.exists(self.path):
            with open(self.path, "r", newline="") as f:
                reader = csv.DictReader(f)
                rows = list(reader)
                for field in reader.fieldnames or []:
                    if field not in fieldnames:
                        fieldnames.append(field)

        self._rows = {row["date"]: row for row in rows if "date" in row}
        self._fieldnames = fieldnames
        return self._rows, self._fieldnames

    def save(self, rows, fieldnames):
        self._rows = rows
        self._fieldnames = fieldnames
        with open(self.path, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows.values())
