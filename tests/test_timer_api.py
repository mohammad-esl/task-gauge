import time

from timer_api import TimerApi


def test_fresh_instance_defaults_to_nothing(tmp_path):
    api = TimerApi(str(tmp_path))
    assert api.active_cat == "Nothing"
    assert "Nothing" in api.data["categories"]


def test_set_category_switches_active_and_persists_config(tmp_path):
    api = TimerApi(str(tmp_path))
    api.data["categories"].append("Work")
    api.data["totals"]["Work"] = 0

    result = api.set_category("Work")
    assert result == {"status": "success"}
    assert api.active_cat == "Work"

    # config.json should reflect the switch after a fresh load
    reloaded = TimerApi(str(tmp_path))
    assert reloaded.active_cat == "Nothing"  # active_cat isn't persisted, only totals are
    assert "Work" in reloaded.data["categories"]


def test_finalize_active_session_accumulates_totals(tmp_path):
    api = TimerApi(str(tmp_path))
    api.data["categories"].append("Work")
    api.data["totals"]["Work"] = 0
    api.active_cat = "Work"
    api.start_time = time.time() - 30  # pretend we've been on Work for 30s

    duration = api._finalize_active_session(time.time())
    assert duration >= 30
    assert api.data["totals"]["Work"] >= 30


def test_short_break_is_not_written_to_history(tmp_path):
    api = TimerApi(str(tmp_path))
    api.active_cat = "Nothing"
    api.start_time = time.time() - 5  # below the 10s break-logging threshold

    api._finalize_active_session(time.time())
    assert api.history.load_sessions() == []


def test_get_status_returns_expected_shape(tmp_path):
    api = TimerApi(str(tmp_path))
    status = api.get_status()
    assert set(status.keys()) == {"active", "session", "total"}
    assert status["active"] == "Nothing"
    assert status["session"] >= 0


def test_update_config_keeps_nothing_first(tmp_path):
    api = TimerApi(str(tmp_path))
    result = api.update_config(["Work", "Study"])
    assert result["categories"][0] == "Nothing"
    assert "Work" in result["categories"]
    assert "Study" in result["categories"]


def test_get_week_report_has_seven_days(tmp_path):
    api = TimerApi(str(tmp_path))
    report = api.get_week_report(0)
    assert len(report["days"]) == 7
    assert all("totals" in d for d in report["days"])


def test_get_gantt_report_includes_live_session(tmp_path):
    api = TimerApi(str(tmp_path))
    api.start_time = time.time() - 120  # 2 minutes into the current session
    report = api.get_gantt_report()
    assert len(report["sessions"]) >= 1
    assert any(s.get("live") for s in report["sessions"])


def test_update_gantt_session_changes_start_and_end(tmp_path):
    api = TimerApi(str(tmp_path))
    session_id = api.sessions.append({
        "date": "2026-08-06", "category": "Work",
        "start": "2026-08-06 10:00:00", "end": "2026-08-06 11:00:00", "duration": 3600,
    })

    updated = api.update_gantt_session(session_id, start="2026-08-06 09:00:00", end="2026-08-06 11:00:00")
    assert updated["start"] == "2026-08-06 09:00:00"
    assert updated["duration"] == 2 * 3600


def test_update_gantt_session_rejects_end_before_start(tmp_path):
    api = TimerApi(str(tmp_path))
    session_id = api.sessions.append({
        "date": "2026-08-06", "category": "Work",
        "start": "2026-08-06 10:00:00", "end": "2026-08-06 11:00:00", "duration": 3600,
    })

    result = api.update_gantt_session(session_id, start="2026-08-06 12:00:00", end="2026-08-06 11:00:00")
    assert result is None
    # original record is untouched
    assert api.sessions.get(session_id)["start"] == "2026-08-06 10:00:00"


def test_update_gantt_session_unknown_id_returns_none(tmp_path):
    api = TimerApi(str(tmp_path))
    assert api.update_gantt_session("does-not-exist", start="2026-08-06 10:00:00", end="2026-08-06 11:00:00") is None


def test_update_gantt_session_resyncs_daily_report(tmp_path):
    api = TimerApi(str(tmp_path))
    api.data["categories"].append("Work")
    session_id = api.sessions.append({
        "date": "2026-08-06", "category": "Work",
        "start": "2026-08-06 10:00:00", "end": "2026-08-06 11:00:00", "duration": 3600,
    })
    api._resync_day("2026-08-06")
    rows, _ = api.report.load(api.data["categories"])
    assert rows["2026-08-06"]["Work"] == "01:00:00"

    api.update_gantt_session(session_id, start="2026-08-06 10:00:00", end="2026-08-06 12:00:00")
    rows, _ = api.report.load(api.data["categories"])
    assert rows["2026-08-06"]["Work"] == "02:00:00"


