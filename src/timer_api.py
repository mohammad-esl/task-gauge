"""TimerApi: the pywebview JS-API bridge. All public (non-underscore)
methods are callable from the frontend as window.pywebview.api.<name>()."""
import os
import time
from datetime import datetime, timedelta

import time_utils
from storage import ConfigStore, HistoryLog, SessionsStore, DailyReportStore
from edit_log import EditLog
from subtasks import SubtaskStore

DEFAULT_CATEGORIES = ["Nothing", "Education", "Work", "Study", "Project 1"]
REPORT_SAVE_INTERVAL = 300  # 5 minutes
BREAK_LOG_THRESHOLD = 10    # seconds; shorter "Nothing" sessions aren't logged
MAX_UNDO_STEPS = 20         # in-memory only; cleared on app restart


class TimerApi:
    def __init__(self, data_dir, static_dir=None):
        self.static_dir = static_dir
        self.config = ConfigStore(os.path.join(data_dir, "config.json"))
        self.history = HistoryLog(os.path.join(data_dir, "timer_history.txt"))
        self.sessions = SessionsStore(os.path.join(data_dir, "timer_sessions.json"))
        self.report = DailyReportStore(os.path.join(data_dir, "daily_report.csv"))
        self.edit_log = EditLog(os.path.join(data_dir, "gantt_edit_log.json"))
        self.subtasks = SubtaskStore(os.path.join(data_dir, "subtasks.json"))
        self._undo_stack = []
        self._subtask_windows = {}

        # In-memory only (see docs/subtasks_plan.md #2-1): which subtask the
        # active/second track is currently tagging sessions with. Never
        # persisted, always resets to None on category change or restart.
        self.active_subtask = None
        self.active_subtask_2 = None

        self.last_report_save = time.time()

        default_data = {
            "categories": list(DEFAULT_CATEGORIES),
            "totals": {name: 0 for name in DEFAULT_CATEGORIES},
            "last_date": time_utils.current_logical_date_str(),
            "dual_task_mode": True,
        }
        self.data = self.config.load(default_data)
        if "last_date" not in self.data:
            self.data["last_date"] = time_utils.current_logical_date_str()
        if "dual_task_mode" not in self.data:
            self.data["dual_task_mode"] = True

        if "Nothing" not in self.data["categories"]:
            self.data["categories"].insert(0, "Nothing")
        if "Nothing" not in self.data["totals"]:
            self.data["totals"]["Nothing"] = 0

        self.active_cat = "Nothing"
        self.start_time = time.time()

        # Second concurrent track, filled via Ctrl+click. None means the
        # slot is empty (no second task running).
        self.active_cat_2 = None
        self.start_time_2 = None

        self._check_daily_reset()

        self._import_missing_history_sessions()

    def _import_missing_history_sessions(self):
        """timer_sessions.json is now the source of truth for the Gantt
        view (needed so sessions can be edited/deleted by id), but it only
        started being written after timer_history.txt already existed.
        One-time backfill: any history.txt session not already present
        gets imported with a fresh id.

        history.txt only stores the end time to whole-minute precision
        (its timestamps are "%Y-%m-%d %H:%M"), while sessions.json is
        precise to the second. Matching on the exact string would treat
        the same real session as "missing" and re-import it as a near
        duplicate a few seconds off from the original, so match on
        (category, end-minute) instead."""
        def minute_key(s):
            end = s.get("end", "")
            return (s.get("category"), end[:16])  # "YYYY-MM-DD HH:MM"

        existing = {minute_key(s) for s in self.sessions.load()}

        to_import = []
        for session in self.history.load_sessions():
            key = minute_key(session)
            if key in existing:
                continue

            to_import.append({
                "date": session["date"],
                "category": session["category"],
                "start": session["start"],
                "end": session["end"],
                "duration": session["duration"],
            })
            existing.add(key)

        if to_import:
            self.sessions.append_many(to_import)

    def save_config(self):
        self.config.save(self.data)

    def _finalize_active_session(self, end_ts):
        duration = int(end_ts - self.start_time)
        if duration <= 0:
            self.start_time = end_ts
            return 0

        self.data["totals"][self.active_cat] = self.data["totals"].get(self.active_cat, 0) + duration
        self._write_to_history(self.active_cat, duration, end_ts=end_ts)
        self._record_session(self.active_cat, self.start_time, end_ts,
                              subtask_id=self.active_subtask)
        self.start_time = end_ts
        return duration

    def _finalize_second_session(self, end_ts):
        """Same as _finalize_active_session but for the optional second
        concurrent track. Only meaningful while active_cat_2 is set. Clears
        the slot (and its subtask selection) — use _split_second_session
        instead when the second track should keep running."""
        if self.active_cat_2 is None:
            return 0

        duration = int(end_ts - self.start_time_2)
        cat = self.active_cat_2
        subtask_id = self.active_subtask_2
        self.active_cat_2 = None
        self.start_time_2 = None
        self.active_subtask_2 = None
        if duration <= 0:
            return 0

        self.data["totals"][cat] = self.data["totals"].get(cat, 0) + duration
        self._write_to_history(cat, duration, end_ts=end_ts)
        self._record_session(cat, end_ts - duration, end_ts, subtask_id=subtask_id)
        return duration

    def _split_second_session(self, end_ts):
        """Like _finalize_second_session but keeps the second track running
        (start_time_2 moves to end_ts instead of clearing the slot). Used
        when switching the second track's subtask mid-session."""
        if self.active_cat_2 is None:
            return 0

        duration = int(end_ts - self.start_time_2)
        if duration <= 0:
            self.start_time_2 = end_ts
            return 0

        cat = self.active_cat_2
        self.data["totals"][cat] = self.data["totals"].get(cat, 0) + duration
        self._write_to_history(cat, duration, end_ts=end_ts)
        self._record_session(cat, self.start_time_2, end_ts,
                              subtask_id=self.active_subtask_2)
        self.start_time_2 = end_ts
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
        changed = False

        start_dt = datetime.fromtimestamp(self.start_time)
        current_dt = datetime.fromtimestamp(now_ts)
        if time_utils.logical_date(start_dt) != time_utils.logical_date(current_dt):
            previous_logical_date = time_utils.logical_date(start_dt).strftime("%Y-%m-%d")
            rollover_ts = time_utils.logical_day_start(time_utils.logical_date(current_dt)).timestamp()
            duration = int(rollover_ts - self.start_time)
            if duration > 0:
                self._write_to_history(self.active_cat, duration, end_ts=rollover_ts)
                self._record_session(self.active_cat, self.start_time, rollover_ts)
                self._add_duration_to_daily_report(previous_logical_date, self.active_cat, duration)
            self.start_time = rollover_ts
            changed = True

        if self.active_cat_2 is not None:
            start_dt_2 = datetime.fromtimestamp(self.start_time_2)
            if time_utils.logical_date(start_dt_2) != time_utils.logical_date(current_dt):
                previous_logical_date_2 = time_utils.logical_date(start_dt_2).strftime("%Y-%m-%d")
                rollover_ts_2 = time_utils.logical_day_start(time_utils.logical_date(current_dt)).timestamp()
                duration_2 = int(rollover_ts_2 - self.start_time_2)
                if duration_2 > 0:
                    self._write_to_history(self.active_cat_2, duration_2, end_ts=rollover_ts_2)
                    self._record_session(self.active_cat_2, self.start_time_2, rollover_ts_2)
                    self._add_duration_to_daily_report(previous_logical_date_2, self.active_cat_2, duration_2)
                self.start_time_2 = rollover_ts_2
                changed = True

        if changed:
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

    def _record_session(self, name, start_ts, end_ts, subtask_id=None):
        duration = int(end_ts - start_ts)
        if duration < 1:
            return

        start_dt = datetime.fromtimestamp(start_ts)
        end_dt = datetime.fromtimestamp(end_ts)
        record = {
            "date": time_utils.logical_date(start_dt).strftime("%Y-%m-%d"),
            "category": name,
            "start": start_dt.strftime("%Y-%m-%d %H:%M:%S"),
            "end": end_dt.strftime("%Y-%m-%d %H:%M:%S"),
            "duration": duration,
        }
        if subtask_id:
            record["subtask_id"] = subtask_id
        self.sessions.append(record)

    def _get_live_totals(self):
        self._align_active_session_to_logical_day()
        totals = self.data["totals"].copy()
        now = time.time()
        session = int(now - self.start_time)
        totals[self.active_cat] = totals.get(self.active_cat, 0) + session
        if self.active_cat_2 is not None:
            session_2 = int(now - self.start_time_2)
            totals[self.active_cat_2] = totals.get(self.active_cat_2, 0) + session_2
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

    def get_range_report(self, start_date, end_date):
        """Total seconds per category across [start_date, end_date] (both
        logical-date strings "YYYY-MM-DD", inclusive). Reads daily_report.csv,
        the same per-day per-category store the week view uses, so it stays
        consistent with WEEKLY VIEW's numbers."""
        self._save_daily_report(time_utils.current_logical_date_str())

        start = datetime.strptime(start_date, "%Y-%m-%d").date()
        end = datetime.strptime(end_date, "%Y-%m-%d").date()
        rows, _ = self.report.load(self.data["categories"])

        totals = {cat: 0 for cat in self.data["categories"]}
        day = start
        while day <= end:
            row = rows.get(day.strftime("%Y-%m-%d"), {})
            for cat in self.data["categories"]:
                totals[cat] += time_utils.parse_hms(row.get(cat, "00:00:00"))
            day += timedelta(days=1)

        return {"start_date": start_date, "end_date": end_date, "totals": totals}

    def get_gantt_report(self, date_str=None):
        self._check_daily_reset()
        self._align_active_session_to_logical_day()

        if not date_str:
            date_str = time_utils.current_logical_date_str()

        # Source of truth: timer_sessions.json. Each block keeps the id of
        # the underlying record (session_id) and whether it was clipped to
        # fit this day (clipped) so the frontend can send edits back
        # against the full original record, not just the visible slice.
        filtered = []
        for session in self.sessions.load():
            clipped = self._clip_session_to_day(session, date_str)
            if not clipped:
                continue
            clipped["session_id"] = session.get("id")
            clipped["clipped"] = (
                clipped["start"] != session.get("start") or clipped["end"] != session.get("end")
            )
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
            clipped["session_id"] = None
            clipped["clipped"] = False
            filtered.append(clipped)

        if self.active_cat_2 is not None:
            duration_2 = int(now - self.start_time_2)
            live_session_2 = {
                "date": date_str,
                "category": self.active_cat_2,
                "start": datetime.fromtimestamp(self.start_time_2).strftime("%Y-%m-%d %H:%M:%S"),
                "end": datetime.fromtimestamp(now).strftime("%Y-%m-%d %H:%M:%S"),
                "duration": duration_2,
                "live": True,
                "source": "live",
            }
            clipped_2 = self._clip_session_to_day(live_session_2, date_str)
            if duration_2 > 0 and clipped_2:
                clipped_2["session_id"] = None
                clipped_2["clipped"] = False
                clipped_2["slot"] = 2
                filtered.append(clipped_2)

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

    def _resync_day(self, date_str):
        """Recompute totals/daily_report for a logical day directly from
        timer_sessions.json. Called after any manual edit/delete/create so
        both the CSV and (for today) the in-memory running totals shown on
        the main dial stay consistent with the session records, which are
        now the source of truth for history."""
        day_seconds = {}
        for session in self.sessions.load():
            if session.get("date") != date_str:
                continue
            cat = session.get("category")
            day_seconds[cat] = day_seconds.get(cat, 0) + int(session.get("duration", 0))

        rows, fieldnames = self.report.load(self.data["categories"])
        for cat in day_seconds:
            if cat not in fieldnames:
                fieldnames.append(cat)

        row = rows.get(date_str, {"date": date_str})
        for cat in fieldnames:
            if cat == "date":
                continue
            row[cat] = time_utils.format_hms(day_seconds.get(cat, 0))
        rows[date_str] = row
        self.report.save(rows, fieldnames)

        # today's dial total = finalized sessions today (just recomputed)
        # plus whatever's still accumulating on the current live session.
        if date_str == time_utils.current_logical_date_str():
            for cat in self.data["categories"]:
                self.data["totals"][cat] = day_seconds.get(cat, 0)
            if self.active_cat not in self.data["totals"]:
                self.data["totals"][self.active_cat] = day_seconds.get(self.active_cat, 0)
            self.save_config()

    def _overlaps_existing(self, category, start_dt, end_dt, exclude_session_id=None):
        """True if [start_dt, end_dt) overlaps another session in the same
        category. Used to keep manual Gantt edits (drag or typed) from ever
        producing overlapping blocks."""
        for s in self.sessions.load():
            if s["category"] != category or s.get("id") == exclude_session_id:
                continue
            try:
                s_start = datetime.strptime(s["start"], "%Y-%m-%d %H:%M:%S")
                s_end = datetime.strptime(s["end"], "%Y-%m-%d %H:%M:%S")
            except Exception:
                continue
            if start_dt < s_end and end_dt > s_start:
                return True
        return False

    def _push_undo(self, action, session_id, before, after):
        self._undo_stack.append({
            "action": action, "session_id": session_id, "before": before, "after": after,
        })
        if len(self._undo_stack) > MAX_UNDO_STEPS:
            self._undo_stack.pop(0)
        self.edit_log.record(action, session_id, before, after)

    def update_gantt_session(self, session_id, start=None, end=None, category=None, subtask_id=None):
        """Edit a session's start/end/category (used for both drag-resize
        and typed-time edits in the Gantt view). Returns the updated
        session, or None if session_id doesn't exist."""
        session = self.sessions.get(session_id)
        if session is None:
            return None

        before = dict(session)
        new_start = start or session["start"]
        new_end = end or session["end"]

        try:
            start_dt = datetime.strptime(new_start, "%Y-%m-%d %H:%M:%S")
            end_dt = datetime.strptime(new_end, "%Y-%m-%d %H:%M:%S")
        except Exception:
            return None

        if end_dt <= start_dt:
            return None

        new_category = category or session["category"]
        if self._overlaps_existing(new_category, start_dt, end_dt, exclude_session_id=session_id):
            return None

        fields = {
            "start": start_dt.strftime("%Y-%m-%d %H:%M:%S"),
            "end": end_dt.strftime("%Y-%m-%d %H:%M:%S"),
            "duration": int((end_dt - start_dt).total_seconds()),
            "date": time_utils.logical_date(start_dt).strftime("%Y-%m-%d"),
        }
        if category:
            fields["category"] = category
        if subtask_id is not None:
            fields["subtask_id"] = subtask_id

        old_date = session["date"]
        updated = self.sessions.update(session_id, **fields)

        self._resync_day(old_date)
        if fields["date"] != old_date:
            self._resync_day(fields["date"])

        self._push_undo("update", session_id, before, dict(updated))
        return updated

    def delete_gantt_session(self, session_id):
        session = self.sessions.get(session_id)
        if session is None:
            return {"status": "not_found"}

        date_str = session["date"]
        before = dict(session)
        self.sessions.delete(session_id)
        self._resync_day(date_str)

        self._push_undo("delete", session_id, before, None)
        return {"status": "deleted"}

    def create_gantt_session(self, category, start, end, subtask_id=None):
        try:
            start_dt = datetime.strptime(start, "%Y-%m-%d %H:%M:%S")
            end_dt = datetime.strptime(end, "%Y-%m-%d %H:%M:%S")
        except Exception:
            return None

        if end_dt <= start_dt or category not in self.data["categories"]:
            return None

        if self._overlaps_existing(category, start_dt, end_dt):
            return None

        date_str = time_utils.logical_date(start_dt).strftime("%Y-%m-%d")
        new_session = {
            "date": date_str,
            "category": category,
            "start": start_dt.strftime("%Y-%m-%d %H:%M:%S"),
            "end": end_dt.strftime("%Y-%m-%d %H:%M:%S"),
            "duration": int((end_dt - start_dt).total_seconds()),
        }
        if subtask_id:
            new_session["subtask_id"] = subtask_id
        session_id = self.sessions.append(new_session)

        self._resync_day(date_str)
        created = self.sessions.get(session_id)

        self._push_undo("create", session_id, None, dict(created))
        return created

    def undo_last_gantt_edit(self):
        """Reverses the most recent create/update/delete made in this
        session (in-memory stack; cleared on restart). Returns the
        reversed entry's action, or None if there's nothing to undo."""
        if not self._undo_stack:
            return None

        entry = self._undo_stack.pop()
        action, session_id, before, after = (
            entry["action"], entry["session_id"], entry["before"], entry["after"],
        )
        dates_to_resync = set()

        if action == "create":
            session = self.sessions.get(session_id)
            if session:
                dates_to_resync.add(session["date"])
                self.sessions.delete(session_id)
        elif action == "delete":
            new_id = self.sessions.append(before)
            dates_to_resync.add(before["date"])
            session_id = new_id  # the restored record gets a new id
        elif action == "update":
            current = self.sessions.get(session_id)
            if current:
                dates_to_resync.add(current["date"])
            self.sessions.update(session_id, **{k: v for k, v in before.items() if k != "id"})
            dates_to_resync.add(before["date"])

        for date_str in dates_to_resync:
            self._resync_day(date_str)

        self.edit_log.record(f"undo:{action}", session_id, after, before)
        return action

    def _check_daily_reset(self):
        today = time_utils.logical_date(datetime.now())
        last = datetime.strptime(self.data["last_date"], "%Y-%m-%d").date()

        if today != last:
            rollover_ts = time_utils.logical_day_start(today).timestamp()
            self._finalize_active_session(rollover_ts)
            self._finalize_second_session(rollover_ts)
            self._save_daily_report(self.data["last_date"])

            self.data["totals"] = {k: 0 for k in self.data["categories"]}
            self.data["last_date"] = today.strftime("%Y-%m-%d")
            self.active_subtask = None
            self.active_subtask_2 = None

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

    def categories_with_history(self):
        """Category names that have at least one recorded session, so the
        settings UI can warn before deleting one (deleting a category only
        drops its running total from config.json — its past sessions stay
        in timer_sessions.json/history/daily_report untouched, just no
        longer shown on the dial or dashboard)."""
        return sorted({s.get("category") for s in self.sessions.load() if s.get("category")})

    def get_init_data(self):
        history_list = [{"name": k, "time": "{}h {}m {}s".format(*time_utils.get_hms(v))}
                        for k, v in self.data["totals"].items()]
        has_subtasks = {cat: bool(self.subtasks.list_for(cat)) for cat in self.data["categories"]}
        return {
            "categories": self.data["categories"],
            "active": self.active_cat,
            "active_2": self.active_cat_2,
            "active_subtask": self.active_subtask,
            "active_subtask_2": self.active_subtask_2,
            "has_subtasks": has_subtasks,
            "dual_task_mode": self.data["dual_task_mode"],
            "history": history_list,
        }

    def set_category(self, name, as_second=False):
        """Plain click (as_second=False) always sets the primary task.
        Ctrl+click (as_second=True) targets the second track; clicking the
        already-active second task again clears that slot."""
        self._check_daily_reset()
        now = time.time()

        if as_second:
            if name == self.active_cat_2:
                self._finalize_second_session(now)
            else:
                self._finalize_second_session(now)
                self.active_cat_2 = name
                self.start_time_2 = now
                self.active_subtask_2 = None
        else:
            self._finalize_active_session(now)
            self.active_cat = name
            self.start_time = now
            self.active_subtask = None

        self.save_config()
        self._save_daily_report(time_utils.current_logical_date_str())
        self.last_report_save = time.time()

        return {"status": "success"}

    def reset_timer(self):
        self._check_daily_reset()
        now = time.time()
        self._finalize_active_session(now)
        self._finalize_second_session(now)
        self.save_config()
        return {"status": "reset"}

    def update_config(self, new_cats):
        now = time.time()
        self._finalize_active_session(now)
        self._finalize_second_session(now)

        if "Nothing" in new_cats:
            new_cats.remove("Nothing")
        new_cats.insert(0, "Nothing")

        removed = set(self.data["categories"]) - set(new_cats)
        for name in removed:
            self.subtasks.drop_category(name)

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
        result = {
            "active": self.active_cat,
            "session": session,
            "total": self.data["totals"].get(self.active_cat, 0) + session,
            "dual_task_mode": self.data["dual_task_mode"],
            "active_2": None,
            "active_subtask": self.active_subtask,
            "active_subtask_2": self.active_subtask_2,
        }
        if self.active_cat_2 is not None:
            session_2 = int(now - self.start_time_2)
            result["active_2"] = self.active_cat_2
            result["session_2"] = session_2
            result["total_2"] = self.data["totals"].get(self.active_cat_2, 0) + session_2
        return result

    # ------------------------------------------------------------------
    # Subtasks: management + optional active-selection + reports.
    # subtask_id is purely a label on a session record — no existing
    # totals/report/gantt code path reads it.
    # ------------------------------------------------------------------

    def get_subtasks(self, category):
        return self.subtasks.list_for(category)

    def create_subtask(self, category, name, planned_start=None, planned_end=None):
        return self.subtasks.create(category, name, planned_start=planned_start,
                                     planned_end=planned_end)

    def update_subtask(self, subtask_id, name=None,
                        planned_start=None, planned_end=None, color=None):
        return self.subtasks.update(subtask_id, name=name,
                                     planned_start=planned_start,
                                     planned_end=planned_end, color=color)

    def archive_subtask(self, subtask_id):
        if self.active_subtask == subtask_id:
            self.active_subtask = None
        if self.active_subtask_2 == subtask_id:
            self.active_subtask_2 = None
        return {"status": "archived" if self.subtasks.archive(subtask_id) else "not_found"}

    def reorder_subtasks(self, category, ids):
        self.subtasks.reorder(category, ids)
        return {"status": "ok"}

    def set_active_subtask(self, subtask_id=None, as_second=False):
        now = time.time()
        target_cat = self.active_cat_2 if as_second else self.active_cat
        if target_cat is None:
            return {"status": "no_active_task"}

        if subtask_id is not None:
            found = self.subtasks.get(subtask_id)
            if not found or found[0] != target_cat:
                return {"status": "invalid"}

        if as_second:
            self._split_second_session(now)
            self.active_subtask_2 = subtask_id
        else:
            self._finalize_active_session(now)
            self.active_subtask = subtask_id

        self.save_config()
        self._save_daily_report(time_utils.current_logical_date_str())
        self.last_report_save = time.time()

        return {"status": "ok", "active_subtask": subtask_id}

    def get_active_subtask(self):
        return {"active": self.active_subtask, "active_2": self.active_subtask_2}

    def set_session_subtask(self, session_id, subtask_id=None):
        """Retroactively (re)labels an already-recorded session. Category
        time is untouched, so _resync_day is unnecessary here."""
        session = self.sessions.get(session_id)
        if session is None:
            return None
        return self.sessions.update(session_id, subtask_id=subtask_id)

    def get_subtask_gantt(self, category, date_str=None):
        """Same clip/live/rollover logic as get_gantt_report, filtered down
        to one category and relabeled by subtask instead of by category."""
        base = self.get_gantt_report(date_str)
        subs = self.subtasks.list_for(category)
        rows = [{"id": None, "name": "بدون زیرتسک"}] + \
               [{"id": s["id"], "name": s["name"]} for s in subs]

        sessions = []
        for s in base["sessions"]:
            if s.get("category") != category:
                continue
            s = dict(s)
            if s.get("live"):
                s["subtask_id"] = (self.active_subtask_2 if s.get("slot") == 2
                                    else self.active_subtask)
            else:
                rec = self.sessions.get(s.get("session_id"))
                s["subtask_id"] = (rec or {}).get("subtask_id")
            sessions.append(s)

        return {"date": base["date"], "category": category,
                "rows": rows, "sessions": sessions}

    def get_subtask_range_report(self, category, start_date, end_date):
        """Seconds spent per subtask (plus "no subtask") across a date
        range, computed straight from timer_sessions.json records."""
        subs = self.subtasks.list_for(category)
        totals = {s["id"]: 0 for s in subs}
        totals[None] = 0

        for session in self.sessions.load():
            if session.get("category") != category:
                continue
            date_str = session.get("date", "")
            if not (start_date <= date_str <= end_date):
                continue
            sid = session.get("subtask_id")
            totals[sid] = totals.get(sid, 0) + int(session.get("duration", 0))

        return {"category": category, "start_date": start_date,
                "end_date": end_date, "totals": totals}

    def get_subtask_summary(self, category):
        subs = self.subtasks.list_for(category)
        spent = {s["id"]: 0 for s in subs}
        last_activity = {s["id"]: None for s in subs}

        for session in self.sessions.load():
            if session.get("category") != category:
                continue
            sid = session.get("subtask_id")
            if sid not in spent:
                continue
            spent[sid] += int(session.get("duration", 0))
            end = session.get("end")
            if end and (last_activity[sid] is None or end > last_activity[sid]):
                last_activity[sid] = end

        return [{
            "id": s["id"],
            "name": s["name"],
            "planned_start": s.get("planned_start"),
            "planned_end": s.get("planned_end"),
            "spent": spent.get(s["id"], 0),
            "last_activity": last_activity.get(s["id"]),
        } for s in subs]

    def open_subtask_window(self, category):
        import webview
        from urllib.parse import quote

        if category in self._subtask_windows:
            try:
                self._subtask_windows[category].show()
                return {"status": "focused"}
            except Exception:
                del self._subtask_windows[category]

        url = os.path.join(self.static_dir, "subtasks.html") + "?category=" + quote(category)
        win = webview.create_window("Subtasks — " + category, url=url,
                                     js_api=self, width=980, height=760)
        win.events.closed += lambda: self._subtask_windows.pop(category, None)
        self._subtask_windows[category] = win
        return {"status": "opened"}
