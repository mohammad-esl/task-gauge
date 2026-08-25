# Version Log

## v1.5 — 2026-08-25
- Performance cleanup: reduced repeated disk I/O caused by 1-second polling.
  - `timer_history.txt` parsing is now cached in memory and only re-parsed when the file's mtime changes (previously re-parsed on every Gantt refresh).
  - `daily_report.csv` reads/writes are routed through a shared in-memory cache instead of each report function re-reading and fully rewriting the file.
  - `timer_sessions.json` is now cached in memory after first load instead of being re-read from disk on every session write.
  - Merged the duplicated CSV read/rewrite logic in `_add_duration_to_daily_report` and `_save_daily_report` into shared `_load_report_rows` / `_write_report_rows` helpers.
  - Gantt chart auto-refresh while the panel is open was decoupled from the 1-second live-timer tick and now refreshes every 5 seconds instead.
- No data file formats changed; existing `config.json`, `timer_history.txt`, `daily_report.csv`, and `timer_sessions.json` remain fully compatible.

## v1.4 — 2026-08-25
- Removed `daily_report.json`, a stale/untracked personal data file that had been committed by mistake and was unused by the app.
- Added `requirements.txt` (`pywebview==6.2.1`) for reproducible installs; updated README install instructions to match.
- Minor whitespace cleanup in `timer.py`.

## v1.3 — 2026-07-31
- Added `run.bat` background launcher (`pythonw.exe`, no console window) so the app no longer closes when its terminal is closed.
- Added a Windows Startup shortcut so the app launches automatically at login.
- Added a per-segment hour label on the "CivilAgent" bar in the weekly stacked chart.
- `venv/` added to `.gitignore`.

## v1.2 — 2026-07-01 to 2026-07-31
- Fixed weekly view to start weeks on Saturday instead of Sunday.
- Fixed the logical day start time (6 AM boundary) handling.
- Added Gantt/timeline view showing session start and end times per day.

## v1.1 — 2026-05-01 to 2026-05-07
- Added weekly stacked bar chart for category time totals.
- Added 5-minute autosave and tabular daily report view.
- Added daily reset with a persisted daily report file.

## v1.0 — 2026-05-01
- Initial release: category-based timer with circular selector UI, session totals, and history log (`timer_history.txt`).