def test_delete_gantt_session_removes_it_and_resyncs(tmp_path):
    api = TimerApi(str(tmp_path))
    api.data["categories"].append("Work")
    session_id = api.sessions.append({
        "date": "2026-08-06", "category": "Work",
        "start": "2026-08-06 10:00:00", "end": "2026-08-06 11:00:00", "duration": 3600,
    })
    api._resync_day("2026-08-06")

    result = api.delete_gantt_session(session_id)
    assert result == {"status": "deleted"}
    assert api.sessions.get(session_id) is None

    rows, _ = api.report.load(api.data["categories"])
    assert rows["2026-08-06"]["Work"] == "00:00:00"


def test_delete_gantt_session_unknown_id(tmp_path):
    api = TimerApi(str(tmp_path))
    assert api.delete_gantt_session("does-not-exist") == {"status": "not_found"}


def test_create_gantt_session_adds_a_new_block(tmp_path):
    api = TimerApi(str(tmp_path))
    api.data["categories"].append("Work")
    api.data["totals"]["Work"] = 0

    created = api.create_gantt_session("Work", "2026-08-06 09:00:00", "2026-08-06 10:30:00")
    assert created is not None
    assert created["duration"] == 90 * 60
    assert created["category"] == "Work"


def test_create_gantt_session_rejects_unknown_category(tmp_path):
    api = TimerApi(str(tmp_path))
    result = api.create_gantt_session("NotACategory", "2026-08-06 09:00:00", "2026-08-06 10:00:00")
    assert result is None


def test_create_gantt_session_rejects_end_before_start(tmp_path):
    api = TimerApi(str(tmp_path))
    result = api.create_gantt_session("Nothing", "2026-08-06 10:00:00", "2026-08-06 09:00:00")
    assert result is None


def test_gantt_report_exposes_session_id_and_clipped_flag(tmp_path):
    api = TimerApi(str(tmp_path))
    api.data["categories"].append("Work")
    # a session fully inside one logical day (6am-6am boundary): not clipped
    same_day_id = api.sessions.append({
        "date": "2026-08-06", "category": "Work",
        "start": "2026-08-06 10:00:00", "end": "2026-08-06 11:00:00", "duration": 3600,
    })
    # a session crossing the 6am logical-day boundary: clipped when viewed
    # from either the day it started on or the day it ends on
    api.sessions.append({
        "date": "2026-08-06", "category": "Work",
        "start": "2026-08-06 05:00:00", "end": "2026-08-06 07:00:00", "duration": 2 * 3600,
    })

    report = api.get_gantt_report("2026-08-06")
    by_id = {s["session_id"]: s for s in report["sessions"] if s.get("session_id")}
    assert by_id[same_day_id]["clipped"] is False

    crossing_blocks = [s for s in report["sessions"] if s.get("session_id") not in (same_day_id, None)]
    assert len(crossing_blocks) == 1
    assert crossing_blocks[0]["clipped"] is True


def test_import_missing_history_sessions_backfills_from_history_txt(tmp_path):
    history_path = tmp_path / "timer_history.txt"
    history_path.write_text(
        "2026-08-06 11:20 | [TASK]     Work | Session: 1h 0m 0s | Total: 1h 0m 0s\n",
        encoding="utf-8",
    )

    api = TimerApi(str(tmp_path))
    sessions = api.sessions.load()
    assert any(s["category"] == "Work" and s["end"] == "2026-08-06 11:20:00" for s in sessions)


def test_import_does_not_duplicate_a_session_whose_seconds_differ_from_history(tmp_path):
    """Regression test: history.txt only records end times to the minute
    ("%H:%M"), while sessions.json is precise to the second. An earlier
    version of the import matched on the exact time string, so a session
    already in sessions.json with real seconds (e.g. :32) never matched
    its :00-rounded history.txt counterpart and got re-imported as a
    near-duplicate every time the app started."""
    sessions_path = tmp_path / "timer_sessions.json"
    sessions_path.write_text(
        '[{"date": "2026-08-06", "category": "Work", '
        '"start": "2026-08-06 10:00:00", "end": "2026-08-06 11:20:32", "duration": 4832}]',
        encoding="utf-8",
    )
    history_path = tmp_path / "timer_history.txt"
    history_path.write_text(
        "2026-08-06 11:20 | [TASK]     Work | Session: 1h 20m 0s | Total: 1h 20m 0s\n",
        encoding="utf-8",
    )

    api = TimerApi(str(tmp_path))
    matching = [s for s in api.sessions.load() if s["category"] == "Work"]
    assert len(matching) == 1


