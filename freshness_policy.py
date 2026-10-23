# -*- coding: utf-8 -*-
"""
freshness_policy.py — سياسة حداثة الأخبار (مرحلة 2 من تطوير «العراق الآن»، 2026-10-22)

المبادئ (المواصفة التنفيذية، القسم 4):
- published_at (وقت نشر المقال الأصلي) أساس حساب العمر — لا وقت الجلب ولا الاكتشاف.
- التاريخ المجهول ≠ طازج: يُصنّف «غير مؤكد زمنيًا»؛ لا نشر تلقائي ولا وسم «عاجل» ولا «منذ لحظات».
- التاريخ المستقبلي بما يتجاوز سماحية انحراف ساعات المصادر = خطأ مصدر.
- «عاجل» حالة تحريرية: تاريخ معروف وحديث + تدقيق متقاطع مع تاريخ المقال الأصلي عند توفره.

وحدة نقية لا تستورد شيئًا من البوت — قابلة للاختبار المستقل.
"""
import datetime
import json
import re

WINDOW_MINUTES = 60          # نافذة الحداثة (قرار المستخدم: لا بث لخبر أقدم من ساعة)
FUTURE_TOLERANCE_MIN = 60    # أقصى انحراف مستقبلي مقبول لساعات المصادر
ARTICLE_OLDER_TOLERANCE_MIN = 30  # فرق مقبول بين تاريخ RSS وتاريخ المقال قبل اعتبار RSS مضلِّلًا

_STATS = {
    "held_unknown": 0,
    "held_stale": 0,
    "held_future": 0,
    "dated_from_article": 0,
    "xcheck_corrected": 0,
    "xcheck_stale": 0,
    "tg_unknown": 0,
}

_LABELS = {
    "held_unknown": "مجهول التاريخ",
    "held_stale": "قديم",
    "held_future": "تاريخ مستقبلي خاطئ",
    "dated_from_article": "أُرّخ من المقال",
    "xcheck_corrected": "صُحّح بالتحقق المتقاطع",
    "xcheck_stale": "سقط بالتحقق المتقاطع",
    "tg_unknown": "تيليغرام بلا تاريخ",
}


def bump(key, n=1):
    if key in _STATS:
        _STATS[key] += n


def stats_snapshot():
    return dict(_STATS)


def stats_line_and_reset():
    parts = [(k, v) for k, v in _STATS.items() if v]
    for k in _STATS:
        _STATS[k] = 0
    if not parts:
        return None
    return "🧹 حداثة: " + "، ".join(f"{_LABELS.get(k, k)}: {v}" for k, v in parts)


def _as_naive_utc(dt):
    if dt is None:
        return None
    if dt.tzinfo is not None:
        return dt.astimezone(datetime.timezone.utc).replace(tzinfo=None)
    return dt


def _now_naive():
    return datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None)


def classify(pub_dt, now=None, window_minutes=WINDOW_MINUTES):
    """يصنّف عمر الخبر: 'fresh' | 'stale' | 'unknown' | 'future'.
    الانحراف المستقبلي ضمن السماحية يُعامل كطازج (ساعات مصادر منحرفة)."""
    if pub_dt is None:
        return "unknown"
    try:
        pub = _as_naive_utc(pub_dt)
        if pub is None:
            return "unknown"
        ref = _as_naive_utc(now) if now is not None else _now_naive()
        age_min = (ref - pub).total_seconds() / 60.0
        if age_min < -FUTURE_TOLERANCE_MIN:
            return "future"
        if age_min <= window_minutes:
            return "fresh"
        return "stale"
    except Exception:
        return "unknown"


def age_minutes(pub_dt, now=None):
    if pub_dt is None:
        return None
    try:
        pub = _as_naive_utc(pub_dt)
        ref = _as_naive_utc(now) if now is not None else _now_naive()
        return (ref - pub).total_seconds() / 60.0
    except Exception:
        return None


def is_breaking_time_ok(pub_dt, now=None, window_minutes=WINDOW_MINUTES):
    """الشرط الزمني لوسم «عاجل»: تاريخ معروف وحديث ضمن النافذة."""
    return classify(pub_dt, now=now, window_minutes=window_minutes) == "fresh"


# ───────────────── استخراج تاريخ المقال الأصلي من HTML ─────────────────

def _parse_iso(s):
    if not s or not isinstance(s, str):
        return None
    s = s.strip()
    try:
        s2 = s[:-1] + "+00:00" if s.endswith("Z") else s
        return _as_naive_utc(datetime.datetime.fromisoformat(s2))
    except Exception:
        pass
    for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.datetime.strptime(s[:19], fmt)
        except Exception:
            continue
    return None


