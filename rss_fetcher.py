try:
    import freshness_policy as _fp
except Exception:
    _fp = None
# -*- coding: utf-8 -*-
"""
  rss_fetcher.py — feedparser + جلب RSS + timeout

  يُصدِّر دوال جلب RSS وتحليله.
  """

import sys as _sys_legacy
import os
# ─── استيراد كل المتغيرات العالمية من bot_legacy ───
from bot_legacy import *
import state as gl  # noqa: F401,F403
# FIX: _feed_is_healthy/_feed_record_ok/_feed_record_fail معرَّفة في rss_cache
# (محمَّل قبل rss_fetcher في features_news.py — الترتيب #7 vs #8)
from rss_cache import _feed_is_healthy, _feed_record_ok, _feed_record_fail  # noqa: F401

def _parse_feed(url, timeout=12):
    result = [None]
    def _fetch():
        try:
            result[0] = feedparser.parse(url)
        except Exception as _exc:
            _log_exc(_exc)
    t = threading.Thread(target=_fetch, daemon=True)
    t.start()
    t.join(timeout)
    return result[0]

def _parse_feed_with_backoff(url, timeout=12, max_retries=3):
    """FIX-10: Exponential backoff عند فشل جلب الـ feed."""
    import random as _rand
    for attempt in range(max_retries):
        result = _parse_feed(url, timeout)
        if result is not None and result.entries:
            return result
        if attempt < max_retries - 1:
            wait = min(2 ** attempt + _rand.uniform(0, 1), 60)
            time.sleep(wait)
    return result  # أعد آخر نتيجة حتى لو فارغة


# ======== جلب RSS متوازي مع وقت النشر الحقيقي ========
_RSS_FRESHNESS_MINUTES = 60   # نافذة الحداثة: 60 دقيقة — طلب المستخدم: لا بث لأي خبر عمره أكثر من ساعة (خاص وقنوات)
_RSS_FETCH_TIMEOUT     = 8     # ثواني لكل feed


# HEROKU FIX v4: ETag store for _fetch_one_feed
_rss_etag_store: dict = {}   # url -> {"etag": str, "last_modified": str, "entries": list}
# FIX (SSOT): كان يُنشئ Lock منفصلاً بنفس الاسم بدل استخدام قفل state.py
# الوحيد المُتشارَك مع bot_scheduled_jobs.py.
_rss_etag_lock  = gl._rss_etag_lock


import calendar as _calendar   # مُستورد مرة واحدة بدلاً من داخل كل loop

def _upscale_image_url(url):
    """يكبّر روابط الصور المعروفة بأنماط CDN قابلة للترقية — بدون طلب شبكة.

    BBC ichef مثلًا: /ws/240/ ← العرض بالبكسل، نرفعه إلى 1024.
    يعيد الرابط الأصلي إذا لم يطابق أي نمط معروف."""
    try:
        import re
        # BBC: https://ichef.bbci.co.uk/ace/ws/240/... أو /news/240/
        m = re.search(r"(ichef\.bbci\.co\.uk/[^/]+/(?:ws|news)/)240(/)", url)
        if m:
            return url[:m.start(1)] + m.group(1) + "1024" + url[m.end(2)-1:]
        # SkyNews Arabia: .../images/v1|v2/2021/04/19/1430886/95/53/1-....jpg
        # الرقمان بعد الـ ID هما العرض/الارتفاع — نرفعهما إلى 800/450
        # FIX 2026-10-22: النمط كان v2 فقط، وروابط v1 (95×53 فعلية) كانت تمرّ
        # كما هي فتظهر صور القناة بجودة مدمّرة كلما فشل جلب og:image.
        m = re.search(r"(images\.skynewsarabia\.com/images/v[12]/\d{4}/\d{2}/\d{2}/\d+/)\d+/\d+(/)", url)
        if m:
            return url[:m.end(1)] + "800/450" + url[m.start(2):]
    except Exception:
        pass
    return url


def _to_int(v):
    """يحول قيمة إلى int بأمان — يعيد 0 عند الفشل."""
    try:
        return int(str(v).strip())
    except Exception:
        return 0


