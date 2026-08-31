import json
import time

from timer_api import TimerApi


def test_fresh_instance_defaults_to_nothing(tmp_path):
    api = TimerApi(str(tmp_path))
    assert api.active_cat == "Nothing"
    assert "Nothing" in api.data["categories"]


def test_construction_with_stale_last_date_triggers_rollover_without_crash(tmp_path):
    config_path = tmp_path / "config.json"
    config_path.write_text(json.dumps({
        "categories": ["Nothing", "Work"],
        "totals": {"Nothing": 0, "Work": 100},
        "last_date": "2000-01-01",
        "dual_task_mode": True,
    }))

    api = TimerApi(str(tmp_path))  # day rollover fires during __init__
    assert api.active_cat == "Nothing"
    assert api.data["last_date"] != "2000-01-01"


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
    assert {"active", "session", "total", "dual_task_mode", "active_2"} <= set(status.keys())
    assert status["active"] == "Nothing"
    assert status["session"] >= 0


def test_update_config_keeps_nothing_first(tmp_path):
    api = TimerApi(str(tmp_path))
    result = api.update_config(["Work", "Study"])
    assert result["categories"][0] == "Nothing"
    assert "Work" in result["categories"]
    assert "Study" in result["categories"]


def test_dual_task_mode_always_on(tmp_path):
    api = TimerApi(str(tmp_path))
    assert api.data["dual_task_mode"] is True
    assert api.active_cat_2 is None


def test_set_category_plain_click_replaces_active_as_before(tmp_path):
    api = TimerApi(str(tmp_path))
    api.data["categories"].extend(["Work", "Study"])
    api.set_category("Work")
    api.set_category("Study")
    assert api.active_cat == "Study"
    assert api.active_cat_2 is None


def test_ctrl_click_starts_second_track_without_disturbing_first(tmp_path):
    api = TimerApi(str(tmp_path))
    api.data["categories"].extend(["Work", "Study"])

    api.set_category("Work")
    assert api.active_cat == "Work"
    assert api.active_cat_2 is None

    api.set_category("Study", as_second=True)
    assert api.active_cat == "Work"       # first track untouched
    assert api.active_cat_2 == "Study"    # second track now running


def test_ctrl_click_on_active_second_track_stops_it(tmp_path):
    api = TimerApi(str(tmp_path))
    api.data["categories"].extend(["Work", "Study"])
    api.set_category("Work")
    api.set_category("Study", as_second=True)
    assert api.active_cat_2 == "Study"

    api.set_category("Study", as_second=True)  # ctrl+click the active second task again
    assert api.active_cat_2 is None
    assert api.active_cat == "Work"


def test_ctrl_click_a_different_category_replaces_second_track(tmp_path):
    api = TimerApi(str(tmp_path))
    api.data["categories"].extend(["Work", "Study", "Project 2"])
    api.set_category("Work")
    api.set_category("Study", as_second=True)
    assert api.active_cat_2 == "Study"

    api.set_category("Project 2", as_second=True)
    assert api.active_cat == "Work"
    assert api.active_cat_2 == "Project 2"


def test_plain_click_while_second_track_running_only_changes_first_track(tmp_path):
    api = TimerApi(str(tmp_path))
    api.data["categories"].extend(["Work", "Study", "Project 2"])
    api.set_category("Work")
    api.set_category("Study", as_second=True)

    api.set_category("Project 2")  # plain click always targets the primary track
    assert api.active_cat == "Project 2"
    assert api.active_cat_2 == "Study"  # second track untouched


def test_get_status_includes_second_track_when_active(tmp_path):
    api = TimerApi(str(tmp_path))
    api.data["categories"].extend(["Work", "Study"])
    api.set_category("Work")
    api.set_category("Study", as_second=True)

    status = api.get_status()
    assert status["dual_task_mode"] is True
    assert status["active_2"] == "Study"
    assert status["session_2"] >= 0


def test_get_gantt_report_includes_both_live_sessions_in_dual_mode(tmp_path):
    api = TimerApi(str(tmp_path))
    api.data["categories"].extend(["Work", "Study"])
    api.set_category("Work")
    api.set_category("Study", as_second=True)
    api.start_time = time.time() - 60
    api.start_time_2 = time.time() - 30

    report = api.get_gantt_report()
    live_sessions = [s for s in report["sessions"] if s.get("live")]
    assert len(live_sessions) == 2
    assert {s["category"] for s in live_sessions} == {"Work", "Study"}


