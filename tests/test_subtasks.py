import os

from subtasks import SubtaskStore


def make_store(tmp_path):
    return SubtaskStore(os.path.join(str(tmp_path), "subtasks.json"))


def test_create_persists_to_disk(tmp_path):
    store = make_store(tmp_path)
    subtask = store.create("Work", "Login module")
    assert subtask["name"] == "Login module"
    assert subtask["status"] == "todo"
    assert subtask["archived"] is False

    reloaded = make_store(tmp_path)
    assert reloaded.list_for("Work")[0]["id"] == subtask["id"]


def test_archive_hides_from_list_for_but_keeps_record(tmp_path):
    store = make_store(tmp_path)
    subtask = store.create("Work", "Login module")

    assert store.archive(subtask["id"]) is True
    assert store.list_for("Work") == []
    assert store.get(subtask["id"]) is not None  # still findable, just archived


def test_reorder_changes_list_for_order(tmp_path):
    store = make_store(tmp_path)
    a = store.create("Work", "A")
    b = store.create("Work", "B")

    store.reorder("Work", [b["id"], a["id"]])
    names = [s["name"] for s in store.list_for("Work")]
    assert names == ["B", "A"]


def test_get_unknown_id_returns_none(tmp_path):
    store = make_store(tmp_path)
    assert store.get("does-not-exist") is None


def test_rename_category_migrates_key_only(tmp_path):
    store = make_store(tmp_path)
    subtask = store.create("Work", "Login module")

    store.rename_category("Work", "Job")
    assert store.list_for("Work") == []
    found = store.list_for("Job")
    assert len(found) == 1
    assert found[0]["id"] == subtask["id"]  # id/name untouched, only the key moved


def test_drop_category_archives_instead_of_deleting(tmp_path):
    store = make_store(tmp_path)
    subtask = store.create("Work", "Login module")

    store.drop_category("Work")
    assert store.list_for("Work") == []
    found = store.get(subtask["id"])
    assert found is not None
    assert found[1]["archived"] is True