def _extract_entry_image(item):
    """يستخرج أفضل صورة متاحة من عنصر RSS — يفضّل الأكبر حجمًا.

    يجمع كل المرشحين من media:content ثم enclosures/links ثم media:thumbnail،
    ويستخدم أبعاد width/height عند توفرها لاختيار الأكبر مساحة.
    يتجاهل بكسلات التتبع (1x1) والصور التافهة، ويخفض أولوية روابط
    المصغرات الصريحة (150x150 / thumb / ...).
    بدون أي طلب شبكة إضافي — البيانات موجودة مسبقًا ضمن الـ feed.
    لا تأثير على سرعة البث."""
    try:
        candidates = []  # (url, width, height, priority)
        # الأولوية: media:content=0 (عادة الحجم الكامل) ثم enclosures=1 ثم thumbnail=2
        for m in (getattr(item, "media_content", None) or []):
            if not isinstance(m, dict):
                continue
            url = m.get("url")
            if url:
                candidates.append((url, _to_int(m.get("width")),
                                   _to_int(m.get("height")), 0))
        for attr in ("links", "enclosures"):
            for enc in (getattr(item, attr, None) or []):
                if not isinstance(enc, dict):
                    continue
                etype = enc.get("type") or ""
                if etype.startswith("image/"):
                    url = enc.get("href") or enc.get("url")
                    if url:
                        candidates.append((url, 0, 0, 1))
        for m in (getattr(item, "media_thumbnail", None) or []):
            if not isinstance(m, dict):
                continue
            url = m.get("url")
            if url:
                candidates.append((url, _to_int(m.get("width")),
                                   _to_int(m.get("height")), 2))
        if not candidates:
            return None

        def _is_trash(url, w, h):
            if w and h and (w <= 2 or h <= 2):
                return True  # بكسل تتبع
            if w and h and w < 120 and h < 120:
                return True  # مصغرة تافهة
            return False

        pool = [c for c in candidates if not _is_trash(c[0], c[1], c[2])]
        if not pool:
            pool = candidates

        _THUMB_PATS = ("150x150", "thumb", "w=100", "w=150", "h=150",
                       "/small/", "_s.jpg", "_t.jpg", "thumbnail")

        def _score(c):
            url, w, h, pri = c
            area = (w or 0) * (h or 0)
            lu = url.lower()
            penalty = 1 if any(p in lu for p in _THUMB_PATS) else 0
            return (area, -pri, -penalty)

        pool.sort(key=_score, reverse=True)
        return _upscale_image_url(pool[0][0])
    except Exception:
        pass
    return None

# ======== تحسين شامل لجودة الصور: og:image كبديل عام لكل المصادر ========
_OG_IMG_CACHE = {}  # article_url -> (timestamp, og_image_url)
_OG_IMG_LOCK = None  # يُهيأ عند أول استخدام
_OG_IMG_TTL = 6 * 3600  # 6 ساعات

def _get_og_lock():
    global _OG_IMG_LOCK
    if _OG_IMG_LOCK is None:
        import threading as _th
        _OG_IMG_LOCK = _th.Lock()
    return _OG_IMG_LOCK


def _looks_tiny(img_url):
    """يكشف الصور المصغرة جدًا من أنماط الرابط — يعيد True إذا كانت تافهة."""
    if not img_url:
        return True
    try:
        import re as _re
        lu = img_url.lower()
        # نمط أبعاد في المسار: /95/53/ أو /240/135/
        m = _re.search(r"(?<!/\d{4})/(\d{1,3})/(\d{1,3})/", lu)
        if m and int(m.group(1)) < 300:
            return True
        # أنماط مصغرات صريحة
        for pat in ("150x150", "100x100", "/thumb/", "thumbnail", "?w=100",
                    "&w=100", "w=150", "_s.jpg", "_t.jpg", "/small/"):
            if pat in lu:
                return True
    except Exception:
        pass
    return False


