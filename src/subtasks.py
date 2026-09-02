"""File-backed store for subtasks (data/subtasks.json). Keyed by category
name, same style as the other stores in storage.py: in-memory cache,
explicit flush to disk on every mutation."""
import os
import json
import uuid
from datetime import datetime


class SubtaskStore:
    def __init__(self, path):
        self.path = path
        self._cache = None

    def load(self):
        if self._cache is not None:
            return self._cache

        if not os.path.exists(self.path):
            self._cache = {}
            return self._cache

        try:
            with open(self.path, "r") as f:
                data = json.load(f)
                self._cache = data if isinstance(data, dict) else {}
        except Exception:
            self._cache = {}
        return self._cache

    def _flush(self):
        with open(self.path, "w") as f:
            json.dump(self._cache, f, indent=2)

    def list_for(self, category):
        subs = [s for s in self.load().get(category, []) if not s.get("archived")]
        return sorted(subs, key=lambda s: s.get("order", 0))

    def get(self, subtask_id):
        """Returns (category, subtask) or None. Looks across all categories
        since ids are globally unique."""
        for category, subs in self.load().items():
            for s in subs:
                if s.get("id") == subtask_id:
                    return category, s
        return None

    def create(self, category, name, planned_start=None, planned_end=None, color=None):
        data = self.load()
        subs = data.setdefault(category, [])
        order = max([s.get("order", 0) for s in subs], default=-1) + 1
        subtask = {
            "id": uuid.uuid4().hex,
            "name": name,
            "planned_start": planned_start,
            "planned_end": planned_end,
            "order": order,
            "color": color,
            "created": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "archived": False,
        }
        subs.append(subtask)
        self._flush()
        return subtask

    def update(self, subtask_id, **fields):
        found = self.get(subtask_id)
        if found is None:
            return None
        _, subtask = found
        subtask.update({k: v for k, v in fields.items() if v is not None})
        self._flush()
        return subtask

    def archive(self, subtask_id):
        found = self.get(subtask_id)
        if found is None:
            return False
        _, subtask = found
        subtask["archived"] = True
        self._flush()
        return True

    def reorder(self, category, ids):
        subs = self.load().get(category, [])
        order_of = {sid: i for i, sid in enumerate(ids)}
        for s in subs:
            if s.get("id") in order_of:
                s["order"] = order_of[s["id"]]
        self._flush()

    def rename_category(self, old, new):
        data = self.load()
        if old in data:
            data[new] = data.pop(old)
            self._flush()

    def drop_category(self, name):
        """Archive (never hard-delete) every subtask of a removed category
        so past sessions never end up with an orphaned subtask_id."""
        subs = self.load().get(name, [])
        changed = False
        for s in subs:
            if not s.get("archived"):
                s["archived"] = True
                changed = True
        if changed:
            self._flush()
