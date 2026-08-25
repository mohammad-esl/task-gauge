"""Persistent audit trail for manual Gantt edits (create/update/delete).
Append-only — kept forever, unlike the in-memory undo stack in TimerApi."""
import os
import json
from datetime import datetime


class EditLog:
    def __init__(self, path):
        self.path = path

    def record(self, action, session_id, before, after):
        entry = {
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "action": action,  # "create" | "update" | "delete"
            "session_id": session_id,
            "before": before,
            "after": after,
        }

        entries = []
        if os.path.exists(self.path):
            try:
                with open(self.path, "r", encoding="utf-8") as f:
                    entries = json.load(f)
                    if not isinstance(entries, list):
                        entries = []
            except Exception:
                entries = []

        entries.append(entry)
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump(entries, f, indent=2)

        return entry