def _fetch_og_image(article_url):
    """يجلب og:image من صفحة المقال — مع كاش ومهلة قصيرة. آمن تمامًا."""
    if not article_url or not article_url.startswith("http"):
        return None
    import time as _t
    now = _t.time()
    lock = _get_og_lock()
    with lock:
        hit = _OG_IMG_CACHE.get(article_url)
        if hit and (now - hit[0]) < _OG_IMG_TTL:
            return hit[1]
    og = None
    try:
        import urllib.request as _ur, re as _re
        req = _ur.Request(article_url, headers={"User-Agent": "Mozilla/5.0"})
        with _ur.urlopen(req, timeout=6) as resp:
            # نقرأ أول 200KB فقط — الـ og:image في الـ head عادة
            html = resp.read(200 * 1024).decode("utf-8", errors="ignore")
        m = _re.search(
            r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)',
            html, _re.IGNORECASE)
        if not m:
            m = _re.search(
                r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']og:image["\']',
                html, _re.IGNORECASE)
        if m:
            og = m.group(1).strip()
            # روابط نسبية → مطلقة
            if og.startswith("//"):
                og = "https:" + og
            elif og.startswith("/"):
                from urllib.parse import urlparse as _up
                pu = _up(article_url)
                og = f"{pu.scheme}://{pu.netloc}{og}"
    except Exception:
        og = None
    with lock:
        _OG_IMG_CACHE[article_url] = (now, og)
        # تنظيف الكاش من القديم
        if len(_OG_IMG_CACHE) > 500:
            old = [k for k, v in _OG_IMG_CACHE.items() if (now - v[0]) > _OG_IMG_TTL]
            for k in old:
                _OG_IMG_CACHE.pop(k, None)
    return og


def _resolve_broadcast_image(item_img, article_url):
    """الحل الشامل: يعيد أفضل صورة للبث.

    - صورة RSS جيدة (غير مصغرة) → تُستخدم مباشرة بدون أي طلب إضافي.
    - صورة مصغرة أو مفقودة → يجرب og:image من صفحة المقال.
    - فشل كل شيء → يعيد الأصلية (والبث يستخدم الشعار الافتراضي).
    لا يرمي استثناءً أبدًا."""
    try:
        # FIX 2026-10-22: ترقية رابط صورة الـ RSS نفسه أولًا (أنماط CDN المعروفة)
        # قبل فحص «مصغّرة» — صورة تأتي من مسار لا يمرّ بـ _extract_entry_image
        # كانت تصل هنا بخامها المصغّر وتُرسَل كما هي عند فشل og:image.
        if item_img:
            item_img = _upscale_image_url(item_img)
        if item_img and not _looks_tiny(item_img):
            return item_img
        if article_url:
            og = _fetch_og_image(article_url)
            if og:
                og = _upscale_image_url(og)
                if not _looks_tiny(og):
                    return og
    except Exception:
        pass
    return item_img


