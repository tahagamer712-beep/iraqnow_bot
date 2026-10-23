# -*- coding: utf-8 -*-
"""
discovery.py — اكتشاف مصادر RSS جديدة وتقييمها (مرحلة 6، 2026-10-22)

يفحص صفحات رئيسية لمواقع إخبارية (قائمة بذور) بحثًا عن وسوم RSS
(autodiscovery)، ثم يقيّم كل خلاصة مرشحة: قابلية الوصول، عدد العناصر،
نسبة التواريخ القابلة للقراءة، حداثة أحدث عنصر، ونسبة الصلة بالعراق.
النتائج تُخزّن كمرشحين بانتظار اعتماد الأدمن — لا يُفعَّل أي مصدر
تلقائيًا. الخلاصات المعتمدة تُكتب في dynamic_rss.json وتندمج بمسار
الجلب للعربية فورًا (prefetcher + _get_feeds_for_user).
"""
import hashlib
import io
import json
import os
import re
import time
from urllib.parse import urljoin, urlparse

_DIR = os.path.dirname(os.path.abspath(__file__))
CANDIDATES_PATH = os.path.join(_DIR, "discovery_candidates.json")
DYNAMIC_RSS_PATH = os.path.join(_DIR, "dynamic_rss.json")

SEED_SITES = [
    "https://www.ina.iq",
    "https://shafaq.com",
    "https://baghdadtoday.news",
    "https://www.almaalomah.me",
    "https://ninanews.com",
    "https://www.rudaw.net",
    "https://www.alsumaria.tv",
    "https://www.kurdistan24.net",
    "https://nrttv.com",
    "https://www.alforatnews.iq",
    "https://www.ikhnews.com",
    "https://www.basnews.com",
    "https://www.nrttv.com",
    "https://www.alhadath.net",
    "https://www.alarabiya.net",
]

_LINK_TAG_RE = re.compile(
    r'<link[^>]+type=["\']application/(?:rss|atom)\+xml["\'][^>]*>', re.I)
_HREF_RE = re.compile(r'href=["\']([^"\']+)["\']', re.I)


def _fetch(url, timeout=6, max_bytes=500_000):
    import requests
    r = requests.get(url, timeout=timeout, headers={
        "User-Agent": "Mozilla/5.0 (compatible; IraqNowBot discovery)"})
    if r.status_code != 200:
        return None
    return r.content[:max_bytes]


def find_feed_links(homepage_url, html_bytes):
    if html_bytes is None:
        return []
    try:
        html = html_bytes.decode("utf-8", "replace")
    except Exception:
        return []
    out = []
    for tag in _LINK_TAG_RE.findall(html):
        m = _HREF_RE.search(tag)
        if m:
            out.append(urljoin(homepage_url, m.group(1)))
    return out[:3]


def evaluate_feed(feed_url):
    """يقيّم خلاصة: يعيد dict إحصاءات + درجة، أو None عند تعذّر الجلب/التحليل."""
    import feedparser
    try:
        raw = _fetch(feed_url, timeout=8, max_bytes=900_000)
        if raw is None:
            return None
        parsed = feedparser.parse(raw)
    except Exception:
        return None
    entries = parsed.entries or []
    if not entries:
        return {"feed_url": feed_url, "entries": 0, "dated_ratio": 0.0,
                "newest_age_h": None, "iraq_ratio": 0.0, "score": 0,
                "sample_titles": [], "error": "no entries"}
    import datetime as _dt
    try:
        import iraq_policy as _ip
    except Exception:
        _ip = None
    now = _dt.datetime.now(_dt.timezone.utc).replace(tzinfo=None)
    dated = 0
    newest = None
    iraq_hits = 0
    titles = []
    for e in entries[:30]:
        t = (e.get("title") or "").strip()
        if t:
            titles.append(t)
            if _ip and _ip.classify_news(t)[0] in ("iraq", "regional"):
                iraq_hits += 1
        pp = e.get("published_parsed") or e.get("updated_parsed")
        if pp:
            dated += 1
            try:
                dtv = _dt.datetime(*pp[:6])
                if newest is None or dtv > newest:
                    newest = dtv
            except Exception:
                pass
    n = min(len(entries), 30)
    dated_ratio = dated / n if n else 0.0
    iraq_ratio = iraq_hits / len(titles) if titles else 0.0
    newest_age_h = ((now - newest).total_seconds() / 3600.0) if newest else None
    score = 0
    score += 30 * dated_ratio
    score += 40 * iraq_ratio
    if newest_age_h is not None:
        if newest_age_h <= 6:
            score += 30
        elif newest_age_h <= 24:
            score += 20
        elif newest_age_h <= 72:
            score += 8
    return {"feed_url": feed_url, "entries": len(entries),
            "dated_ratio": round(dated_ratio, 2),
            "newest_age_h": (round(newest_age_h, 1) if newest_age_h is not None else None),
            "iraq_ratio": round(iraq_ratio, 2), "score": int(round(score)),
            "sample_titles": titles[:3]}