def test_categories_with_history_reflects_recorded_sessions(tmp_path):
    api = TimerApi(str(tmp_path))
    api.data["categories"].append("Work")
    api.sessions.append({
        "date": "2026-08-06", "category": "Work",
        "start": "2026-08-06 10:00:00", "end": "2026-08-06 11:00:00", "duration": 3600,
    })

    assert api.categories_with_history() == ["Work"]


def test_categories_with_history_empty_when_no_sessions(tmp_path):
    api = TimerApi(str(tmp_path))
    assert api.categories_with_history() == []


def test_get_week_report_has_seven_days(tmp_path):
    api = TimerApi(str(tmp_path))
    report = api.get_week_report(0)
    assert len(report["days"]) == 7
    assert all("totals" in d for d in report["days"])


def test_get_range_report_sums_daily_totals_for_category(tmp_path):
    api = TimerApi(str(tmp_path))
    rows, fieldnames = api.report.load(api.data["categories"])
    rows["2026-08-10"] = {"date": "2026-08-10", "Education": "01:00:00", "Nothing": "00:00:00"}
    rows["2026-08-11"] = {"date": "2026-08-11", "Education": "02:00:00", "Nothing": "00:00:00"}
    api.report.save(rows, fieldnames)

    report = api.get_range_report("2026-08-10", "2026-08-11")
    assert report["totals"]["Education"] == 3 * 3600


def test_get_range_report_single_day_matches_that_day(tmp_path):
    api = TimerApi(str(tmp_path))
    rows, fieldnames = api.report.load(api.data["categories"])
    rows["2026-08-10"] = {"date": "2026-08-10", "Education": "00:30:00", "Nothing": "00:00:00"}
    api.report.save(rows, fieldnames)

    report = api.get_range_report("2026-08-10", "2026-08-10")
    assert report["totals"]["Education"] == 1800


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


def test_create_gantt_session_rejects_overlap_in_same_category(tmp_path):
    api = TimerApi(str(tmp_path))
    api.data["categories"].append("Work")
    api.sessions.append({
        "date": "2026-08-06", "category": "Work",
        "start": "2026-08-06 10:00:00", "end": "2026-08-06 11:00:00", "duration": 3600,
    })

    result = api.create_gantt_session("Work", "2026-08-06 10:30:00", "2026-08-06 11:30:00")
    assert result is None


def test_create_gantt_session_allows_touching_edges_and_other_categories(tmp_path):
    api = TimerApi(str(tmp_path))
    api.data["categories"].extend(["Work", "Study"])
    api.sessions.append({
        "date": "2026-08-06", "category": "Work",
        "start": "2026-08-06 10:00:00", "end": "2026-08-06 11:00:00", "duration": 3600,
    })

    # exactly flush against the existing block's end: allowed
    flush = api.create_gantt_session("Work", "2026-08-06 11:00:00", "2026-08-06 12:00:00")
    assert flush is not None

    # same time range but a different category: allowed
    other_cat = api.create_gantt_session("Study", "2026-08-06 10:00:00", "2026-08-06 11:00:00")
    assert other_cat is not None


def test_update_gantt_session_rejects_overlap_in_same_category(tmp_path):
    api = TimerApi(str(tmp_path))
    api.data["categories"].append("Work")
    api.sessions.append({
        "date": "2026-08-06", "category": "Work",
        "start": "2026-08-06 10:00:00", "end": "2026-08-06 11:00:00", "duration": 3600,
    })
    moving_id = api.sessions.append({
        "date": "2026-08-06", "category": "Work",
        "start": "2026-08-06 12:00:00", "end": "2026-08-06 13:00:00", "duration": 3600,
    })

    result = api.update_gantt_session(moving_id, start="2026-08-06 10:30:00", end="2026-08-06 11:30:00")
    assert result is None
    # original record is untouched
    assert api.sessions.get(moving_id)["start"] == "2026-08-06 12:00:00"


def test_update_gantt_session_does_not_block_against_itself(tmp_path):
    api = TimerApi(str(tmp_path))
    api.data["categories"].append("Work")
    session_id = api.sessions.append({
        "date": "2026-08-06", "category": "Work",
        "start": "2026-08-06 10:00:00", "end": "2026-08-06 11:00:00", "duration": 3600,
    })

    # a tiny resize that still overlaps its own old range should succeed
    result = api.update_gantt_session(session_id, start="2026-08-06 10:05:00", end="2026-08-06 11:00:00")
    assert result is not None
    assert result["start"] == "2026-08-06 10:05:00"


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