def _fetch_one_feed(feed_url):
    """
    يجلب feed واحد ويعيد قائمة entries مرتبة حسب وقت النشر.
    كل entry: dict بـ link, title, summary, published_dt, feed_url
    HEROKU FIX v4: Uses ETag/Last-Modified to avoid re-fetching unchanged feeds.
    """
    # FIX 2026-10-22 (log-monitor): روابط ملوثة بلواحق عرضية
    # (مثل "https://t.me/x   العربية") كانت تُسقط
    # "URL can't contain control characters" من داخل feedparser —
    # نأخذ أول رمز مفصول بمسافة ونرفض أي رابط
    # ما زال يحوي مسافات/محارف تحكم قبل أي طلب شبكة.
    try:
        feed_url = str(feed_url or "").strip().split()[0]
    except Exception:
        return []
    if not feed_url or any(ord(c) < 32 or c.isspace() for c in feed_url):
        _logger.warning("⚠️ _fetch_one_feed: رابط feed غير صالح — تخطّاً")
        return []
    # Track health
    if _FF.get("feed_health", True) and not _feed_is_healthy(feed_url):
        return []   # feed is auto-disabled due to repeated failures
    try:
        # Try HTTP GET with ETag/Last-Modified headers first
        entries_from_http = None
        if _FF.get("rss_etag", True):
            try:
                import requests as _req_etag
                with _rss_etag_lock:
                    cached_meta = _rss_etag_store.get(feed_url, {})
                headers = {"User-Agent": "IraqNowBot/1.0 +https://t.me/Iraqnowbot"}
                if cached_meta.get("etag"):
                    headers["If-None-Match"] = cached_meta["etag"]
                if cached_meta.get("last_modified"):
                    headers["If-Modified-Since"] = cached_meta["last_modified"]
                resp = _req_etag.get(feed_url, headers=headers,
                                     timeout=_RSS_FETCH_TIMEOUT, stream=False)
                if resp.status_code == 304:  # Not Modified
                    _feed_record_ok(feed_url)
                    with _rss_etag_lock:
                        return _rss_etag_store.get(feed_url, {}).get("entries", [])
                if resp.status_code == 200:
                    import io as _io_etag
                    parsed_http = feedparser.parse(
                        _io_etag.BytesIO(resp.content))
                    new_etag = resp.headers.get("ETag", "")
                    new_lm   = resp.headers.get("Last-Modified", "")
                    entries_from_http = (parsed_http, new_etag, new_lm)
            except Exception:
                entries_from_http = None  # fallback to feedparser direct
        if entries_from_http:
            parsed, new_etag, new_lm = entries_from_http
        else:
            parsed = _parse_feed(feed_url, timeout=_RSS_FETCH_TIMEOUT)
            new_etag, new_lm = "", ""
        if not parsed or not parsed.entries:
            _feed_record_fail(feed_url)
            return []
        entries_out = []
        for item in parsed.entries[:40]:
            link  = getattr(item, 'link',  None)
            title = getattr(item, 'title', '').strip()
            if not link or not title:
                continue
            summ  = getattr(item, 'summary', '') or getattr(item, 'description', '')
            # استخراج وقت النشر الفعلي
            # ── فصل أوقات الخبر (مرحلة الحداثة 2026-10-22): نشر أصلي / آخر تحديث / وقت الجلب ──
            def _struct_to_dt(_s):
                if not _s:
                    return None
                try:
                    return datetime.datetime.utcfromtimestamp(_calendar.timegm(_s))
                except Exception:
                    return None
            _pub_only_dt = _struct_to_dt(getattr(item, 'published_parsed', None))
            _upd_dt = _struct_to_dt(getattr(item, 'updated_parsed', None))
            pub_dt = _pub_only_dt or _upd_dt
            _date_source = 'published' if _pub_only_dt else ('updated' if _upd_dt else 'none')
            entries_out.append({
                "link":         link,
                "title":        title,
                "summary":      summ,
                "published_dt": pub_dt, "pub_only_dt": _pub_only_dt, "updated_dt": _upd_dt, "date_source": _date_source, "fetched_at": datetime.datetime.utcnow(),   # datetime UTC أو None
                "feed_url":     feed_url,
                "image":        _extract_entry_image(item),  # جاهزة من الـ feed — بدون طلب شبكة إضافي
            })
        # رتّب من الأحدث للأقدم
        entries_out.sort(
            key=lambda x: x["published_dt"] or datetime.datetime(2000, 1, 1),
            reverse=True
        )
        # Save ETag metadata for next request
        if _FF.get("rss_etag", True) and (new_etag or new_lm):
            with _rss_etag_lock:
                _rss_etag_store[feed_url] = {
                    "etag": new_etag, "last_modified": new_lm,
                    "entries": entries_out
                }
        _feed_record_ok(feed_url)
        return entries_out
    except Exception as _exc_feed:
        _logger.warning("⚠️ _fetch_one_feed فشل: %s — %s: %s",
                        feed_url[:80], type(_exc_feed).__name__, _exc_feed)
        _feed_record_fail(feed_url)
        return []


