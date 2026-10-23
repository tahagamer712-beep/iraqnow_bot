# -*- coding: utf-8 -*-
"""
tg_sources.py — مصادر أخبار تيليغرام الديناميكية (مرحلة 5، 2026-10-22)

تخزين JSON منفصل عن القوائم الثابتة في social_media.py. القراءة تتم عبر
المعاينة العامة t.me/s فقط (لا Telethon في هذا النظام) — لذلك المصدر
القابل للاستخدام يجب أن يكون قناة عامة باسم مستخدم. الإضافة بالمعرّف
الرقمي تُقبل فقط إذا أمكن تحويله إلى اسم مستخدم عام عبر Bot API.
"""
import io
import json
import os
import re
import time

_DIR = os.path.dirname(os.path.abspath(__file__))
STORE_PATH = os.path.join(_DIR, "tg_sources.json")
_SOCIAL_PATH = os.path.join(_DIR, "social_media.py")

_HANDLE_RE = re.compile(r"^[A-Za-z0-9_]{4,}$")
_ID_RE = re.compile(r"^-100\d{6,}$")
_LINK_RE = re.compile(r"^(?:https?://)?(?:t\.me|telegram\.me)/([A-Za-z0-9_]+)/?$")
_INVITE_RE = re.compile(r"^(?:https?://)?(?:t\.me|telegram\.me)/(\+|joinchat/)")


def load_store():
    try:
        with io.open(STORE_PATH, encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict) and isinstance(data.get("sources"), list):
            return data
    except Exception:
        pass
    return {"sources": []}


def save_store(data):
    tmp = STORE_PATH + ".tmp"
    with io.open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
    os.replace(tmp, STORE_PATH)


def static_handles():
    """معرّفات القنوات الثابتة من social_media.py (قراءة نصية آمنة بلا استيراد)."""
    try:
        src = io.open(_SOCIAL_PATH, encoding="utf-8", errors="replace").read()
        i = src.index("TELEGRAM_NEWS_CHANNELS = {")
        j = src.index("\n}", i)
        return {h.lower() for h in re.findall(r'"handle":\s*"([^"]+)"', src[i:j])}
    except Exception:
        return set()


def parse_input(text):
    """يحلّل إدخالًا (سطرًا أو عدة أسطر/فواصل) إلى عناصر مصنّفة:
    (kind, value) حيث kind: 'username' | 'id' | 'invite' | 'invalid'."""
    out = []
    if not text:
        return out
    parts = re.split(r"[\n,،;]+", text)
    for raw in parts:
        p = raw.strip()
        if not p:
            continue
        if _INVITE_RE.match(p):
            out.append(("invite", p))
            continue
        m = _LINK_RE.match(p)
        if m:
            h = m.group(1)
            out.append(("username", h) if _HANDLE_RE.match(h) else ("invalid", p))
            continue
        if _ID_RE.match(p):
            out.append(("id", p))
            continue
        h = p.lstrip("@").strip()
        if _HANDLE_RE.match(h):
            out.append(("username", h))
        else:
            out.append(("invalid", p))
    return out


def dynamic_channels():
    """قنوات ديناميكية مفعّلة بصيغة الكاشط: [{'handle':..., 'name':...}]."""
    data = load_store()
    return [{"handle": s["handle"], "name": s.get("name", s["handle"])}
            for s in data["sources"] if s.get("enabled", True) and s.get("handle")]


def find_source(handle):
    data = load_store()
    for s in data["sources"]:
        if s["handle"].lower() == handle.lower():
            return s
    return None


def add_source(handle, name, added_by, probe_info=""):
    data = load_store()
    if find_source(handle):
        return False
    data["sources"].append({
        "handle": handle, "name": name or handle, "added_by": added_by,
        "added_at": int(time.time()), "enabled": True,
        "trust": "normal", "probe": probe_info,
    })
    save_store(data)
    return True


def remove_source(handle):
    data = load_store()
    before = len(data["sources"])
    data["sources"] = [s for s in data["sources"] if s["handle"].lower() != handle.lower()]
    if len(data["sources"]) != before:
        save_store(data)
        return True
    return False


def set_enabled(handle, enabled):
    data = load_store()
    for s in data["sources"]:
        if s["handle"].lower() == handle.lower():
            s["enabled"] = bool(enabled)
            save_store(data)
            return True
    return False
