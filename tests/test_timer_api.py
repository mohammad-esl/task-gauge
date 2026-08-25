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