def _parallel_fetch_feeds(feed_urls, max_workers=8):
    """
    يجلب قائمة feeds بالتوازي ويدمج النتائج مرتبةً بوقت النشر.
    """
    all_entries = []
    workers = min(max_workers, len(feed_urls) or 1, 4)  # HEROKU: max 4
    try:
        with ThreadPoolExecutor(max_workers=workers) as ex:
            futures = {ex.submit(_fetch_one_feed, url): url for url in feed_urls}
            for future in as_completed(futures):  # بدون timeout — كل feed له timeout خاص
                try:
                    all_entries.extend(future.result())
                except Exception as _exc:
                    _log_exc(_exc)
    except (RuntimeError, OSError):
        # خيوط النظام مستنزفة — نجلب بشكل متسلسل كبديل
        for url in feed_urls[:5]:
            try:
                all_entries.extend(_fetch_one_feed(url))
            except Exception as _exc:
                _log_exc(_exc)
    # رتّب الكل من الأحدث للأقدم
    all_entries.sort(
        key=lambda x: x["published_dt"] or datetime.datetime(2000, 1, 1),
        reverse=True
    )
    return all_entries


def _is_fresh(pub_dt, window_minutes=_RSS_FRESHNESS_MINUTES):
    """هل الخبر منشور خلال النافذة؟ — سياسة الحداثة (2026-10-22):
    التاريخ المجهول لم يعُد يُقبل (كان يُقبل ضمنيًا — أصل مشكلة «الخبر القديم»)."""
    if _fp is not None:
        return _fp.classify(pub_dt, window_minutes=window_minutes) == "fresh"
    if pub_dt is None:
        return False
    try:
        if pub_dt.tzinfo is not None:
            pub_naive = pub_dt.astimezone(datetime.timezone.utc).replace(tzinfo=None)
        else:
            pub_naive = pub_dt
        age = (datetime.datetime.utcnow() - pub_naive).total_seconds() / 60
        return -60 <= age <= window_minutes
    except Exception:
        return False

_PUB_TIME_I18N = {
    "العربية 🇮🇶": ("منذ لحظات", "منذ {} دقيقة", "منذ {} ساعة"),
    "English 🇬🇧":  ("just now",    "{} min ago",    "{} hr ago"),
    "Русский 🇷🇺":  ("только что",  "{} мин назад",  "{} ч назад"),
    "فارسی 🇮🇷":    ("لحظاتی پیش", "{} دقیقه پیش", "{} ساعت پیش"),
    "हिन्दी 🇮🇳":   ("अभी",        "{} मिनट पहले",  "{} घंटे पहले"),
    "Türkçe 🇹🇷":   ("az önce",    "{} dk önce",    "{} sa önce"),
    "Deutsch 🇩🇪":  ("gerade eben", "vor {} Min",    "vor {} Std"),
    "Español 🇲🇽":  ("hace un momento", "hace {} min", "hace {} h"),
    "Português 🇧🇷":("há pouco",   "há {} min",     "há {} h"),
    "Italiano 🇮🇹": ("or ora",     "{} min fa",     "{} ore fa"),
    "Українська 🇺🇦":("щойно",    "{} хв тому",    "{} год тому"),
    "اردو 🇵🇰":     ("ابھی",       "{} منٹ پہلے",   "{} گھنٹے پہلے"),
    "Français 🇫🇷": ("à l'instant", "il y a {} min", "il y a {} h"),
}

def _get_feeds_for_user(lang, country):
    """يدمج مصادر الدولة المحددة + مصادر اللغة معاً (الدولة أولاً)"""
    lang_feeds    = list(RSS.get(lang, []))
    # خلاصات ديناميكية معتمدة من الاكتشاف (مرحلة 6 — 2026-10-22) — للعربية
    if lang == "العربية 🇮🇶":
        try:
            import discovery as _disc
            for _du in _disc.load_dynamic_rss():
                if _du not in lang_feeds:
                    lang_feeds.append(_du)
        except Exception:
            pass
    flag          = _get_country_flag(country)
    country_feeds = COUNTRY_RSS.get(flag, [])
    if not country_feeds:
        return lang_feeds
    # دمج: مصادر الدولة أولاً ثم بقية مصادر اللغة التي ليست في قائمة الدولة
    country_set = set(country_feeds)
    extra = [f for f in lang_feeds if f not in country_set]
    return country_feeds + extra

