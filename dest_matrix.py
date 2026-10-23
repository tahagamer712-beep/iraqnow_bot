# -*- coding: utf-8 -*-
"""
dest_matrix.py — مصفوفة وجهات النشر (مرحلة 8، 2026-10-22)
أعلام إيقاف مستقلة لكل وجهة: قنوات / مميزون / رياضة (إشعارات ما قبل
المباريات). البث العام للمستخدمين يبقى بعلمه الأصلي broadcast_paused.
"""
import io
import json
import os

_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "matrix.json")
_DEFAULTS = {"channels": False, "premium": False, "sports": False}


def _load():
    try:
        with io.open(_PATH, encoding="utf-8") as f:
            d = json.load(f)
        out = dict(_DEFAULTS)
        for k in _DEFAULTS:
            if k in d:
                out[k] = bool(d[k])
        return out
    except Exception:
        return dict(_DEFAULTS)


def paused(dest):
    return _load().get(dest, False)


def set_paused(dest, val):
    if dest not in _DEFAULTS:
        return False
    d = _load()
    d[dest] = bool(val)
    tmp = _PATH + ".tmp"
    with io.open(tmp, "w", encoding="utf-8") as f:
        json.dump(d, f)
    os.replace(tmp, _PATH)
    return d[dest]
