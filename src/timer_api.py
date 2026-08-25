"""TimerApi: the pywebview JS-API bridge. All public (non-underscore)
methods are callable from the frontend as window.pywebview.api.<name>()."""
import os
import time
from datetime import datetime, timedelta

import time_utils
from storage import ConfigStore, HistoryLog, SessionsStore, DailyReportStore

DEFAULT_CATEGORIES = ["Nothing", "Education", "Work", "Study", "Project 1"]
REPORT_SAVE_INTERVAL = 300  # 5 minutes
BREAK_LOG_THRESHOLD = 10    # seconds; shorter "Nothing" sessions aren't logged


class TimerApi:
    def __init__(self, data_dir):
        self.config = ConfigStore(os.path.join(data_dir, "config.json"))
        self.history = HistoryLog(os.path.join(data_dir, "timer_history.txt"))
        self.sessions = SessionsStore(os.path.join(data_dir, "timer_sessions.json"))
        self.report = DailyReportStore(os.path.join(data_dir, "daily_report.csv"))

        self.last_report_save = time.time()

        default_data = {
            "categories": list(DEFAULT_CATEGORIES),
            "totals": {name: 0 for name in DEFAULT_CATEGORIES},
            "last_date": time_utils.current_logical_date_str(),
        }
        self.data = self.config.load(default_data)
        if "last_date" not in self.data:
            self.data["last_date"] = time_utils.current_logical_date_str()

        self._check_daily_reset()

        if "Nothing" not in self.data["categories"]:
            self.data["categories"].insert(0, "Nothing")
        if "Nothing" not in self.data["totals"]:
            self.data["totals"]["Nothing"] = 0

        self.active_cat = "Nothing"
        self.start_time = time.time()

    def save_config(self):
        self.config.save(self.data)

    def _finalize_active_session(self, end_ts):
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

        rows, fieldnames = self.report.load(self.data["categories"])
        if category not in fieldnames:
            fieldnames.append(category)

        row = rows.get(date_str, {"date": date_str})
        for cat in fieldnames:
            if cat != "date":
                row.setdefault(cat, "00:00:00")

        current_seconds = time_utils.parse_hms(row.get(category, "00:00:00"))
        row[category] = time_utils.format_hms(current_seconds + duration)
        rows[date_str] = row

        self.report.save(rows, fieldnames)

    def _align_active_session_to_logical_day(self):
        now_ts = time.time()
        start_dt = datetime.fromtimestamp(self.start_time)
        current_dt = datetime.fromtimestamp(now_ts)

        if time_utils.logical_date(start_dt) == time_utils.logical_date(current_dt):
            return

        previous_logical_date = time_utils.logical_date(start_dt).strftime("%Y-%m-%d")
        rollover_ts = time_utils.logical_day_start(time_utils.logical_date(current_dt)).timestamp()
        duration = int(rollover_ts - self.start_time)
        if duration > 0:
            self._write_to_history(self.active_cat, duration, end_ts=rollover_ts)
            self._record_session(self.active_cat, self.start_time, rollover_ts)
            self._add_duration_to_daily_report(previous_logical_date, self.active_cat, duration)
        self.start_time = rollover_ts
        self.save_config()

    def _clip_session_to_day(self, session, date_str):
        try:
            start_dt = datetime.strptime(session["start"], "%Y-%m-%d %H:%M:%S")
            end_dt = datetime.strptime(session["end"], "%Y-%m-%d %H:%M:%S")
            day_start = time_utils.logical_day_start(date_str)
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

    def _record_session(self, name, start_ts, end_ts):
        duration = int(end_ts - start_ts)
        if duration < 1:
            return

        start_dt = datetime.fromtimestamp(start_ts)
        end_dt = datetime.fromtimestamp(end_ts)
        self.sessions.append({
            "date": time_utils.logical_date(start_dt).strftime("%Y-%m-%d"),
            "category": name,
            "start": start_dt.strftime("%Y-%m-%d %H:%M:%S"),
            "end": end_dt.strftime("%Y-%m-%d %H:%M:%S"),
            "duration": duration,
        })

    def _get_live_totals(self):
        self._align_active_session_to_logical_day()
        totals = self.data["totals"].copy()
        session = int(time.time() - self.start_time)
        totals[self.active_cat] = totals.get(self.active_cat, 0) + session
        return totals

    def _save_daily_report(self, date_str):
        totals = self._get_live_totals()
        rows, fieldnames = self.report.load(self.data["categories"])

        row = {"date": date_str}
        for cat in fieldnames:
            if cat != "date":
                row[cat] = time_utils.format_hms(totals.get(cat, 0))

        rows[date_str] = row
        self.report.save(rows, fieldnames)

    def get_today_report(self):
        self._check_daily_reset()
        return {
            "date": time_utils.current_logical_date_str(),
            "totals": self._get_live_totals(),
        }

    def save_today_report(self):
        today = time_utils.current_logical_date_str()
        self._save_daily_report(today)
        return {"status": "saved"}

    def get_week_report(self, week_offset=0):
        self._save_daily_report(time_utils.current_logical_date_str())

        today = time_utils.logical_date(datetime.now())
        days_since_saturday = (today.weekday() + 2) % 7
        start_of_week = today - timedelta(days=days_since_saturday)
        start_of_week = start_of_week + timedelta(weeks=int(week_offset))
        end_of_week = start_of_week + timedelta(days=6)

        rows, _ = self.report.load(self.data["categories"])

        days = []
        for i in range(7):
            day = start_of_week + timedelta(days=i)
            date_str = day.strftime("%Y-%m-%d")
            row = rows.get(date_str, {})

            totals = {
                cat: time_utils.parse_hms(row.get(cat, "00:00:00"))
                for cat in self.data["categories"]
            }

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
            date_str = time_utils.current_logical_date_str()

        # Primary source: timer_history.txt. Each history row stores the
        # session end time and duration, so we reconstruct:
        # start_time = end_time - duration.
        filtered = []
        for session in self.history.load_sessions():
            clipped = self._clip_session_to_day(session, date_str)
            if clipped:
                filtered.append(clipped)

        # Add the current live session without saving it yet.
        now = time.time()
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
        today = time_utils.logical_date(datetime.now())
        last = datetime.strptime(self.data["last_date"], "%Y-%m-%d").date()

        if today != last:
            rollover_ts = time_utils.logical_day_start(today).timestamp()
            self._finalize_active_session(rollover_ts)
            self._save_daily_report(self.data["last_date"])

            self.data["totals"] = {k: 0 for k in self.data["categories"]}
            self.data["last_date"] = today.strftime("%Y-%m-%d")

            self.history.append(f"\n--- NEW DAY: {self.data['last_date']} ---\n")
            self.save_config()

    def _write_to_history(self, name, session_duration, end_ts=None):
        # We log "Nothing" to history only if it was a significant "break".
        if session_duration < BREAK_LOG_THRESHOLD:
            return

        end_dt = datetime.now() if end_ts is None else datetime.fromtimestamp(end_ts)
        timestamp = end_dt.strftime("%Y-%m-%d %H:%M")
        sh, sm, ss = time_utils.get_hms(session_duration)
        th, tm, ts = time_utils.get_hms(self.data["totals"].get(name, 0))

        prefix = "[BREAK]   " if name == "Nothing" else "[TASK]    "
        log_entry = (f"{timestamp} | {prefix} {name.ljust(15)} | "
                     f"Session: {sh}h {sm}m {ss}s | Total: {th}h {tm}m {ts}s\n")
        self.history.append(log_entry)

    def get_init_data(self):
        history_list = [{"name": k, "time": "{}h {}m {}s".format(*time_utils.get_hms(v))}
                        for k, v in self.data["totals"].items()]
        return {"categories": self.data["categories"], "active": self.active_cat, "history": history_list}

    def set_category(self, name):
        self._check_daily_reset()

        now = time.time()
        self._finalize_active_session(now)
        self.save_config()

        self.active_cat = name
        self.start_time = now

        self._save_daily_report(time_utils.current_logical_date_str())
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

        if "Nothing" in new_cats:
            new_cats.remove("Nothing")
        new_cats.insert(0, "Nothing")

        new_totals = {name: self.data["totals"].get(name, 0) for name in new_cats}
        self.data["categories"], self.data["totals"] = new_cats, new_totals

        self.active_cat = "Nothing"
        self.start_time = time.time()
        self.save_config()
        self._save_daily_report(time_utils.current_logical_date_str())
        return self.get_init_data()

    def get_status(self):
        self._check_daily_reset()
        self._align_active_session_to_logical_day()

        if time.time() - self.last_report_save >= REPORT_SAVE_INTERVAL:
            self._save_daily_report(time_utils.current_logical_date_str())
            self.last_report_save = time.time()

        now = time.time()
        session = int(now - self.start_time)
        return {
            "active": self.active_cat,
            "session": session,
            "total": self.data["totals"].get(self.active_cat, 0) + session,
        }
