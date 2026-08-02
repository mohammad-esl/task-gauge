import webview
import time
import os
import json
import csv
import re
from datetime import datetime, timedelta


class TimerApi:
    def __init__(self):
        self.log_file = "timer_history.txt"
        self.config_file = "config.json"
        self.report_file = "daily_report.csv"
        self.sessions_file = "timer_sessions.json"
        self.day_start_hour = 6
        self.last_report_save = time.time()
        self.report_save_interval = 300  # 5 minutes

        # Default data
        self.data = {
            "categories": ["Nothing", "Education", "Work", "Study", "Project 1"],
            "totals": {"Nothing": 0, "Education": 0, "Work": 0, "Study": 0, "Project 1": 0},
            "last_date": self._current_logical_date_str(),
        }

        self.load_config()
        self._check_daily_reset()

        # Force "Nothing" to exist
        if "Nothing" not in self.data["categories"]:
            self.data["categories"].insert(0, "Nothing")
        if "Nothing" not in self.data["totals"]:
            self.data["totals"]["Nothing"] = 0

        self.active_cat = "Nothing"
        self.start_time = time.time()

    def load_config(self):
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, "r") as f:
                    self.data = json.load(f)
            except Exception:
                pass

        if "last_date" not in self.data:
            self.data["last_date"] = self._current_logical_date_str()

    def save_config(self):
        with open(self.config_file, "w") as f:
            json.dump(self.data, f)

    def _parse_history_duration(self, hours, minutes, seconds):
        return int(hours) * 3600 + int(minutes) * 60 + int(seconds)

    def _logical_day_start(self, day_value):
        if isinstance(day_value, str):
            day_value = datetime.strptime(day_value, "%Y-%m-%d").date()
        return datetime.combine(day_value, datetime.min.time()) + timedelta(hours=self.day_start_hour)

    def _logical_date(self, dt_value):
        return (dt_value - timedelta(hours=self.day_start_hour)).date()

    def _current_logical_date_str(self):
        return self._logical_date(datetime.now()).strftime("%Y-%m-%d")

    def _finalize_active_session(self, end_ts):
        if not hasattr(self, "active_cat") or not hasattr(self, "start_time"):
            return 0

        duration = int(end_ts - self.start_time)
        if duration <= 0:
            self.start_time = end_ts
            return 0

        self.data["totals"][self.active_cat] = self.data["totals"].get(self.active_cat, 0) + duration
        self._write_to_history(self.active_cat, duration, end_ts=end_ts)
        self._record_session(self.active_cat, self.start_time, end_ts)
        self.start_time = end_ts
        return duration

    def _add_duration_to_daily_report(self, date_str, category, duration):
        if duration <= 0:
            return

        rows = []
        fieldnames = ["date"] + self.data["categories"]

        if os.path.exists(self.report_file):
            with open(self.report_file, "r", newline="") as f:
                reader = csv.DictReader(f)
                rows = list(reader)

                for field in reader.fieldnames or []:
                    if field not in fieldnames:
                        fieldnames.append(field)

        existing = {row["date"]: row for row in rows if "date" in row}
        row = existing.get(date_str, {"date": date_str})

        for cat in fieldnames:
            if cat == "date":
                continue
            row.setdefault(cat, "00:00:00")

        try:
            h, m, s = [int(x) for x in row.get(category, "00:00:00").split(":")]
            current_seconds = h * 3600 + m * 60 + s
        except Exception:
            current_seconds = 0

        row[category] = self._format_hms(current_seconds + duration)
        existing[date_str] = row

        with open(self.report_file, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(existing.values())

    def _align_active_session_to_logical_day(self):
        if not hasattr(self, "active_cat") or not hasattr(self, "start_time"):
            return

        now_ts = time.time()
        start_dt = datetime.fromtimestamp(self.start_time)
        current_dt = datetime.fromtimestamp(now_ts)

        if self._logical_date(start_dt) == self._logical_date(current_dt):
            return

        previous_logical_date = self._logical_date(start_dt).strftime("%Y-%m-%d")
        rollover_ts = self._logical_day_start(self._logical_date(current_dt)).timestamp()
        duration = int(rollover_ts - self.start_time)
        if duration > 0:
            self._write_to_history(self.active_cat, duration, end_ts=rollover_ts)
            self._record_session(self.active_cat, self.start_time, rollover_ts)
            self._add_duration_to_daily_report(previous_logical_date, self.active_cat, duration)
        self.start_time = rollover_ts
        self.save_config()

    def _load_history_sessions(self):
        if not os.path.exists(self.log_file):
            return []

        sessions = []
        pattern = re.compile(
            r"^(\d{4}-\d{2}-\d{2} \d{2}:\d{2})\s*\|\s*"
            r"(?:\[(?:TASK|BREAK)\]\s*)?"
            r"(.+?)\s*\|\s*Session:\s*"
            r"(\d+)h\s+(\d+)m\s+(\d+)s"
        )

        try:
            with open(self.log_file, "r", encoding="utf-8") as f:
                lines = f.readlines()
        except Exception:
            return []

        for line in lines:
            match = pattern.search(line)
            if not match:
                continue

            end_text, category, h, m, sec = match.groups()
            duration = self._parse_history_duration(h, m, sec)
            if duration < 1:
                continue

            try:
                end_dt = datetime.strptime(end_text, "%Y-%m-%d %H:%M")
            except Exception:
                continue

            start_dt = end_dt - timedelta(seconds=duration)
            category = category.strip()

            sessions.append({
                "date": end_dt.strftime("%Y-%m-%d"),
                "category": category,
                "start": start_dt.strftime("%Y-%m-%d %H:%M:%S"),
                "end": end_dt.strftime("%Y-%m-%d %H:%M:%S"),
                "duration": duration,
                "source": "history",
            })

        return sessions

    def _clip_session_to_day(self, session, date_str):
        try:
            start_dt = datetime.strptime(session["start"], "%Y-%m-%d %H:%M:%S")
            end_dt = datetime.strptime(session["end"], "%Y-%m-%d %H:%M:%S")
            day_start = self._logical_day_start(date_str)
        except Exception:
            return None

        day_end = day_start + timedelta(days=1)
        clipped_start = max(start_dt, day_start)
        clipped_end = min(end_dt, day_end)

        if clipped_end <= clipped_start:
            return None

        clipped = session.copy()
        clipped["date"] = date_str
        clipped["start"] = clipped_start.strftime("%Y-%m-%d %H:%M:%S")
        clipped["end"] = clipped_end.strftime("%Y-%m-%d %H:%M:%S")
        clipped["duration"] = int((clipped_end - clipped_start).total_seconds())
        return clipped

    def _load_sessions(self):
        if not os.path.exists(self.sessions_file):
            return []

        try:
            with open(self.sessions_file, "r") as f:
                data = json.load(f)
                if isinstance(data, list):
                    return data
        except Exception:
            pass

        return []

    def _save_sessions(self, sessions):
        with open(self.sessions_file, "w") as f:
            json.dump(sessions, f, indent=2)

    def _record_session(self, name, start_ts, end_ts):
        duration = int(end_ts - start_ts)
        if duration < 1:
            return

        start_dt = datetime.fromtimestamp(start_ts)
        end_dt = datetime.fromtimestamp(end_ts)

        sessions = self._load_sessions()
        sessions.append({
            "date": self._logical_date(start_dt).strftime("%Y-%m-%d"),
            "category": name,
            "start": start_dt.strftime("%Y-%m-%d %H:%M:%S"),
            "end": end_dt.strftime("%Y-%m-%d %H:%M:%S"),
            "duration": duration,
        })

        # Keep the file from growing forever. This preserves roughly the latest 5000 sessions.
        if len(sessions) > 5000:
            sessions = sessions[-5000:]

        self._save_sessions(sessions)

    def _get_live_totals(self):
        self._align_active_session_to_logical_day()
        totals = self.data["totals"].copy()

        if hasattr(self, "active_cat") and hasattr(self, "start_time"):
            session = int(time.time() - self.start_time)
            totals[self.active_cat] = totals.get(self.active_cat, 0) + session

        return totals

    def _format_hms(self, seconds):
        h, m, s = self._get_hms(seconds)
        return f"{h:02d}:{m:02d}:{s:02d}"

    def _save_daily_report(self, date_str):
        totals = self._get_live_totals()
        rows = []
        fieldnames = ["date"] + self.data["categories"]

        if os.path.exists(self.report_file):
            with open(self.report_file, "r", newline="") as f:
                reader = csv.DictReader(f)
                rows = list(reader)

                for field in reader.fieldnames or []:
                    if field not in fieldnames:
                        fieldnames.append(field)

        existing = {row["date"]: row for row in rows if "date" in row}

        row = {"date": date_str}
        for cat in fieldnames:
            if cat == "date":
                continue
            row[cat] = self._format_hms(totals.get(cat, 0))

        existing[date_str] = row

        with open(self.report_file, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(existing.values())

    def get_today_report(self):
        self._check_daily_reset()
        return {
            "date": self._current_logical_date_str(),
            "totals": self._get_live_totals(),
        }

    def save_today_report(self):
        today = self._current_logical_date_str()
        self._save_daily_report(today)
        return {"status": "saved"}

    def get_week_report(self, week_offset=0):
        self._save_daily_report(self._current_logical_date_str())

        today = self._logical_date(datetime.now())
        days_since_saturday = (today.weekday() + 2) % 7
        start_of_week = today - timedelta(days=days_since_saturday)
        start_of_week = start_of_week + timedelta(weeks=int(week_offset))
        end_of_week = start_of_week + timedelta(days=6)

        rows = {}
        if os.path.exists(self.report_file):
            with open(self.report_file, "r", newline="") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    rows[row["date"]] = row

        days = []
        for i in range(7):
            day = start_of_week + timedelta(days=i)
            date_str = day.strftime("%Y-%m-%d")
            row = rows.get(date_str, {})

            totals = {}
            for cat in self.data["categories"]:
                value = row.get(cat, "00:00:00")
                try:
                    h, m, s = [int(x) for x in value.split(":")]
                    totals[cat] = h * 3600 + m * 60 + s
                except Exception:
                    totals[cat] = 0

            days.append({
                "date": date_str,
                "label": day.strftime("%a"),
                "totals": totals,
            })

        return {
            "week_start": start_of_week.strftime("%Y-%m-%d"),
            "week_end": end_of_week.strftime("%Y-%m-%d"),
            "categories": self.data["categories"],
            "days": days,
        }

    def get_gantt_report(self, date_str=None):
        self._check_daily_reset()
        self._align_active_session_to_logical_day()

        if not date_str:
            date_str = self._current_logical_date_str()

        # Primary source: timer_history.txt.
        # Each history row stores the session end time and duration, so we reconstruct:
        # start_time = end_time - duration.
        history_sessions = self._load_history_sessions()
        filtered = []

        for session in history_sessions:
            clipped = self._clip_session_to_day(session, date_str)
            if clipped:
                filtered.append(clipped)

        # Add the current live session without saving it yet.
        now = time.time()
        if hasattr(self, "active_cat") and hasattr(self, "start_time"):
            duration = int(now - self.start_time)
            live_session = {
                "date": date_str,
                "category": self.active_cat,
                "start": datetime.fromtimestamp(self.start_time).strftime("%Y-%m-%d %H:%M:%S"),
                "end": datetime.fromtimestamp(now).strftime("%Y-%m-%d %H:%M:%S"),
                "duration": duration,
                "live": True,
                "source": "live",
            }
            clipped = self._clip_session_to_day(live_session, date_str)
            if duration > 0 and clipped:
                filtered.append(clipped)

        categories = list(self.data["categories"])
        for session in filtered:
            cat = session.get("category")
            if cat and cat not in categories:
                categories.append(cat)

        filtered.sort(key=lambda item: item.get("start", ""))

        return {
            "date": date_str,
            "categories": categories,
            "sessions": filtered,
        }

    def _check_daily_reset(self):
        today = self._logical_date(datetime.now())
        last = datetime.strptime(self.data["last_date"], "%Y-%m-%d").date()

        if today != last:
            rollover_ts = self._logical_day_start(today).timestamp()
            self._finalize_active_session(rollover_ts)
            self._save_daily_report(self.data["last_date"])

            self.data["totals"] = {k: 0 for k in self.data["categories"]}
            self.data["last_date"] = today.strftime("%Y-%m-%d")

            with open(self.log_file, "a") as f:
                f.write(f"\n--- NEW DAY: {self.data['last_date']} ---\n")

            self.save_config()

    def _get_hms(self, s):
        return s // 3600, (s % 3600) // 60, s % 60

    def _write_to_history(self, name, session_duration, end_ts=None):
        # We log "Nothing" to history only if it was a significant "break" (> 10 seconds)
        if session_duration < 10:
            return

        if end_ts is None:
            end_dt = datetime.now()
        else:
            end_dt = datetime.fromtimestamp(end_ts)

        timestamp = end_dt.strftime("%Y-%m-%d %H:%M")
        sh, sm, ss = self._get_hms(session_duration)
        th, tm, ts = self._get_hms(self.data["totals"].get(name, 0))

        prefix = "[BREAK]   " if name == "Nothing" else "[TASK]    "
        log_entry = (f"{timestamp} | {prefix} {name.ljust(15)} | "
                     f"Session: {sh}h {sm}m {ss}s | Total: {th}h {tm}m {ts}s\n")

        with open(self.log_file, "a") as f:
            f.write(log_entry)

    def get_init_data(self):
        # Now "Nothing" is included in the history list for the Dashboard
        history_list = [{"name": k, "time": f"{h}h {m}m {s}s"}
                        for k, v in self.data["totals"].items()
                        for h, m, s in [self._get_hms(v)]]
        return {"categories": self.data["categories"], "active": self.active_cat, "history": history_list}

    def set_category(self, name):
        self._check_daily_reset()

        now = time.time()
        self._finalize_active_session(now)
        self.save_config()

        self.active_cat = name
        self.start_time = now

        self._save_daily_report(self._current_logical_date_str())
        self.last_report_save = time.time()

        return {"status": "success"}

    def reset_timer(self):
        self._check_daily_reset()
        now = time.time()
        self._finalize_active_session(now)
        self.save_config()
        return {"status": "reset"}

    def update_config(self, new_cats):
        self.set_category(self.active_cat)

        # Ensure Nothing stays at index 0
        if "Nothing" in new_cats:
            new_cats.remove("Nothing")
        new_cats.insert(0, "Nothing")

        new_totals = {name: self.data["totals"].get(name, 0) for name in new_cats}
        self.data["categories"], self.data["totals"] = new_cats, new_totals

        self.active_cat = "Nothing"
        self.start_time = time.time()
        self.save_config()
        self._save_daily_report(self._current_logical_date_str())
        return self.get_init_data()

    def get_status(self):
        self._check_daily_reset()
        self._align_active_session_to_logical_day()

        if time.time() - self.last_report_save >= self.report_save_interval:
            self._save_daily_report(self._current_logical_date_str())
            self.last_report_save = time.time()

        now = time.time()
        session = int(now - self.start_time)
        return {
            "active": self.active_cat,
            "session": session,
            "total": self.data["totals"].get(self.active_cat, 0) + session,
        }


html_content = """
<!DOCTYPE html>
<html>
<head>
    <style>
        :root { --bg: #0a0a0a; --accent: #00e5ff; --ring: #161616; --red: #ff4b2b; }
        body { background: var(--bg); color: white; font-family: 'Segoe UI', sans-serif;
               display: flex; justify-content: center; align-items: center; height: 100vh; margin: 0; overflow: hidden; }
        .main-container { position: relative; width: 520px; height: 520px; transition: filter 0.3s; }
        .blur { filter: blur(15px); pointer-events: none; }
        #hit-surface { position: absolute; width: 100%; height: 100%; z-index: 5; }
        .slice { fill: var(--ring); stroke: #222; stroke-width: 1; cursor: pointer; transition: fill 0.2s; }
        .slice:hover { fill: #222; }
        #hub { position: absolute; width: 100%; height: 100%; z-index: 6; pointer-events: none; transition: transform 0.6s cubic-bezier(0.34, 1.56, 0.64, 1); }
        .needle { position: absolute; top: 16px; left: 50%; transform: translateX(-50%); width: 4px; height: 44px; background: var(--accent); box-shadow: 0 0 15px var(--accent); border-radius: 2px; }
        .label { position: absolute; width: 110px; text-align: center; font-weight: bold; font-size: 11px; color: #444; z-index: 7; pointer-events: none; text-transform: uppercase; }
        .label.active { color: var(--accent); text-shadow: 0 0 10px var(--accent); }
        .center-display { position: absolute; width: 300px; height: 300px; background: #000; border-radius: 50%; top: 50%; left: 50%; transform: translate(-50%, -50%); border: 10px solid #222; z-index: 10; display: flex; flex-direction: column; justify-content: center; align-items: center; }
        #session-time { font-size: 72px; color: var(--accent); font-family: monospace; line-height: 1; cursor: pointer; }
        .total-box { color: #888; font-family: monospace; font-size: 13px; background: #111; padding: 4px 12px; border-radius: 15px; border: 1px solid #222;}
        .controls { margin-top: 15px; display: flex; gap: 8px; flex-wrap: wrap; justify-content: center; max-width: 240px; }
        .icon-btn { background: none; border: 1px solid #333; color: #555; cursor: pointer; padding: 4px 8px; border-radius: 4px; font-size: 10px; }
        .icon-btn:hover { color: white; border-color: #777; }
        #settings-panel, #gantt-panel { position: absolute; width: 520px; background: rgba(15,15,15,0.98); border: 1px solid #333; padding: 20px; border-radius: 15px; z-index: 100; display: none; box-shadow: 0 0 50px black; max-height: 90vh; overflow-y: auto; }
        #gantt-panel { width: 660px; }
        textarea { width: 100%; height: 80px; background: #000; color: var(--accent); border: 1px solid #444; padding: 8px; box-sizing: border-box; margin-bottom: 15px; }
        .stats-table { width: 100%; font-size: 11px; border-collapse: collapse; margin-bottom: 15px; color: #aaa; }
        .stats-table td { padding: 4px 0; border-bottom: 1px solid #222; }
        .stats-table tr td:last-child { text-align: right; color: var(--accent); }
        .save-btn { background: var(--accent); color: black; border: none; padding: 10px; width: 100%; cursor: pointer; font-weight: bold; border-radius: 4px; margin-top: 5px; }
        #week-chart { height: 180px; display: flex; align-items: flex-end; gap: 8px; border-bottom: 1px solid #333; padding-bottom: 8px; margin-bottom: 12px; }
        .bar-wrapper { flex: 1; height: 100%; display: flex; flex-direction: column; justify-content: flex-end; align-items: center; }
        .bar { width: 100%; display: flex; flex-direction: column-reverse; background: #111; border: 1px solid #222; box-sizing: border-box; }
        .bar-label { font-size: 10px; color: #777; margin-top: 4px; }
        .legend { display: flex; flex-wrap: wrap; gap: 6px; margin-bottom: 12px; font-size: 10px; color: #aaa; }
        .legend-item { display: flex; align-items: center; gap: 4px; }
        .legend-dot { width: 8px; height: 8px; border-radius: 2px; }
        .gantt-toolbar { display: flex; justify-content: space-between; align-items: center; gap: 10px; margin-bottom: 12px; }
        .gantt-date { color: #777; font-size: 11px; }
        .gantt-frame { background: #070707; border: 1px solid #222; border-radius: 10px; padding: 12px; }
        .gantt-axis { position: relative; height: 22px; margin-left: 110px; border-bottom: 1px solid #252525; color: #555; font-size: 10px; }
        .axis-mark { position: absolute; transform: translateX(-50%); bottom: 4px; }
        .gantt-row { display: flex; align-items: center; min-height: 34px; border-bottom: 1px solid #151515; }
        .gantt-row:last-child { border-bottom: none; }
        .gantt-label { width: 100px; padding-right: 10px; color: #aaa; font-size: 11px; text-align: right; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
        .gantt-lane { position: relative; flex: 1; height: 26px; background: #101010; border-left: 1px solid #222; border-right: 1px solid #222; overflow: hidden; }
        .gantt-block { position: absolute; top: 5px; height: 16px; min-width: 2px; border-radius: 4px; cursor: default; box-shadow: 0 0 10px rgba(0,0,0,0.35); }
        .gantt-empty { color: #555; font-size: 12px; padding: 20px; text-align: center; }
    </style>
</head>
<body>
    <div id="settings-panel">
        <h4 style="margin:0 0 10px 0; color:var(--accent); letter-spacing:1px">DASHBOARD</h4>
        <table class="stats-table" id="history-table"></table>

        <h5 style="margin:10px 0 5px 0; font-size:10px; color:#555">WEEKLY VIEW</h5>
        <div style="display:flex; gap:6px; margin-bottom:10px;">
            <button class="icon-btn" onclick="changeWeek(-1)">← PREV</button>
            <button class="icon-btn" onclick="changeWeek(0)">THIS WEEK</button>
            <button class="icon-btn" onclick="changeWeek(1)">NEXT →</button>
        </div>

        <div id="week-label" style="font-size:11px; color:#777; margin-bottom:8px;"></div>
        <div id="week-chart"></div>
        <div id="week-legend" class="legend"></div>

        <h5 style="margin:10px 0 5px 0; font-size:10px; color:#555">EDIT TASKS (One per line)</h5>
        <textarea id="cat-input" placeholder="Enter tasks..."></textarea>
        <button class="save-btn" onclick="saveSettings()">APPLY CHANGES</button>
        <button class="save-btn" style="background:#222; color:#777" onclick="toggleSettings()">CLOSE</button>
    </div>

    <div id="gantt-panel">
        <div class="gantt-toolbar">
            <h4 style="margin:0; color:var(--accent); letter-spacing:1px">GANTT / TIMELINE VIEW</h4>
            <div style="display:flex; gap:6px;">
                <button class="icon-btn" onclick="shiftGanttDay(-1)">← PREV DAY</button>
                <button class="icon-btn" onclick="shiftGanttDay(0)">TODAY</button>
                <button class="icon-btn" onclick="shiftGanttDay(1)">NEXT DAY →</button>
            </div>
        </div>
        <div id="gantt-date" class="gantt-date"></div>
        <div id="gantt-chart" class="gantt-frame"></div>
        <button class="save-btn" style="background:#222; color:#777" onclick="toggleGantt()">CLOSE</button>
    </div>

    <div class="main-container" id="app-ui">
        <svg id="hit-surface" viewBox="0 0 100 100"></svg>
        <div id="hub"><div class="needle"></div></div>
        <div class="center-display">
            <div id="session-time" onclick="toggleSettings()">00:00</div>
            <div class="total-box">TOTAL <span id="total-time">00:00:00</span></div>
            <div class="controls">
                <button class="icon-btn" onclick="toggleSettings()">STATS/EDIT</button>
                <button class="icon-btn" onclick="toggleGantt()">GANTT</button>
                <button class="icon-btn" onclick="resetCurrent()" style="color:var(--red)">RESET</button>
            </div>
        </div>
    </div>

    <script>
        let cats = [];
        let currentWeekOffset = 0;
        let ganttDateOffset = 0;
        const hub = document.getElementById('hub');
        const svg = document.getElementById('hit-surface');

        const chartColors = [
            "#00e5ff", "#ff4b2b", "#ffd166", "#06d6a0", "#9b5de5",
            "#f15bb5", "#fee440", "#00bbf9", "#f77f00", "#80ed99"
        ];

        function format(s, full=false) {
            let h = Math.floor(s / 3600).toString().padStart(2, '0');
            let m = Math.floor((s % 3600) / 60).toString().padStart(2, '0');
            let sec = (s % 60).toString().padStart(2, '0');
            return full ? `${h}:${m}:${sec}` : `${m}:${sec}`;
        }

        function secondsToLabel(s) {
            let h = Math.floor(s / 3600);
            let m = Math.floor((s % 3600) / 60);
            return `${h}h ${m}m`;
        }

        function visibleCategories(categories) {
            return categories.filter(c => c !== "Nothing");
        }

        function visibleDayTotal(day) {
            return Object.entries(day.totals)
                .filter(([cat]) => cat !== "Nothing")
                .reduce((sum, [, seconds]) => sum + seconds, 0);
        }

        function addDays(date, days) {
            const d = new Date(date);
            d.setDate(d.getDate() + days);
            return d;
        }

        function localDateString(date) {
            const y = date.getFullYear();
            const m = String(date.getMonth() + 1).padStart(2, '0');
            const d = String(date.getDate()).padStart(2, '0');
            return `${y}-${m}-${d}`;
        }

        function logicalDateString(date) {
            const shifted = new Date(date);
            shifted.setHours(shifted.getHours() - 6, shifted.getMinutes(), shifted.getSeconds(), shifted.getMilliseconds());
            return localDateString(shifted);
        }

        function timeToTimelineMinutes(dateTimeText) {
            const timePart = dateTimeText.split(' ')[1] || '00:00:00';
            const parts = timePart.split(':').map(Number);
            const totalMinutes = parts[0] * 60 + parts[1] + (parts[2] || 0) / 60;
            return (totalMinutes - 360 + 1440) % 1440;
        }

        function displayTime(dateTimeText) {
            const timePart = dateTimeText.split(' ')[1] || '00:00:00';
            return timePart.slice(0, 5);
        }

        function changeWeek(direction) {
            if (direction === 0) {
                currentWeekOffset = 0;
            } else {
                currentWeekOffset += direction;
            }
            loadWeekChart();
        }

        function loadWeekChart() {
            window.pywebview.api.get_week_report(currentWeekOffset).then(data => {
                document.getElementById("week-label").innerText =
                    `${data.week_start} → ${data.week_end}`;

                const chart = document.getElementById("week-chart");
                const legend = document.getElementById("week-legend");
                chart.innerHTML = "";
                legend.innerHTML = "";

                const chartCategories = visibleCategories(data.categories);

                chartCategories.forEach((cat, i) => {
                    const item = document.createElement("div");
                    item.className = "legend-item";

                    const dot = document.createElement("div");
                    dot.className = "legend-dot";
                    dot.style.background = chartColors[i % chartColors.length];

                    const text = document.createElement("span");
                    text.innerText = cat;

                    item.appendChild(dot);
                    item.appendChild(text);
                    legend.appendChild(item);
                });

                const maxDayTotal = Math.max(
                    1,
                    ...data.days.map(day => visibleDayTotal(day))
                );

                data.days.forEach(day => {
                    const dayTotal = visibleDayTotal(day);

                    const wrapper = document.createElement("div");
                    wrapper.className = "bar-wrapper";

                    const bar = document.createElement("div");
                    bar.className = "bar";
                    bar.style.height = `${Math.max(4, (dayTotal / maxDayTotal) * 150)}px`;
                    bar.title = `${day.date} — ${secondsToLabel(dayTotal)}`;

                    chartCategories.forEach((cat, i) => {
                        const seconds = day.totals[cat] || 0;
                        if (seconds <= 0 || dayTotal <= 0) return;

                        const segment = document.createElement("div");
                        segment.style.height = `${(seconds / dayTotal) * 100}%`;
                        segment.style.background = chartColors[i % chartColors.length];
                        segment.style.position = "relative";
                        segment.title = `${cat}: ${secondsToLabel(seconds)}`;

                        if (cat === "CivilAgent") {
                            const catLabel = document.createElement("div");
                            catLabel.style.cssText = "position:absolute; top:1px; left:0; right:0; text-align:center; font-size:8px; color:#000; font-family:monospace; font-weight:bold; pointer-events:none; overflow:hidden;";
                            catLabel.innerText = secondsToLabel(seconds);
                            segment.appendChild(catLabel);
                        }

                        bar.appendChild(segment);
                    });

                    const label = document.createElement("div");
                    label.className = "bar-label";
                    label.innerText = day.label;

                    wrapper.appendChild(bar);
                    wrapper.appendChild(label);
                    chart.appendChild(wrapper);
                });
            });
        }

        function toggleSettings() {
            const panel = document.getElementById('settings-panel');
            const gantt = document.getElementById('gantt-panel');
            const ui = document.getElementById('app-ui');
            const isVisible = panel.style.display === 'block';
            if (!isVisible) {
                gantt.style.display = 'none';
                window.pywebview.api.get_init_data().then(data => {
                    const table = document.getElementById('history-table');
                    table.innerHTML = data.history.map(h => `<tr><td>${h.name}</td><td>${h.time}</td></tr>`).join('');
                    document.getElementById('cat-input').value = data.categories.filter(c => c !== "Nothing").join('\\n');
                    loadWeekChart();
                });
            }
            panel.style.display = isVisible ? 'none' : 'block';
            ui.className = isVisible ? 'main-container' : 'main-container blur';
        }

        function toggleGantt() {
            const panel = document.getElementById('gantt-panel');
            const settings = document.getElementById('settings-panel');
            const ui = document.getElementById('app-ui');
            const isVisible = panel.style.display === 'block';

            if (!isVisible) {
                settings.style.display = 'none';
                ganttDateOffset = 0;
                loadGanttChart();
            }

            panel.style.display = isVisible ? 'none' : 'block';
            ui.className = isVisible ? 'main-container' : 'main-container blur';
        }

        function shiftGanttDay(direction) {
            if (direction === 0) {
                ganttDateOffset = 0;
            } else {
                ganttDateOffset += direction;
            }
            loadGanttChart();
        }

        function loadGanttChart() {
            const targetDate = logicalDateString(addDays(new Date(), ganttDateOffset));
            window.pywebview.api.get_gantt_report(targetDate).then(data => {
                document.getElementById('gantt-date').innerText = data.date;
                renderGantt(data);
            });
        }

        function renderGantt(data) {
            const chart = document.getElementById('gantt-chart');
            chart.innerHTML = '';

            const sessions = data.sessions || [];
            const chartCategories = data.categories.filter(cat => sessions.some(s => s.category === cat));

            if (sessions.length === 0) {
                chart.innerHTML = '<div class="gantt-empty">No sessions recorded for this day yet.</div>';
                return;
            }

            const axis = document.createElement('div');
            axis.className = 'gantt-axis';
            [6, 12, 18, 24, 30].forEach(hour => {
                const mark = document.createElement('div');
                mark.className = 'axis-mark';
                mark.style.left = `${((hour - 6) / 24) * 100}%`;
                mark.innerText = `${String(hour % 24).padStart(2, '0')}:00`;
                axis.appendChild(mark);
            });
            chart.appendChild(axis);

            chartCategories.forEach(cat => {
                const row = document.createElement('div');
                row.className = 'gantt-row';

                const label = document.createElement('div');
                label.className = 'gantt-label';
                label.innerText = cat;
                label.title = cat;

                const lane = document.createElement('div');
                lane.className = 'gantt-lane';

                sessions.filter(s => s.category === cat).forEach(s => {
                    const startMin = Math.max(0, Math.min(1440, timeToTimelineMinutes(s.start)));
                    let endMin = Math.max(0, Math.min(1440, timeToTimelineMinutes(s.end)));
                    if (endMin <= startMin) {
                        endMin = 1440;
                    }
                    const left = (startMin / 1440) * 100;
                    const width = Math.max(0.25, ((endMin - startMin) / 1440) * 100);
                    const colorIndex = Math.max(0, data.categories.indexOf(cat) - 1);

                    const block = document.createElement('div');
                    block.className = 'gantt-block';
                    block.style.left = `${left}%`;
                    block.style.width = `${width}%`;
                    block.style.background = chartColors[colorIndex % chartColors.length];
                    block.title = `${cat}\n${displayTime(s.start)} → ${displayTime(s.end)}\n${secondsToLabel(s.duration || 0)}${s.live ? ' / live' : ''}`;
                    lane.appendChild(block);
                });

                row.appendChild(label);
                row.appendChild(lane);
                chart.appendChild(row);
            });
        }

        function resetCurrent() {
            if(confirm("Reset current session?")) window.pywebview.api.reset_timer();
        }

        function saveSettings() {
            const lines = document.getElementById('cat-input').value.split('\\n').filter(l => l.trim() !== "");
            window.pywebview.api.update_config(lines).then(initUI);
            toggleSettings();
        }

        function initUI(data) {
            cats = data.categories;
            svg.innerHTML = '';
            document.querySelectorAll('.label').forEach(e => e.remove());
            const step = 360 / cats.length;
            cats.forEach((name, i) => {
                const centerAngle = i * step;
                const sRad = (centerAngle - step/2 - 90) * Math.PI / 180, eRad = (centerAngle + step/2 - 90) * Math.PI / 180;
                const x1 = 50 + 50 * Math.cos(sRad), y1 = 50 + 50 * Math.sin(sRad), x2 = 50 + 50 * Math.cos(eRad), y2 = 50 + 50 * Math.sin(eRad);
                const path = document.createElementNS("http://www.w3.org/2000/svg", "path");
                path.setAttribute("d", `M 50 50 L ${x1} ${y1} A 50 50 0 0 1 ${x2} ${y2} Z`);
                path.setAttribute("class", "slice");
                path.onclick = () => select(name, centerAngle);
                svg.appendChild(path);
                const label = document.createElement('div');
                label.className = 'label';
                label.id = 'lbl-' + name;
                label.innerText = name;
                const rad = (centerAngle - 90) * (Math.PI / 180);
                label.style.left = (260 + 210 * Math.cos(rad) - 55) + 'px';
                label.style.top = (260 + 210 * Math.sin(rad) - 10) + 'px';
                document.getElementById('app-ui').appendChild(label);
            });
            const activeIdx = cats.indexOf(data.active);
            select(data.active, activeIdx * step);
        }

        window.addEventListener('pywebviewready', () => window.pywebview.api.get_init_data().then(initUI));

        function select(name, deg) {
            hub.style.transform = `rotate(${deg}deg)`;
            window.pywebview.api.set_category(name);
            document.querySelectorAll('.label').forEach(l => l.classList.remove('active'));
            if(document.getElementById('lbl-' + name)) document.getElementById('lbl-' + name).classList.add('active');
        }

        setInterval(() => {
            if(window.pywebview.api) {
                window.pywebview.api.get_status().then(s => {
                    document.getElementById('session-time').innerText = format(s.session);
                    document.getElementById('total-time').innerText = format(s.total, true);
                    if (document.getElementById('gantt-panel').style.display === 'block') {
                        loadGanttChart();
                    }
                });
            }
        }, 1000);
    </script>
</body>
</html>
"""


if __name__ == '__main__':
    api = TimerApi()
    window = webview.create_window(
        'Task Gauge Pro',
        html=html_content,
        js_api=api,
        width=780,
        height=740,
        resizable=False,
    )
    webview.start(gui='edgechromium')
