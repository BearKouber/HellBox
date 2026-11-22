"""训练模式的 8 个存档（2026-11-13 用户要求）：每格存一份「地图 + 出怪」设置和选的出怪方案名。

文件 mod/training_slots.json：长度 8 的列表，空格是 null；一格 = {"cfg": drill_spec 的设置, "preset": 出怪方案名或 ""}。
"""
import json
import os
from pathlib import Path

import paths

COUNT = 8
FILE = Path(paths.MOD) / "training_slots.json"


def load():
    try:
        data = json.loads(FILE.read_text(encoding="utf-8"))
    except (FileNotFoundError, ValueError):
        data = []
    if not isinstance(data, list):
        data = []
    out = [d if isinstance(d, dict) and isinstance(d.get("cfg"), dict) else None for d in data[:COUNT]]
    return out + [None] * (COUNT - len(out))


def save(slots):
    tmp = FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(list(slots)[:COUNT], ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp, FILE)