def test_import_missing_history_sessions_does_not_duplicate_on_reload(tmp_path):
    history_path = tmp_path / "timer_history.txt"
    history_path.write_text(
        "2026-08-06 11:20 | [TASK]     Work | Session: 1h 0m 0s | Total: 1h 0m 0s\n",
        encoding="utf-8",
    )

    TimerApi(str(tmp_path))
    api2 = TimerApi(str(tmp_path))
    matching = [s for s in api2.sessions.load() if s["category"] == "Work" and s["end"] == "2026-08-06 11:20:00"]
    assert len(matching) == 1


def test_undo_reverses_create(tmp_path):
    api = TimerApi(str(tmp_path))
    api.data["categories"].append("Work")
    created = api.create_gantt_session("Work", "2026-08-06 09:00:00", "2026-08-06 10:00:00")

    action = api.undo_last_gantt_edit()
    assert action == "create"
    assert api.sessions.get(created["id"]) is None


def test_undo_reverses_delete(tmp_path):
    api = TimerApi(str(tmp_path))
    api.data["categories"].append("Work")
    session_id = api.sessions.append({
        "date": "2026-08-06", "category": "Work",
        "start": "2026-08-06 10:00:00", "end": "2026-08-06 11:00:00", "duration": 3600,
    })
    api.delete_gantt_session(session_id)
    assert api.sessions.get(session_id) is None

    action = api.undo_last_gantt_edit()
    assert action == "delete"
    restored = [s for s in api.sessions.load() if s["category"] == "Work" and s["start"] == "2026-08-06 10:00:00"]
    assert len(restored) == 1


def test_undo_reverses_update(tmp_path):
    api = TimerApi(str(tmp_path))
    api.data["categories"].append("Work")
    session_id = api.sessions.append({
        "date": "2026-08-06", "category": "Work",
        "start": "2026-08-06 10:00:00", "end": "2026-08-06 11:00:00", "duration": 3600,
    })
    api.update_gantt_session(session_id, start="2026-08-06 09:00:00", end="2026-08-06 11:00:00")
    assert api.sessions.get(session_id)["start"] == "2026-08-06 09:00:00"

    action = api.undo_last_gantt_edit()
    assert action == "update"
    assert api.sessions.get(session_id)["start"] == "2026-08-06 10:00:00"


def test_undo_with_empty_stack_returns_none(tmp_path):
    api = TimerApi(str(tmp_path))
    assert api.undo_last_gantt_edit() is None


def test_undo_stack_is_last_in_first_out(tmp_path):
    api = TimerApi(str(tmp_path))
    api.data["categories"].append("Work")
    first_id = api.sessions.append({
        "date": "2026-08-06", "category": "Work",
        "start": "2026-08-06 10:00:00", "end": "2026-08-06 11:00:00", "duration": 3600,
    })
    api.update_gantt_session(first_id, start="2026-08-06 09:00:00", end="2026-08-06 11:00:00")
    created = api.create_gantt_session("Work", "2026-08-06 12:00:00", "2026-08-06 13:00:00")

    # last action was the create, so undo should remove that first
    assert api.undo_last_gantt_edit() == "create"
    assert api.sessions.get(created["id"]) is None
    assert api.sessions.get(first_id)["start"] == "2026-08-06 09:00:00"  # update still applied

    # then the update
    assert api.undo_last_gantt_edit() == "update"
    assert api.sessions.get(first_id)["start"] == "2026-08-06 10:00:00"


def test_gantt_edits_are_recorded_in_edit_log(tmp_path):
    api = TimerApi(str(tmp_path))
    api.data["categories"].append("Work")
    created = api.create_gantt_session("Work", "2026-08-06 09:00:00", "2026-08-06 10:00:00")
    api.delete_gantt_session(created["id"])

    import json
    with open(api.edit_log.path, encoding="utf-8") as f:
        entries = json.load(f)

    actions = [e["action"] for e in entries]
    assert actions == ["create", "delete"]
    assert entries[0]["session_id"] == created["id"]
