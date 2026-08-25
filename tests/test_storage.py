import os

from storage import ConfigStore, HistoryLog, SessionsStore, DailyReportStore


def test_config_store_roundtrip(tmp_path):
    store = ConfigStore(str(tmp_path / "config.json"))
    store.save({"a": 1})
    assert store.load(default={}) == {"a": 1}


def test_config_store_missing_file_returns_default(tmp_path):
    store = ConfigStore(str(tmp_path / "missing.json"))
    assert store.load(default={"x": 1}) == {"x": 1}


def test_config_store_corrupt_file_returns_default(tmp_path):
    path = tmp_path / "config.json"
    path.write_text("not json", encoding="utf-8")
    store = ConfigStore(str(path))
    assert store.load(default={"x": 1}) == {"x": 1}


def test_history_log_parses_task_line(tmp_path):
    path = tmp_path / "history.txt"
    path.write_text(
        "2026-08-06 11:20 | [TASK]     DOE_Crawling (Dr. Gh) | Session: 3h 38m 35s | Total: 3h 38m 35s\n",
        encoding="utf-8",
    )
    log = HistoryLog(str(path))
    sessions = log.load_sessions()
    assert len(sessions) == 1
    s = sessions[0]
    assert s["category"] == "DOE_Crawling (Dr. Gh)"
    assert s["duration"] == 3 * 3600 + 38 * 60 + 35
    assert s["end"] == "2026-08-06 11:20:00"
    assert s["start"] == "2026-08-06 07:41:25"


def test_history_log_cache_invalidates_on_mtime_change(tmp_path):
    path = tmp_path / "history.txt"
    path.write_text(
        "2026-08-06 11:20 | [TASK]     Work | Session: 0h 1m 0s | Total: 0h 1m 0s\n",
        encoding="utf-8",
    )
    log = HistoryLog(str(path))
    first = log.load_sessions()
    assert len(first) == 1

    # append a second line and bump mtime forward so the cache is invalidated
    with open(path, "a", encoding="utf-8") as f:
        f.write("2026-08-06 12:00 | [TASK]     Work | Session: 0h 2m 0s | Total: 0h 3m 0s\n")
    new_mtime = os.path.getmtime(path) + 5
    os.utime(path, (new_mtime, new_mtime))

    second = log.load_sessions()
    assert len(second) == 2


def test_history_log_ignores_malformed_lines(tmp_path):
    path = tmp_path / "history.txt"
    path.write_text("--- NEW DAY: 2026-08-06 ---\nnot a valid history line\n", encoding="utf-8")
    log = HistoryLog(str(path))
    assert log.load_sessions() == []


def test_history_log_missing_file_returns_empty(tmp_path):
    log = HistoryLog(str(tmp_path / "missing.txt"))
    assert log.load_sessions() == []


def test_sessions_store_append_and_load(tmp_path):
    store = SessionsStore(str(tmp_path / "sessions.json"))
    store.append({"category": "Work", "duration": 60})
    store.append({"category": "Study", "duration": 120})
    loaded = store.load()
    assert len(loaded) == 2
    assert loaded[0]["category"] == "Work"


def test_sessions_store_caps_at_max(tmp_path):
    store = SessionsStore(str(tmp_path / "sessions.json"))
    store.MAX_SESSIONS = 3
    for i in range(5):
        store.append({"i": i})
    loaded = store.load()
    assert len(loaded) == 3
    assert [s["i"] for s in loaded] == [2, 3, 4]


def test_sessions_store_append_assigns_id(tmp_path):
    store = SessionsStore(str(tmp_path / "sessions.json"))
    session_id = store.append({"category": "Work"})
    assert session_id
    loaded = store.load()
    assert loaded[0]["id"] == session_id


def test_sessions_store_loading_legacy_file_backfills_ids(tmp_path):
    path = tmp_path / "sessions.json"
    path.write_text('[{"category": "Work", "duration": 60}]', encoding="utf-8")
    store = SessionsStore(str(path))
    loaded = store.load()
    assert loaded[0].get("id")

    # ids are persisted back to disk, not just assigned in memory
    fresh_store = SessionsStore(str(path))
    assert fresh_store.load()[0]["id"] == loaded[0]["id"]


def test_sessions_store_update_by_id(tmp_path):
    store = SessionsStore(str(tmp_path / "sessions.json"))
    session_id = store.append({"category": "Work", "start": "a", "end": "b"})
    updated = store.update(session_id, start="c", end="d")
    assert updated["start"] == "c"
    assert updated["end"] == "d"
    assert updated["category"] == "Work"  # untouched fields survive


def test_sessions_store_update_missing_id_returns_none(tmp_path):
    store = SessionsStore(str(tmp_path / "sessions.json"))
    assert store.update("does-not-exist", start="x") is None


def test_sessions_store_delete_by_id(tmp_path):
    store = SessionsStore(str(tmp_path / "sessions.json"))
    keep_id = store.append({"category": "Work"})
    delete_id = store.append({"category": "Study"})

    assert store.delete(delete_id) is True
    remaining = store.load()
    assert len(remaining) == 1
    assert remaining[0]["id"] == keep_id


def test_sessions_store_delete_missing_id_returns_false(tmp_path):
    store = SessionsStore(str(tmp_path / "sessions.json"))
    assert store.delete("does-not-exist") is False


def test_sessions_store_get_by_id(tmp_path):
    store = SessionsStore(str(tmp_path / "sessions.json"))
    session_id = store.append({"category": "Work"})
    assert store.get(session_id)["category"] == "Work"
    assert store.get("does-not-exist") is None


def test_sessions_store_append_many_single_write(tmp_path):
    path = tmp_path / "sessions.json"
    store = SessionsStore(str(path))
    ids = store.append_many([{"category": "Work"}, {"category": "Study"}])
    assert len(ids) == 2
    assert len(set(ids)) == 2  # unique ids
    loaded = store.load()
    assert len(loaded) == 2
    assert loaded[0]["id"] == ids[0]


def test_daily_report_store_roundtrip(tmp_path):
    store = DailyReportStore(str(tmp_path / "report.csv"))
    rows, fieldnames = store.load(categories=["Nothing", "Work"])
    assert rows == {}
    assert fieldnames == ["date", "Nothing", "Work"]

    rows["2026-08-06"] = {"date": "2026-08-06", "Nothing": "01:00:00", "Work": "02:00:00"}
    store.save(rows, fieldnames)

    fresh_store = DailyReportStore(str(tmp_path / "report.csv"))
    loaded_rows, loaded_fields = fresh_store.load(categories=["Nothing", "Work"])
    assert loaded_rows["2026-08-06"]["Work"] == "02:00:00"
    assert loaded_fields == ["date", "Nothing", "Work"]


def test_daily_report_store_preserves_unknown_columns(tmp_path):
    path = tmp_path / "report.csv"
    path.write_text("date,Nothing,OldCategory\n2026-08-01,00:00:00,01:00:00\n", encoding="utf-8")
    store = DailyReportStore(str(path))
    rows, fieldnames = store.load(categories=["Nothing"])
    assert "OldCategory" in fieldnames
    assert rows["2026-08-01"]["OldCategory"] == "01:00:00"
