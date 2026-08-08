"""Save/Load configuration: read and write scope settings as JSON.
Not part of controller.py because this is file I/O, not SCPI/hardware logic."""

import json


def save_config(path, settings):
    """settings คือ dict เช่น {'channel': 1, 'coupling': 'DC', 'vdiv': 1.0, ...}"""
    with open(path, "w", encoding="utf-8") as f:
        json.dump(settings, f, indent=2, ensure_ascii=False)


def load_config(path):
    """คืนค่า dict settings ที่เคยบันทึกไว้"""
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)