# تحميل الـ feeds مع الدمج الذكي: الأفضلية للـ DEFAULT_RSS لكن مع الحفاظ على أي إضافات يدوية
_loaded_rss = load_json(RSS_FILE, {})
RSS = {}
for lang, feeds in DEFAULT_RSS.items():
    RSS[lang] = DEFAULT_RSS[lang]  # دائماً خذ المصادر الجديدة
for lang, feeds in _loaded_rss.items():
    if lang not in RSS:
        RSS[lang] = feeds  # أضف أي لغة أضافها الأدمن يدوياً

def _track_source_speed(source_name: str, pub_dt):
    """يسجّل توقيت نشر المصدر لقياس سرعته"""
    if pub_dt:
        _source_speed_log[source_name].append(pub_dt.timestamp())
        if len(_source_speed_log[source_name]) > 100:
            _source_speed_log[source_name] = _source_speed_log[source_name][-100:]

def _get_source_rankings() -> list:
    """يحسب ترتيب المصادر حسب السرعة والكمية"""
    now = time.time()
    rankings = []
    for source, timestamps in _source_speed_log.items():
        recent = [t for t in timestamps if now - t < 24 * 3600]
        if not recent:
            continue
        avg_gap = (max(recent) - min(recent)) / max(len(recent) - 1, 1) if len(recent) > 1 else 9999
        rankings.append({
            "source": source,
            "count_24h": len(recent),
            "avg_gap_min": round(avg_gap / 60, 1),
            "score": len(recent) * 100 / max(avg_gap / 60, 1),
        })
    return sorted(rankings, key=lambda x: x["score"], reverse=True)

# ═══════════════════════════════════════════════════════════════════
# 9. سكرابنق المصادر المظلمة (الرسمية)
# ═══════════════════════════════════════════════════════════════════
def get_source_name_from_url(feed_url):
    """استخراج اسم المصدر من رابط الـ RSS أو رابط تلغرام"""
    try:
        # روابط تلغرام: t.me/channelname أو t.me/channelname/123
        if "t.me/" in feed_url:
            # استخراج الهاندل بشكل موثوق
            clean_url = feed_url.replace("https://", "").replace("http://", "")
            parts = clean_url.split("/")
            # parts[0]="t.me", parts[1]=handle, parts[2]=message_id (اختياري)
            handle = parts[1] if len(parts) > 1 else parts[0].split("t.me/")[-1]
            handle = handle.split("?")[0].strip()  # حذف query params إن وجدت
            # بحث في قاموس القنوات المعروفة (TELEGRAM_NEWS_CHANNELS)
            if handle in _TG_CHANNEL_NAMES:
                return _TG_CHANNEL_NAMES[handle]
            # بحث في SOURCE_NAMES بشكل غير حساس لحالة الأحرف
            handle_lower = handle.lower()
            for key, name in SOURCE_NAMES.items():
                if key.startswith("t.me/") and key.split("t.me/")[-1].lower() == handle_lower:
                    return name
            # إعادة الهاندل كاسم نظيف (بدون رابط)
            return f"@{handle}"
        import urllib.parse as _up
        host = _up.urlparse(feed_url).netloc.lower()
        for prefix in ("www.", "feeds.", "rss.", "feed."):
            if host.startswith(prefix):
                host = host[len(prefix):]
        for key, name in SOURCE_NAMES.items():
            if key in host:
                return name
        parts = host.split(".")
        if len(parts) >= 2:
            return parts[-2].replace("-", " ").capitalize()
        return host
    except Exception:
        return ""

def get_source_name_from_feed(feed_obj, feed_url=""):
    """استخراج اسم المصدر من بيانات الـ feed أو من الـ URL"""
    try:
        feed_meta = getattr(feed_obj, 'feed', None)
        if feed_meta:
            feed_title = getattr(feed_meta, 'title', '')
            if feed_title and len(feed_title.strip()) > 1:
                clean = feed_title.strip().split('|')[0].split(' - ')[0].strip()
                if clean and len(clean) < 60:
                    return clean
    except Exception as _exc:
        _log_exc(_exc)
    return get_source_name_from_url(feed_url)

# ======== دوال الأخبار ========