def _load_json(path, default):
    try:
        with io.open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def _save_json(path, data):
    tmp = path + ".tmp"
    with io.open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
    os.replace(tmp, path)


def candidate_id(feed_url):
    return hashlib.md5(feed_url.encode("utf-8")).hexdigest()[:10]


def known_feed_urls():
    """كل روابط الخلاصات المعروفة: الثابتة (من ملفات البيانات نصيًا) + الديناميكية."""
    urls = set()
    try:
        src = io.open(os.path.join(_DIR, "data_rss.py"), encoding="utf-8", errors="replace").read()
        urls |= set(re.findall(r'https?://[^\s\'",\]]+', src))
    except Exception:
        pass
    for rec in load_dynamic_rss_records():
        urls.add(rec["url"])
    return urls


def discover(seed_sites=None, progress=None):
    """يشغّل الاكتشاف ويضيف مرشحين جددًا (status=pending). يعيد ملخصًا."""
    seeds = seed_sites or SEED_SITES
    known = known_feed_urls()
    data = _load_json(CANDIDATES_PATH, {"candidates": []})
    by_url = {c["feed_url"]: c for c in data["candidates"]}
    added = 0
    evaluated = 0
    for site in seeds:
        try:
            html = _fetch(site)
            links = find_feed_links(site, html)
        except Exception:
            links = []
        for feed_url in links:
            if feed_url in known and feed_url not in by_url:
                continue
            ev = evaluate_feed(feed_url)
            if ev is None:
                continue
            evaluated += 1
            rec = {"id": candidate_id(feed_url), "feed_url": feed_url,
                   "site": site, "discovered_at": int(time.time()),
                   "status": "pending", **ev}
            if feed_url in by_url:
                by_url[feed_url].update(rec)
            else:
                data["candidates"].append(rec)
                by_url[feed_url] = rec
                added += 1
            if progress:
                progress(rec)
    _save_json(CANDIDATES_PATH, data)
    return {"evaluated": evaluated, "added": added,
            "total_candidates": len(data["candidates"])}


def pending_candidates():
    data = _load_json(CANDIDATES_PATH, {"candidates": []})
    return [c for c in data["candidates"] if c.get("status") == "pending"]


def set_candidate_status(cid, status):
    data = _load_json(CANDIDATES_PATH, {"candidates": []})
    for c in data["candidates"]:
        if c.get("id") == cid:
            c["status"] = status
            _save_json(CANDIDATES_PATH, data)
            return c
    return None


def load_dynamic_rss_records():
    data = _load_json(DYNAMIC_RSS_PATH, {"feeds": []})
    return data.get("feeds", [])


_DYN_CACHE = {"mtime": 0, "urls": []}


def load_dynamic_rss():
    """روابط الخلاصات الديناميكية المعتمدة (بذاكرة مثبّطة على mtime)."""
    try:
        mt = os.path.getmtime(DYNAMIC_RSS_PATH)
    except Exception:
        return []
    if mt != _DYN_CACHE["mtime"]:
        _DYN_CACHE["mtime"] = mt
        _DYN_CACHE["urls"] = [r["url"] for r in load_dynamic_rss_records() if r.get("url")]
    return list(_DYN_CACHE["urls"])


def approve_candidate(cid, added_by=0):
    c = set_candidate_status(cid, "approved")
    if not c:
        return False
    data = _load_json(DYNAMIC_RSS_PATH, {"feeds": []})
    if c["feed_url"] not in [r["url"] for r in data["feeds"]]:
        data["feeds"].append({"url": c["feed_url"], "name": urlparse(c["feed_url"]).netloc,
                              "added_by": added_by, "added_at": int(time.time()),
                              "via": "discovery"})
        _save_json(DYNAMIC_RSS_PATH, data)
    global _DYN_CACHE
    _DYN_CACHE = {"mtime": 0, "urls": []}
    return True


def remove_dynamic_rss(url):
    data = _load_json(DYNAMIC_RSS_PATH, {"feeds": []})
    before = len(data["feeds"])
    data["feeds"] = [r for r in data["feeds"] if r["url"] != url]
    if len(data["feeds"]) != before:
        _save_json(DYNAMIC_RSS_PATH, data)
        global _DYN_CACHE
        _DYN_CACHE = {"mtime": 0, "urls": []}
        return True
    return False


def run_discovery_job():
    """وظيفة المجدول الأسبوعية: اكتشاف صامت — المرشحون ينتظرون اعتماد الأدمن."""
    try:
        return discover()
    except Exception:
        return {"evaluated": 0, "added": 0, "total_candidates": 0}