def extract_article_date(html):
    """يستخرج datePublished من JSON-LD، ثم وسوم meta، ثم <time datetime>.
    يعيد datetime (naive UTC) أو None."""
    if not html:
        return None
    try:
        for block in re.findall(r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>', html, re.S | re.I):
            try:
                data = json.loads(block.strip())
            except Exception:
                continue
            stack = [data]
            while stack:
                node = stack.pop()
                if isinstance(node, dict):
                    for key in ("datePublished", "dateCreated"):
                        if node.get(key):
                            dt = _parse_iso(str(node[key]))
                            if dt:
                                return dt
                    for v in node.values():
                        if isinstance(v, (dict, list)):
                            stack.append(v)
                elif isinstance(node, list):
                    stack.extend(node)
    except Exception:
        pass
    for pat in (
        r'<meta[^>]+(?:property|name)=["\']article:published_time["\'][^>]+content=["\']([^"\']+)["\']',
        r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+(?:property|name)=["\']article:published_time["\']',
        r'<meta[^>]+itemprop=["\']datePublished["\'][^>]+content=["\']([^"\']+)["\']',
        r'<meta[^>]+(?:property|name)=["\']og:updated_time["\'][^>]+content=["\']([^"\']+)["\']',
    ):
        m = re.search(pat, html, re.I)
        if m:
            dt = _parse_iso(m.group(1))
            if dt:
                return dt
    m = re.search(r'<time[^>]+datetime=["\']([^"\']+)["\']', html, re.I)
    if m:
        return _parse_iso(m.group(1))
    return None


def cross_check(rss_dt, article_dt, window_minutes=WINDOW_MINUTES):
    """يقارن تاريخ RSS بتاريخ المقال الأصلي:
    'no_article_date' | 'consistent' | 'article_older' (يُصحَّح التاريخ ويُقبل)
    | 'article_stale' (المقال أقدم من النافذة — يُسقَط) | 'article_newer'."""
    if article_dt is None:
        return "no_article_date"
    if rss_dt is None:
        return "consistent"
    art = _as_naive_utc(article_dt)
    rss = _as_naive_utc(rss_dt)
    if art is None or rss is None:
        return "no_article_date"
    diff_min = (rss - art).total_seconds() / 60.0
    if diff_min > ARTICLE_OLDER_TOLERANCE_MIN:
        if classify(art, window_minutes=window_minutes) == "stale":
            return "article_stale"
        return "article_older"
    if diff_min < -ARTICLE_OLDER_TOLERANCE_MIN:
        return "article_newer"
    return "consistent"


# ─────────── جودة المصادر (مرحلة 4): عدّادات لكل خلاصة + حفظ مثبّط ───────────
import os as _os
import json as _json
import time as _time

FEED_STATS = {}
_FEED_FLUSH = {"ts": 0.0}
FEED_STATS_PATH = _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "source_quality.json")


def bump_feed(feed_url, kind):
    """kind: kept | held_unknown | held_stale | held_future | world_held"""
    if not feed_url:
        return
    rec = FEED_STATS.setdefault(feed_url, {"kept": 0, "held_unknown": 0, "held_stale": 0,
                                             "held_future": 0, "world_held": 0, "last_seen": 0})
    if kind in rec:
        rec[kind] += 1
    rec["last_seen"] = int(_time.time())


def feed_quality(feed_url):
    """تصنيف مصدر من عدّاداته المتراكمة (مواصفة 5.1)."""
    rec = FEED_STATS.get(feed_url)
    if not rec:
        return "unknown"
    total = rec["kept"] + rec["held_unknown"] + rec["held_stale"] + rec["held_future"]
    if total < 10:
        return "insufficient_data"
    stale_ratio = rec["held_stale"] / total
    unknown_ratio = rec["held_unknown"] / total
    if stale_ratio > 0.6:
        return "inaccurate_timing"
    if unknown_ratio > 0.6:
        return "no_dates"
    if rec["kept"] / total >= 0.5:
        return "useful"
    return "low_value"


def maybe_flush_feed_stats(min_interval=600):
    now = _time.time()
    if now - _FEED_FLUSH["ts"] < min_interval:
        return False
    _FEED_FLUSH["ts"] = now
    try:
        out = {u: {**rec, "quality": feed_quality(u)} for u, rec in FEED_STATS.items()}
        tmp = FEED_STATS_PATH + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            _json.dump(out, f, ensure_ascii=False, indent=1)
        _os.replace(tmp, FEED_STATS_PATH)
        return True
    except Exception:
        return False
