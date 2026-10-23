# -*- coding: utf-8 -*-
"""
  news_broadcaster.py — بث الأخبار للمستخدمين + watchdog

  يُصدِّر نظام البث للمستخدمين.
  """

import sys as _sys_legacy
import os
# ─── استيراد كل المتغيرات العالمية من bot_legacy ───
from bot_legacy import *
import state as gl  # noqa: F401,F403

# ═══ سياسة النشر المركزية (برومبت §3.4 + ملحق 2 §1.3 — 2026-10-22) ═══
# ملف JSON صغير بجانب ملفات البوت يقرأه البث كل دورة، فيستطيع الأدمن تعديل
# السياسة دون لمس الكود: arabic_only (العربية لغة النشر الوحيدة) وحدود كثافة
# النشر لكل قناة (فاصل أدنى، سقف ساعي/يومي، حد مستقل للعاجل).
_PUBLISH_POLICY_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "publish_policy.json")
_PACING_STATE_PATH   = os.path.join(os.path.dirname(os.path.abspath(__file__)), "publish_pacing.json")
_PUBLISH_POLICY_DEFAULTS = {
    "arabic_only": True,
    "pacing": {"min_gap_sec": 120, "max_per_hour": 6, "max_per_day": 60, "breaking_max_per_hour": 3},
}

def _load_publish_policy():
    try:
        import json as _jpp
        with open(_PUBLISH_POLICY_PATH, "r", encoding="utf-8") as _pf:
            _p = _jpp.load(_pf)
        if isinstance(_p, dict):
            _merged = dict(_PUBLISH_POLICY_DEFAULTS)
            _merged.update({k: v for k, v in _p.items() if k != "pacing"})
            _pc = dict(_PUBLISH_POLICY_DEFAULTS["pacing"])
            if isinstance(_p.get("pacing"), dict):
                _pc.update(_p["pacing"])
            _merged["pacing"] = _pc
            return _merged
    except Exception:
        pass
    return dict(_PUBLISH_POLICY_DEFAULTS)

def _load_pacing_state():
    try:
        import json as _jps
        with open(_PACING_STATE_PATH, "r", encoding="utf-8") as _f:
            _d = _jps.load(_f)
        return _d if isinstance(_d, dict) else {}
    except Exception:
        return {}

def _save_pacing_state(state):
    try:
        import json as _jps
        _tmp = _PACING_STATE_PATH + ".tmp"
        with open(_tmp, "w", encoding="utf-8") as _f:
            _jps.dump(state, _f, ensure_ascii=False)
        os.replace(_tmp, _PACING_STATE_PATH)
    except Exception:
        pass

def prefill_sent_news(feeds):
    """روابط آخر 3 أخبار من كل مصدر — من كاش RSS الجاهز فقط، بلا أي جلب شبكي.

    FIX 2026-10-22 (شكوى طه: /start يتأخر هواي): النسخة القديمة كانت تجلب
    10 خلاصات مباشرة داخل معالج /start نفسه (_parse_feed بمهلة 12 ثانية
    لكل خلاصة، تسلسليًا) فتأخّر الرد عشرات الثواني. الكاش الذي يبنيه
    _rss_prefetcher يحوي البيانات نفسها جاهزة — نقرأ منه ونرجع فورًا.
    كاش فارغ (إقلاع حديث) → نرجع {} بلا انتظار؛ المستخدم الجديد لا يخسر
    شيئًا لأن البث نفسه مفلتر بـ global_sent أصلًا.
    يرجع dict {link: timestamp} — متوافق مع _user_sent_active."""
    now_ts = time.time()
    links = {}
    try:
        cache = globals().get("_global_rss_cache") or {}
        lock = globals().get("_global_rss_cache_lock")
        items = []
        if lock is not None:
            with lock:
                items = [(u, list(v[0])) for u, v in cache.items() if v and v[0]]
        else:
            items = [(u, list(v[0])) for u, v in cache.items() if v and v[0]]
        by_feed = dict(items)
        for feed_url in (feeds or [])[:10]:
            for entry in by_feed.get(feed_url, [])[:3]:
                link = entry.get("link") if isinstance(entry, dict) else getattr(entry, "link", "")
                if link:
                    links[link] = now_ts
    except Exception as _exc:
        _log_exc(_exc)
    return links


# =====================================================================
# ==================== دوال نظام الرياضة ============================
# =====================================================================

def _live_events_broadcaster():
    """يتابع الأحداث الحية ويرسل تحديثات"""
    if not _live_events:
        return
    now = time.time()
    to_remove = []
    for uid_s, event_info in list(_live_events.items()):
        try:
            event = event_info["event"]
            started = event_info["started"]
            last_upd = event_info.get("last_update", 0)
            # انتهاء التتبع بعد 6 ساعات
            if now - started > 6 * 3600:
                to_remove.append(uid_s)
                try:
                    bot.send_message(int(uid_s),
                        f"⏹ انتهى التتبع المباشر لـ: *{event}*\n_(6 ساعات)_",
                        parse_mode="Markdown")
                except Exception as _exc:
                    _log_exc(_exc)
                continue
            # تحديث كل دقيقتين فقط
            if now - last_upd < 120:
                continue
            # جمع أخبار جديدة عن الحدث
            new_items = []
            for feed_url in list(RSS.get("العربية 🇮🇶", []))[:8]:
                try:
                    feed = _parse_feed(feed_url)
                    if not feed:
                        continue
                    for entry in feed.entries[:5]:
                        title = getattr(entry, 'title', '')
                        link = getattr(entry, 'link', '')
                        pub = _pub_dt_from_item(entry)
                        if not pub or now - pub.timestamp() > 3600:
                            continue
                        if any(w.lower() in title.lower() for w in event.split()):
                            new_items.append((title, link, pub))
                except Exception as _exc:
                    _log_exc(_exc)

            _live_events[uid_s]["last_update"] = now
            if new_items:
                prev_titles = set(event_info.get("updates", []))
                fresh = [(t, l, p) for t, l, p in new_items if t not in prev_titles]
                if fresh:
                    text = f"🔴 *تحديث مباشر — {event}*\n\n"
                    for title, link, pub in fresh[:3]:
                        time_str = pub.strftime('%H:%M') if pub else ''
                        text += f"⏱ `{time_str}` — [{title}]({link})\n\n"
                    try:
                        bot.send_message(int(uid_s), text[:4096],
                            parse_mode="Markdown", disable_web_page_preview=True)
                    except Exception as _exc:
                        _log_exc(_exc)
                    for t, _, _ in fresh:
                        event_info.setdefault("updates", []).append(t)
                        if len(event_info["updates"]) > 50:
                            event_info["updates"] = event_info["updates"][-50:]
        except Exception:
            continue
    for uid_s in to_remove:
        _live_events.pop(uid_s, None)

# ═══════════════════════════════════════════════════════════════════
# 7. مجتمع مشاركة الأخبار
# ═══════════════════════════════════════════════════════════════════
def broadcast_premium_instant_news():
    if bot_paused or broadcast_paused: return
    try:
        import dest_matrix as _dmp
        if _dmp.paused("premium"):
            return
    except Exception:
        pass
    try:
        rss_cache = {}
        for uid, info in _safe_users_snapshot():
            try:
                if not is_premium(uid):
                    continue
                if int(uid) in banned:
                    continue
                if not info.get("notifications", True):
                    continue
                lang    = info.get("lang", "العربية 🇮🇶")
                country = info.get("country", "")
                feeds   = _get_feeds_for_user(lang, country)
                sent = info.setdefault("sent_news", {})
                interests = info.get("interests", [])
                changed = False
                _premium_sent_count = 0
                for feed_url in feeds:
                    if feed_url not in rss_cache:
                        try:
                            rss_cache[feed_url] = _parse_feed(feed_url)
                        except Exception:
                            rss_cache[feed_url] = None
                    feed = rss_cache.get(feed_url)
                    if not feed:
                        continue
                    for item in feed.entries[:5]:
                        if not hasattr(item, 'link') or item.link in sent:
                            continue
                        # FIX: تطبيع الرابط + مفتاح العنوان — نفس منطق broadcast_news
                        # لمنع إرسال نفس الخبر مرتين لو broadcast_news أرسله بمسار آخر
                        _norm_link = _normalize_news_link(item.link)
                        _title_key = (getattr(item, 'title', '') or '').strip()[:70]
                        if _norm_link in sent or _title_key in sent:
                            continue
                        pub_dt = _pub_dt_from_item(item) if hasattr(item, 'published_parsed') else None
                        if not _is_fresh(pub_dt):
                            continue
                        if not news_matches_interests(item.title, interests):
                            continue
                        sent[item.link] = time.time()
                        sent[_norm_link] = time.time()
                        sent[_title_key] = time.time()
                        changed = True
                        link = getattr(item, 'link', '')
                        title = getattr(item, 'title', '')
                        item_sum = getattr(item, 'summary', '') or getattr(item, 'description', '')
                        markup = make_news_share_markup(link, title, lang, item_sum)
                        src_name = get_source_name_from_url(feed_url)
                        pub_time_str = _format_pub_time(_pub_dt_from_item(item) if hasattr(item, 'published_parsed') else None, lang=lang)
                        news_body = format_news_item(t(lang, "label_breaking"), title, lang, src_name, pub_time_str, summary=item_sum)
                        item_img = _resolve_broadcast_image(_extract_entry_image(item), getattr(item, 'link', '')) or DEFAULT_NEWS_IMAGE
                        _prem_delay = _premium_sent_count * _NEWS_SPACING_SECONDS
                        if item_img:
                            queue_send_delayed(uid, news_body[:1024], delay=_prem_delay, photo=item_img, parse_mode="Markdown", reply_markup=markup)
                        else:
                            queue_send_delayed(uid, news_body, delay=_prem_delay, parse_mode="Markdown", reply_markup=markup)
                        _premium_sent_count += 1
                if changed:
                    _db_save_user(uid, info)
            except Exception:
                continue
    except Exception as e:
        try:
            bot.send_message(ADMIN_ID, f"⚠️ خطأ في broadcast_premium_instant_news: {e}")
        except Exception as _exc:
            _log_exc(_exc)

def broadcast_news():
    """
    Wrapper يطلق _broadcast_news_impl بخيط منفصل ويقطعه عند تجاوز الوقت.
    هذا يحل مشكلة "الدورة السابقة لا تزال شغّالة" التي تعلّق البث للأبد
    عندما يعلّق استدعاء AI/HTTP/scrape بدون مهلة.
    """
    if bot_paused or broadcast_paused:
        _logger.info("⏸ broadcast_news: موقوف (bot_paused=%s, broadcast_paused=%s)", bot_paused, broadcast_paused)
        return

    # FIX: فحص القفل بشكل صحيح — منع تشغيل دورتين معاً
    if _broadcast_news_lock.is_set():
        elapsed = time.time() - _broadcast_lock_ts[0]
        if elapsed < 300:   # دورة أقل من 5 دقائق — تخطي
            _logger.info("🔒 broadcast_news: الدورة السابقة لا تزال شغّالة (%.0fث) — تخطي", elapsed)
            return
        _logger.error("⏱ broadcast_news: الدورة السابقة علقت %.0fث — التخلي عنها", elapsed)
        _broadcast_news_lock.clear()

    _broadcast_news_lock.set()
    _broadcast_lock_ts[0] = time.time()
    _broadcast_impl_thread[0] = None   # لا thread منفصل بعد الآن

    # FIX: استدعاء مباشر بدون Thread — يمنع تراكم الخيوط على Heroku
    try:
        _broadcast_news_impl()
    except Exception as _e:
        try:
            _record_broadcast_error(f"broadcast_news_impl: {_e}")
            _track_error("broadcast_news_impl", _e)
        except Exception:
            pass
        try:
            _logger.exception("💥 _broadcast_news_impl انفجرت: %s", _e)
        except Exception:
            pass
    finally:
        try:
            _broadcast_news_lock.clear()
        except Exception:
            pass
        # لا نقدر نقتل خيط Python بأمان، بس الـ wrapper التالي سيعرف أنها لا تزال شغّالة
        # ويتخطى. وبعد _BROADCAST_HARD_TIMEOUT+5 ثانية إضافية، سيتم التخلي عنها.

def _broadcast_news_impl():
    """
    البث التلقائي للأخبار — يستخدم تتبعاً عالمياً لكل لغة بدلاً من تتبع منفصل لكل مستخدم.
    هذا يضمن:
    1. عدم تكرار الخبر مع أي عدد من المستخدمين (حتى لو كانوا 100 ألف).
    2. استهلاك ذاكرة ثابت بغض النظر عن عدد المستخدمين (مجموعة واحدة لكل لغة).
    """
    # FIX 2026-10-22: استيراد محلي صريح — الاسمين معرّفان في news_formatter
    # لكن ترتيب تحميل الوحدات يجعلهما غير متوفرين عبر bot_legacy أحيانًا.
    from news_formatter import make_news_share_markup, _LABEL_LATEST

    # FIX: إذا تضخّم global_sent_news أكثر من اللازم، نظّفه لفك حصار الأخبار
    try:
        with _global_sent_lock:
            total_gsn = sum(len(v) for v in _global_sent_news.values())
            if total_gsn > 50000:
                _logger.warning("⚠️ global_sent_news ضخم (%d) — تشذيب ذكي بدل حذف كامل", total_gsn)
            # FIX 2026-10-22 (بأمر طه): تشذيب وقائي كل دورة — سقف 400 رابط لكل لغة (الأحدث)،
            # حتى لا يبتلع سجل المُرسلات كامل مخزون الأخبار فيتوقف البث وينطلق تنبيه الامتلاء.
            for _lang in list(_global_sent_news.keys()):
                _gset = _global_sent_news.get(_lang, {})
                if isinstance(_gset, dict) and len(_gset) > 400:
                    _sorted_gsn = sorted(_gset.items(), key=lambda kv: kv[1])
                    _global_sent_news[_lang] = dict(_sorted_gsn[-400:])
    except Exception:
        pass
    with _global_rss_cache_lock:
        _rss_cache_total = sum(len(v[0]) for v in _global_rss_cache.values())
        _rss_cache_feeds = len(_global_rss_cache)
    _logger.info(
        "🔄 broadcast_news بدأت دورة جديدة — مستخدمون: %d | كاش RSS: %d خبر من %d feed",
        len(users), _rss_cache_total, _rss_cache_feeds
    )
    if _rss_cache_total == 0:
        _logger.error(
            "❌ broadcast_news: كاش RSS فارغ تماماً! لا يمكن إرسال أي أخبار. "
            "سبب محتمل: _rss_prefetcher لم يعمل بعد أو كل الـ feeds فاشلة."
        )
    # إعادة تعيين مجموعة الأرشفة في كل دورة حتى لا تكبر إلى ما لا نهاية
    _broadcast_news_impl._archived_this_cycle = set()
    # alias للتوافق مع الكود القديم اللي يستخدم broadcast_news._archived_this_cycle
    broadcast_news._archived_this_cycle = _broadcast_news_impl._archived_this_cycle
    try:
        # الخطوة 1: جمع الأخبار الجديدة لكل لغة (مرة واحدة فقط بدلاً من لكل مستخدم)
        new_items_by_lang  = {}  # lang -> أخبار جديدة (مفلترة بـ global_sent) — للقنوات
        all_fresh_by_lang  = {}  # lang -> كل الأخبار الطازجة (بدون global_sent) — للمستخدمين
        total_collected = 0      # عداد إجمالي لمنع الفيضان
        all_langs = set()
        for uid, info in list(users.items()):
            if info.get("lang"):
                all_langs.add(info["lang"])
        # أضف لغات القنوات والمجموعات حتى تحصل على أخبارها في نفس الدورة
        for ch in channels_groups:
            if not ch.get('paused') and not ch.get('custom_sources'):
                cl = ch.get('lang', 'العربية 🇮🇶')
                if cl:
                    all_langs.add(cl)
        _pub_policy = _load_publish_policy()
        for lang in all_langs:
            # FIX 2026-10-22 (برومبت §3.4 — بأمر طه «كمّل باقي البنود»): العربية
            # هي لغة النشر الوحيدة. البولات الأجنبية لا تُعالج ولا تُنشر كقنوات
            # نشر مستقلة (كانت تولّد بثًا أجنبيًا كاملًا بلا صلة بالعراق).
            if _pub_policy.get("arabic_only", True) and lang != "العربية 🇮🇶":
                _logger.info("🌐 [بث] تخطي بول غير عربي — سياسة النشر بالعربية فقط: %s", lang[:15])
                continue
            if total_collected >= _MAX_NEWS_PER_CYCLE:
                break
            feeds = RSS.get(lang, [])

            # ══════════════════════════════════════════════════════════════
            # المرحلة A: جمع المرشحين (بدون أي قفل — لا يتجمد البث!)
            # ══════════════════════════════════════════════════════════════
            raw_candidates = []  # (link, title, feed_url, summary, pub_dt, image)

            # ─── RSS ─────────────────────────────────────────────────────
            # يقرأ من الكاش فقط — _rss_prefetcher يُحدّثه كل 90 ثانية.
            # لا جلب متزامن هنا → broadcast_news لا يتأخر أبداً.
            # استثناء: إذا لم يكن الـ feed في الكاش إطلاقاً (أول تشغيل)
            # نجلب أول 3 feeds فقط بشكل متوازٍ لتسريع الإقلاع الأول.
            now_ts = time.time()
            missing_feeds = []
            with _global_rss_cache_lock:
                for f in feeds:
                    if f not in _global_rss_cache:
                        missing_feeds.append(f)
            if missing_feeds:
                # جلب أول 5 feeds فقط (الإقلاع الأول) لتجنب التأخر
                first_batch = missing_feeds[:5]
                def _fetch_missing(url):
                    entries = _fetch_one_feed(url)
                    with _global_rss_cache_lock:
                        _global_rss_cache[url] = (entries, time.time())
                with ThreadPoolExecutor(max_workers=min(3, len(first_batch))) as ex:  # FIX: كان 5
                    futs = {ex.submit(_fetch_missing, url): url for url in first_batch}
                    for fut in as_completed(futs, timeout=15):
                        try: fut.result()
                        except Exception: pass
            all_entries = []
            with _global_rss_cache_lock:
                for feed_url in feeds:
                    cached = _global_rss_cache.get(feed_url)
                    if cached:
                        all_entries.extend(cached[0])
            all_entries.sort(
                key=lambda x: x.get("published_dt") or datetime.datetime(2000, 1, 1),
                reverse=True
            )
            _logger.info("🗂 [%s] %d خبر في كاش RSS من %d feed — يبدأ المعالجة",
                         lang[:15], len(all_entries), len(feeds))
            if not all_entries:
                _logger.warning("⚠️ [%s] كاش RSS فارغ! تأكد أن _rss_prefetcher يعمل والشبكة متاحة", lang[:15])
            for entry in all_entries:
                link  = entry["link"]
                title = entry["title"]
                if is_blacklisted(title):
                    continue
                # HEROKU FIX v4: skip near-duplicate titles from different sources
                if _is_duplicate_title(title):
                    continue
                pub_dt = entry.get("published_dt")
                # FIX 2026-10-22 (خنق التدفق — «ماكو اخبار بالبوت»): الخلاصات
                # الجسرية (تيليغرام وغيرها) كثيرًا ما تأتي بلا تاريخ نشر،
                # فتُحجب «مجهول التاريخ» رغم أن البوت اكتشفها للتو. fetched_at
                # (وقت بناء قائمة الخلاصة عند آخر تغيير بمحتواها — استجابة
                # 304 تحفظ القيم الأصلية) هو زمن اكتشاف البوت؛ يُستخدم تاريخًا
                # للمرشح عند غياب تاريخ النشر فتُقاس الحداثة بزمن الاكتشاف.
                # لا يُعرض أبدًا للمستخدم بوصفه وقت نشر الخبر.
                if pub_dt is None:
                    pub_dt = entry.get("fetched_at")
                # pub_dt موجود → نتحقق من الحداثة
                if pub_dt is not None and not _is_fresh(pub_dt):
                    continue
                raw_candidates.append((link, title, entry["feed_url"], entry.get("summary",""), pub_dt, entry.get("image")))

            # ─── Web Scraping — budget زمني 20 ثانية للكل ───────────────
            _scrape_budget = 20   # ثانية إجمالية للـ scraping بكل أنواعه
            _scrape_t0 = time.time()
            if _BS4_AVAILABLE:
                for src in SCRAPE_SOURCES.get(lang, []):
                    if time.time() - _scrape_t0 > _scrape_budget:
                        break
                    try:
                        scraped = _scrape_news_site(src['url'], src['base_url'], max_items=10)
                        for s_title, s_link in scraped:
                            if not is_blacklisted(s_title):
                                raw_candidates.append((s_link, s_title, src['url'], '', None, None))
                    except Exception as _exc:
                        _log_exc(_exc)

            # ─── قنوات تيليغرام — budget مشترك مع الـ scraping ──────────
            if _BS4_AVAILABLE and (time.time() - _scrape_t0) < _scrape_budget:
                _tg_all = list(TELEGRAM_NEWS_CHANNELS.get(lang, []))
                if lang == "العربية 🇮🇶":
                    try:
                        import tg_sources as _tgsx
                        _seen_h = {(c.get("handle") or "").lower() for c in _tg_all}
                        for _dc in _tgsx.dynamic_channels():
                            if (_dc.get("handle") or "").lower() not in _seen_h:
                                _tg_all.append(_dc)
                    except Exception:
                        pass
                for ch in _tg_all:
                    if time.time() - _scrape_t0 > _scrape_budget:
                        break
                    try:
                        tg_posts = _scrape_telegram_channel(ch['handle'], max_items=10)
                        for tg_item in tg_posts:
                            raw_text, tg_link = tg_item[0], tg_item[1]
                            tg_pub_dt = tg_item[2] if len(tg_item) > 2 else None
                            if not is_blacklisted(raw_text) and not _is_tg_spam(raw_text, tg_link):
                                uid_key = tg_link or raw_text[:80]
                                raw_candidates.append((uid_key, raw_text, f"t.me/{ch['handle']}", raw_text, tg_pub_dt, None))
                    except Exception as _exc:
                        _log_exc(_exc)

            # ─── NewsAPI (non-blocking) ───────────────────────────────────
            # FIX: كان requests.get() يعلق الـ thread الرئيسي للبث حتى 8 ثوانٍ
            # لكل لغة × عدد اللغات = قد يتجاوز 30 ثانية → يؤخّر كل دورة البث.
            # الحل: نُشغّل طلب NewsAPI في executor منفصل مع timeout قاسٍ (4ث)،
            # وإذا تأخّر نتجاهله ونكمل البث من كاش RSS فقط — بدون تعطيل.
            if NEWS_KEY:
                try:
                    lang_code = LANG_CODES.get(lang, "en")
                    from concurrent.futures import ThreadPoolExecutor as _NBEX, TimeoutError as _NBTO
                    def _fetch_newsapi_nb():
                        return requests.get(
                            f"https://newsapi.org/v2/top-headlines?language={lang_code}&pageSize=10&apiKey={NEWS_KEY}",
                            timeout=5
                        )
                    with _NBEX(max_workers=1) as _nbex:
                        _na_future = _nbex.submit(_fetch_newsapi_nb)
                        try:
                            na_r = _na_future.result(timeout=4)
                        except (_NBTO, Exception) as _nb_exc:
                            # تجاهل هادئ — البث يكمل من RSS فقط
                            _logger.debug("⚡ NewsAPI skipped (non-blocking timeout): %s", _nb_exc)
                            na_r = None
                    if na_r is not None and na_r.status_code == 200:
                        for art in na_r.json().get("articles", []):
                            na_link  = art.get("url", "")
                            na_title = art.get("title", "")
                            if na_link and na_title and not is_blacklisted(na_title):
                                na_pub_str = art.get("publishedAt", "")
                                try:
                                    na_pub_dt = datetime.datetime.strptime(na_pub_str, "%Y-%m-%dT%H:%M:%SZ") if na_pub_str else None
                                except Exception:
                                    na_pub_dt = None
                                if na_pub_dt and _is_fresh(na_pub_dt):
                                    src_name = art.get("source", {}).get("name", "NewsAPI")
                                    raw_candidates.append((na_link, na_title, src_name, art.get("description","") or "", na_pub_dt, art.get("urlToImage") or None))
                except Exception as _exc:
                    _log_exc(_exc)

            # ═══ بوابة الحداثة المركزية (مرحلة 2 — 2026-10-22) ═══
            # كل مرشح يحمل تاريخ نشر معروفًا وحديثًا أو يُحجب. المجهول يُؤرَّخ
            # من صفحة المقال عند الإمكان، والعاجل المحتمل يُدقَّق متقاطعًا مع
            # تاريخ المقال الأصلي لكشف إعادة تدوير الأخبار القديمة.
            try:
                import freshness_policy as _fp
                _kept = []
                # FIX 2026-10-22 (خنق التدفق — شكوى طه «ماكو اخبار بالبوت»): كانت
                # الميزانية 4 فقط بينما يصل ~18-40 مرشحًا بلا تاريخ كل دورة —
                # فتُحجب الغالبية «مجهول التاريخ» دون أن تُؤرَّخ أصلًا، وجفّ البث
                # كليًا مع بوابة «عراقي فقط». 20 محاولة مع كاش تواريخ 30 دقيقة
                # (المحاولات اللاحقة مجانية) تفتح الخنق دون إضعاف قاعدة الحداثة:
                # لا خبر يمرّ إلا بتاريخ حقيقي من صفحته أو خلاصته.
                _fetch_budget = [20]
                _xcache = getattr(broadcast_news, "_xcheck_cache", None)
                if _xcache is None:
                    _xcache = broadcast_news._xcheck_cache = {}
                def _article_date(_url):
                    if _fetch_budget[0] <= 0 or not _url or not str(_url).startswith("http"):
                        return None
                    _fetch_budget[0] -= 1
                    try:
                        _r = requests.get(_url, timeout=2.5, headers={"User-Agent": "Mozilla/5.0 IraqNowBot/2.0"})
                        if _r.status_code == 200 and _r.text:
                            return _fp.extract_article_date(_r.text[:300000])
                    except Exception:
                        return None
                    return None
                for (_l, _t, _s, _sm, _pdt, _img) in raw_candidates:
                    _v = _fp.classify(_pdt)
                    if _v == "stale":
                        _fp.bump("held_stale"); _fp.bump_feed(_s, "held_stale"); continue
                    if _v == "future":
                        _fp.bump("held_future"); _fp.bump_feed(_s, "held_future"); continue
                    if _v == "unknown":
                        _dk = _normalize_news_link(_l) if _l else _l
                        _dcache = getattr(broadcast_news, "_date_cache", None)
                        if _dcache is None:
                            _dcache = broadcast_news._date_cache = {}
                        _dc = _dcache.get(_dk)
                        if _dc and (time.time() - _dc[1] < 1800):
                            _adt = _dc[0]
                        else:
                            _adt = _article_date(_l)
                            _dcache[_dk] = (_adt, time.time())
                        if _adt is not None:
                            _fp.bump("dated_from_article")
                            if _fp.classify(_adt) == "fresh":
                                _kept.append((_l, _t, _s, _sm, _adt, _img))
                            else:
                                _fp.bump("held_stale")
                        else:
                            _fp.bump("held_unknown"); _fp.bump_feed(_s, "held_unknown")
                        continue
                    try:
                        _imp = _news_importance_score(_t)
                    except Exception:
                        _imp = 0
                    if _imp >= 2:
                        _ck = _normalize_news_link(_l) if _l else _l
                        _cached = _xcache.get(_ck)
                        if _cached and (time.time() - _cached[1] < 1800):
                            _adt = _cached[0]
                        else:
                            _adt = _article_date(_l)
                            _xcache[_ck] = (_adt, time.time())
                        _xc = _fp.cross_check(_pdt, _adt)
                        if _xc == "article_stale":
                            _fp.bump("xcheck_stale"); continue
                        if _xc == "article_older":
                            _fp.bump("xcheck_corrected")
                            _kept.append((_l, _t, _s, _sm, _adt, _img)); continue
                    _kept.append((_l, _t, _s, _sm, _pdt, _img))
                # ── سياسة العراق أولًا (مرحلة 3 — 2026-10-22): حجب العالمي الروتيني + فرز الأولويات ──
                try:
                    import iraq_policy as _ip
                    _pol = []
                    for (_l2, _t2, _s2, _sm2, _pdt2, _img2) in _kept:
                        _cls, _csc, _rsn = _ip.classify_news(_t2, _sm2)
                        try:
                            _imp2 = _news_importance_score(_t2)
                        except Exception:
                            _imp2 = 0
                        if _cls == "world_minor":
                            _ip.bump("world_minor_held"); continue
                        # حظر مطلق (أمر طه 2026-10-22): أخبار غزة لا تُنشر أبدًا
                        if _cls == "blocked_topic":
                            _ip.bump("gaza_blocked"); continue
                        # FIX 2026-10-22 (بأمر طه — «أغلب المنشور مو عراقي»): البول العربي
                        # عراقي فقط. الإقليمي والعالمي لا يُنشران تلقائيًا مهما بلغت
                        # أهميتهما؛ التصنيف «إقليمي» كان يمرّر أي خبر يذكر دولة جارة
                        # ولو بلا أي صلة بالعراق، فامتلأت القناة بأخبار العالم.
                        if lang == "العربية 🇮🇶" and _cls != "iraq":
                            _ip.bump("regional_held" if _cls == "regional" else "world_major_held")
                            continue
                        if not _ip.publishable(_cls, _imp2):
                            _ip.bump("world_major_held_lowimp"); continue
                        _pol.append((_ip.CLASS_RANK.get(_cls, 3), -(_pdt2.timestamp()) if _pdt2 else 0, (_l2, _t2, _s2, _sm2, _pdt2, _img2)))
                    _pol.sort(key=lambda _x: (_x[0], _x[1]))
                    _kept = [_x[2] for _x in _pol]
                    _pline = _ip.stats_line_and_reset()
                    if _pline:
                        _logger.info("🇮🇶 [%s] %s", lang[:15], _pline)
                except Exception as _ipexc:
                    _log_exc(_ipexc)
                for _kc in _kept:
                    _fp.bump_feed(_kc[2], "kept")
                _fp.maybe_flush_feed_stats()
                raw_candidates = _kept
                _sline = _fp.stats_line_and_reset()
                if _sline:
                    _logger.info("🧹 [%s] %s", lang[:15], _sline)
            except Exception as _fexc:
                _log_exc(_fexc)
            _logger.info("📋 [%s] %d مرشح خام بعد فلتر is_duplicate+freshness (من %d خبر في كاش)",
                         lang[:15], len(raw_candidates), len(all_entries))
            if not raw_candidates and all_entries:
                _logger.warning(
                    "⚠️ [%s] كل أخبار الكاش (%d) محجوبة بـ _is_duplicate_title أو انتهت صلاحيتها — "
                    "البوت ينتظر أخباراً جديدة. إذا استمر هذا أكثر من 30 دقيقة، نفّذ /clearcache",
                    lang[:15], len(all_entries)
                )
            # ══════════════════════════════════════════════════════════════
            # المرحلة B: بناء قائمتين منفصلتين
            # all_fresh: كل الأخبار الطازجة (للمستخدمين — مفلترة بـ user_sent شخصياً)
            # new_items: أخبار جديدة فعلاً (للقنوات — مفلترة بـ global_sent لمنع التكرار)
            # ══════════════════════════════════════════════════════════════
            # تنقية أساسية لـ all_fresh (إزالة usernames/hashtags من منشورات تيليغرام)
            import re as _re_b
            all_fresh_cleaned = []
            for (lnk, ttl, src, summ, pdt, img) in raw_candidates:
                try:
                    if src.startswith('t.me/'):
                        _t = _re_b.sub(r'@\S+|#\S+|https?://\S+', '', ttl).strip()
                        if _t and len(_t) >= 15:
                            all_fresh_cleaned.append((lnk, _t, src, summ, pdt, img))
                    else:
                        all_fresh_cleaned.append((lnk, ttl, src, summ, pdt, img))
                except Exception:
                    all_fresh_cleaned.append((lnk, ttl, src, summ, pdt, img))
            # تطبيق فلتر اللغة وإزالة التكرار على all_fresh
            _af = [item for item in all_fresh_cleaned if _title_in_lang(item[1], lang)]
            _af = _dedup_news_list(_af)
            # ── Semantic Dedup: حذف الأخبار المكررة معنوياً عبر مصادر مختلفة ──
            _af_sem = []
            for _item in _af:
                _ttl = _item[1] if len(_item) > 1 else ""
                if not _is_semantic_duplicate(_ttl, lang):
                    _af_sem.append(_item)
            all_fresh_by_lang[lang] = _af_sem

            # global_sent للقنوات فقط (يمنع إعادة إرسال نفس الخبر كل دورة)
            # نستخدم فقط الروابط النشطة (لم تنتهِ صلاحيتها بعد TTL = 4 ساعات)
            with _global_sent_lock:
                lang_dict = _global_sent_news.setdefault(lang, {})
                global_sent = _gsn_active_keys(lang_dict)
            # فلتر global_sent مع تطبيع الروابط لمنع التكرار بروابط متشابهة
            new_items = [
                cand for cand in raw_candidates
                if _normalize_news_link(cand[0]) not in global_sent and cand[0] not in global_sent
            ]
            total_collected += len(new_items)

            # ══════════════════════════════════════════════════════════════
            # المرحلة C: تنقية + AI (بدون أي قفل)
            # ══════════════════════════════════════════════════════════════
            # AI تنظيف قنوات تيليغرام — ميزانية زمنية (45ث) + سقف استدعاءات (15)
            # FIX: الميزانية تُفحص داخل الحلقة لمنع تعليق البث عند تراكم الأخبار
            _AI_MAX_CALLS_PER_CYCLE = 15
            _ai_calls_made = 0
            cleaned = []
            for (lnk, ttl, src, summ, pdt, img) in new_items:
                try:
                    _ai_budget_ok = (
                        (time.time() - _broadcast_lock_ts[0]) < 45
                        and _ai_calls_made < _AI_MAX_CALLS_PER_CYCLE
                    )
                    if src.startswith('t.me/') and _ai_budget_ok:
                        clean_ttl = _ai_clean_news(ttl, link=lnk)
                        _ai_calls_made += 1
                        if not clean_ttl or len(clean_ttl) < 15:
                            continue
                        cleaned.append((lnk, clean_ttl, src, summ, pdt, img))
                    elif src.startswith('t.me/'):
                        import re as _r2
                        _t = _r2.sub(r'@\S+|#\S+|https?://\S+', '', ttl).strip()
                        if _t and len(_t) >= 15:
                            cleaned.append((lnk, _t, src, summ, pdt, img))
                    else:
                        cleaned.append((lnk, ttl, src, summ, pdt, img))
                except Exception:
                    cleaned.append((lnk, ttl, src, summ, pdt, img))
            new_items = cleaned

            # فلتر اللغة
            new_items = [item for item in new_items if _title_in_lang(item[1], lang)]
            # إزالة التكرار الذكي
            _pre_dedup_links = {i[0] for i in new_items}
            new_items = _dedup_news_list(new_items)
            # FIX 2026-10-22 (دمج التغطيات — برومبت §1.5/§12.3): النسخ المسقطة
            # هنا هي القصة نفسها من مصادر أخرى = تأكيدات لا أخبار جديدة؛
            # تُسجَّل روابطها في global_sent بالمرحلة D حتى لا تعود في دورة
            # لاحقة بوصفها خبرًا «جديدًا» بصياغة مختلفة.
            _dup_variant_links = _pre_dedup_links - {i[0] for i in new_items}
            # AI تلخيص أخبار RSS (أول 5 فقط لمنع التجميد)
            if _AI_AVAILABLE and new_items:
                ai_items = []
                _ai_used = 0
                for (lnk, ttl, src, summ, pdt, img) in new_items:
                    try:
                        if not src.startswith('t.me/' ) and _ai_used < 2 and summ and len(summ) > 50:
                            clean = _ai_clean_news(ttl, body=summ[:600], link=lnk)
                            _ai_used += 1
                            # إذا أعاد AI قيمة None أو فارغة → استخدم العنوان الأصلي
                            if not clean:
                                clean = ttl
                        else:
                            clean = ttl
                        # تأكيد أخير: العنوان لا يكون None أبداً
                        if not clean:
                            continue
                        ai_items.append((lnk, clean, src, summ, pdt, img))
                    except Exception:
                        ai_items.append((lnk, ttl, src, summ, pdt, img))
                new_items = ai_items

            # ══════════════════════════════════════════════════════════════
            # المرحلة D: تسجيل الأخبار الجديدة فعلاً في global_sent (للإحصاء فقط)
            # ══════════════════════════════════════════════════════════════
            if new_items:
                with _global_sent_lock:
                    lang_dict = _global_sent_news.setdefault(lang, {})
                    now_ts = time.time()
                    # نُضيف الرابط مع الطابع الزمني — ينتهي تلقائياً بعد TTL
                    for (lnk, *_rest) in new_items:
                        norm = _normalize_news_link(lnk) or lnk
                        lang_dict[norm] = now_ts
                        if lnk != norm:
                            lang_dict[lnk] = now_ts
                    # روابط نسخ القصص المدموجة (تأكيدات من مصادر أخرى) تُحرق أيضًا
                    for _dl in _dup_variant_links:
                        _dn = _normalize_news_link(_dl) or _dl
                        lang_dict[_dn] = now_ts
                        if _dl != _dn:
                            lang_dict[_dl] = now_ts

            # FIX: حُذف الـ fallback الذي كان يمسح نصف global_sent ويُعيد إرسال أخبار مكررة للقنوات
            # الآن _GLOBAL_SENT_TTL=6h يتطابق مع نافذة الطزاجة → لا حاجة للـ fallback
            if not new_items and raw_candidates:
                _logger.info("📭 [%s] global_sent منع كل %d مرشح — انتظار انتهاء TTL أو أخبار جديدة", lang[:15], len(raw_candidates))

            new_items_by_lang[lang] = new_items
            # all_fresh_by_lang[lang] مُملوء بالفعل أعلاه بـ _af_sem (مع semantic dedup)
            # لا نُعيد كتابته هنا لأن ذلك يُلغي الـ semantic dedup
            if new_items:
                _logger.info("📥 [%s] %d خبر طازج جاهز للإرسال", lang[:15], len(new_items))
            else:
                _logger.info("📭 [%s] لا أخبار طازجة بعد كل الفلاتر", lang[:15])

        total_new = sum(len(v) for v in new_items_by_lang.values())
        _logger.info("📊 broadcast_news: إجمالي الأخبار الجديدة = %d عبر %d لغة", total_new, len(new_items_by_lang))

        # حفظ التتبع العالمي بعد جمع الأخبار
        _save_global_sent_news()
        # تسجيل الأخبار للملخص الأسبوعي
        for _lang, _items in new_items_by_lang.items():
            for _link, _title, _feed, _sum, _pdt, _img in _items:
                try:
                    _record_weekly_news(_title, _link, _lang)
                except Exception as _exc:
                    _log_exc(_exc)
        # فحص القصص المتابَعة وإرسال تنبيهات
        try:
            _check_followed_stories(new_items_by_lang)
        except Exception as _exc:
            _log_exc(_exc)
        # الخطوة 2: إرسال الأخبار الجديدة لكل مستخدم حسب لغته
        users_reached_this_cycle = 0
        news_sent_this_cycle = 0
        now = _now_sa()
        for uid, info in list(users.items()):
            try:
                if int(uid) in banned:
                    continue
                if not info.get("notifications", True):
                    continue
                # ── وضع الصمت الذكي (Sleep Mode) ──────────────────────────
                if _is_sleeping(int(uid)):
                    continue
                # فحص الإيقاف المؤقت للمستخدم
                paused_until = info.get("news_paused_until")
                if paused_until:
                    try:
                        if datetime.datetime.fromisoformat(paused_until) > now:
                            continue
                        else:
                            users[str(uid)].pop("news_paused_until", None)
                    except Exception as _exc:
                        _log_exc(_exc)
                lang = info.get("lang")
                if not lang:
                    # FIX: بدلاً من تخطي المستخدم، أعطه اللغة الافتراضية
                    lang = "العربية 🇮🇶"
                    users[str(uid)]["lang"] = lang
                    _logger.info("🌐 مستخدم %s بدون lang — ضُبطت لـ %s", uid, lang)
                # توحيد المصدر: المستخدمون والقنوات/المجموعات يستلمون نفس
                # قائمة الأخبار (new_items_by_lang) — لمنع الاختلاف بين الخاص والقناة
                # إذا كانت new_items_by_lang فارغة (تم استهلاكها بـ global_sent) نرجع لـ all_fresh
                # ── تطبيق الترتيب الشخصي (InsightX Personalization) ──────
                _user_pool = new_items_by_lang.get(lang, []) or all_fresh_by_lang.get(lang, [])
                items = _rank_news_by_interests(_user_pool, uid)
                if not items:
                    continue
                user_interests = info.get("interests", [])
                digest_mode   = info.get("digest_mode", False)
                # جدول مخصص: لا نرسل خارج الساعات المطلوبة (الأخبار العاجلة تُرسل دائماً)
                custom_sched  = info.get("custom_schedule", [])
                current_hour  = _now_sa().hour
                in_sched_window = (not custom_sched) or (current_hour in custom_sched)
                sent_to_user  = 0
                digest_lines  = []
                for link, title, feed_url, item_sum, pub_dt, item_img in items:
                    if sent_to_user >= MAX_NEWS_PER_USER_CYCLE:
                        break
                    # الجدول المخصص: تجاوز غير العاجلة خارج ساعات المستخدم
                    if not in_sched_window and _news_importance_score(title) < 2:
                        continue
                    # فلترة الاهتمامات (لكل المستخدمين)
                    if user_interests and not news_matches_interests(title, user_interests):
                        continue
                    # مستوى التنبيه
                    if not _passes_alert_level(title, uid):
                        continue
                    # فحص عدم إرسال هذا الخبر سابقاً لهذا المستخدم (مع TTL 24 ساعة)
                    _raw_sent = info.get("sent_news", {})
                    user_sent = _user_sent_active(_raw_sent)   # يُحوّل ويُنظف المنتهية
                    info["sent_news"] = user_sent              # تحديث فوري في الذاكرة
                    # تطبيع الرابط لمنع التكرار حتى لو تغيرت معاملات URL
                    link_key  = _normalize_news_link(link) if link else title[:80]
                    title_key = title.strip()[:70]  # لمنع إرسال نفس الخبر من مصدرين مختلفين
                    if link_key in user_sent or title_key in user_sent:
                        continue
                    # إضافة إيموجي المشاعر للعنوان
                    s_emoji = _sentiment_emoji(title)
                    display_title = f"{s_emoji} {title}" if s_emoji else title
                    src_name = get_source_name_from_url(feed_url)
                    # وقت النشر الفعلي من المصدر — بلغة المستخدم
                    pub_time_str = _format_pub_time(pub_dt, lang=lang)
                    if digest_mode:
                        # جمع الأخبار لإرسالها كرسالة واحدة
                        imp = _news_importance_score(title)
                        bullet = "🚨" if imp >= 2 else ("⚡" if imp == 1 else "•")
                        time_suffix = f" _{pub_time_str}_" if pub_time_str else ""
                        digest_lines.append(f"{bullet} [{display_title}]({link}){time_suffix}")
                    else:
                        # إعداد بدون تحليل: لا أزرار إذا فعّل المستخدم هذا الخيار
                        no_analysis = info.get("no_analysis_mode", False)
                        markup = None if no_analysis else make_news_share_markup(link, title, lang, item_sum)
                        # استخدام تسمية "عاجل" للأخبار المهمة — نفس جودة القنوات
                        imp_score = _news_importance_score(title)
                        _age_min = None
                        try:
                            if pub_dt:
                                _age_min = (datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None) - pub_dt).total_seconds() / 60.0
                        except Exception:
                            _age_min = None
                        # قاعدة العاجل (مواصفة 4.3 — 2026-10-22): أهمية ≥2 وعمر ≤10 دقائق معًا؛
                        # الأهمية وحدها لا تكفي بعد اليوم
                        if imp_score >= 2 and _age_min is not None and _age_min <= 10:
                            news_label = t(lang, "label_breaking") or "🚨 عاجل"
                        elif imp_score >= 1:
                            news_label = "⚡ " + _LABEL_LATEST.get(lang, "مهم")
                        else:
                            news_label = _LABEL_LATEST.get(lang, "آخر الأخبار")
                        news_body = format_news_item(news_label, display_title, lang, src_name, pub_time_str, summary=item_sum)
                        # FIX: تباعد بين الأخبار المتعددة لنفس المستخدم بدورة واحدة (لا تشعر كسبام)
                        _send_delay = sent_to_user * _NEWS_SPACING_SECONDS
                        # لا صورة من المصدر → شعار الوكالة الافتراضي بدل نص بلا صورة إطلاقاً
                        _img_to_send = _resolve_broadcast_image(item_img, link) or DEFAULT_NEWS_IMAGE
                        if _img_to_send:
                            # صورة الخبر جاهزة من الـ RSS نفسه — نرسلها مباشرة بدل زر "صورة المقال"
                            queue_send_delayed(uid, news_body[:1024], delay=_send_delay, photo=_img_to_send,
                                parse_mode="Markdown", reply_markup=markup)
                        else:
                            queue_send_delayed(uid, news_body, delay=_send_delay,
                                parse_mode="Markdown", reply_markup=markup, disable_web_page_preview=True)
                    sent_to_user += 1
                    news_sent_this_cycle += 1
                    # ─── أرشفة الخبر (مرة واحدة فقط لكل رابط) ─────────────
                    _arc_key = link_key
                    if _arc_key not in broadcast_news._archived_this_cycle:
                        broadcast_news._archived_this_cycle.add(_arc_key)
                        _AI_EXECUTOR.submit(_archive_news_item, title, link, feed_url[:60], lang, item_sum or "")
                        # ── InsightX Auto-Intelligence Hooks ──────────────
                        try:
                            _register_broadcast_title(title, lang)      # Semantic dedup
                            _update_narrative(title, src_name)          # Narrative Arc
                            _update_predictive(title)                   # Predictive Signals
                            _check_entity_alerts(title, src_name)       # Entity Tracker
                            _alert_disinfo_if_needed(title, lang)       # Disinfo Alert
                            # ── 🚨 رادار الأزمات (Crisis Radar) ───────────
                            _crisis_result = _track_crisis(title, src_name or "")
                            if _crisis_result and _crisis_result.get("crisis_alert"):
                                _cr = _crisis_result
                                # أرسل لكل مستخدمين الـ breaking news بلغتهم الخاصة
                                for _cu, _cd in list(users.items()):
                                    try:
                                        _cu_id   = int(_cu)
                                        if not (_cd.get("breaking") and not _cd.get("muted")):
                                            continue
                                        _cu_lang = _cd.get("lang", "العربية 🇮🇶")
                                        _i18n    = _NEW_FEAT_I18N
                                        _hdr  = _i18n["crisis_alert_header"].get(_cu_lang, _i18n["crisis_alert_header"]["العربية 🇮🇶"])
                                        _sev_lbl = _i18n["crisis_severity_label"].get(_cu_lang, _i18n["crisis_severity_label"]["العربية 🇮🇶"])
                                        _rel_lbl = _i18n["crisis_related_news"].get(_cu_lang, _i18n["crisis_related_news"]["العربية 🇮🇶"])
                                        _hr_lbl  = _i18n["crisis_in_hour"].get(_cu_lang, _i18n["crisis_in_hour"]["العربية 🇮🇶"])
                                        _lst_lbl = _i18n["crisis_last_news"].get(_cu_lang, _i18n["crisis_last_news"]["العربية 🇮🇶"])
                                        _ftr_lbl = _i18n["crisis_footer"].get(_cu_lang, _i18n["crisis_footer"]["العربية 🇮🇶"])
                                        _bar     = '█' * _cr['severity'] + '░' * (5 - _cr['severity'])
                                        _crisis_msg = (
                                            f"{_hdr}\n"
                                            f"━━━━━━━━━━━━━━━━━━\n"
                                            f"🔴 *{escape_md(_cr['topic'])}*\n"
                                            f"{_sev_lbl}: `{_bar}` {_cr['severity']}/5\n"
                                            f"{_rel_lbl}: *{_cr['count']}* {_hr_lbl}\n"
                                            f"{_lst_lbl}: _{escape_md(title[:120])}_\n"
                                            f"━━━━━━━━━━━━━━━━━━\n"
                                            f"{_ftr_lbl}"
                                        )
                                        queue_send(_cu_id, _crisis_msg, parse_mode="Markdown", disable_web_page_preview=True)
                                    except Exception as _exc:
                                        _log_exc(_exc)
                        except Exception as _exc:
                            _log_exc(_exc)
                    # تسجيل الخبر كمُرسَل لهذا المستخدم مع timestamp للـ TTL
                    _now_ts = time.time()
                    user_sent[link_key]  = _now_ts
                    user_sent[title_key] = _now_ts
                    # تنظيف المنتهية الصلاحية إذا تضخّم الـ dict
                    if len(user_sent) > 3000:
                        user_sent = _user_sent_active(user_sent)
                        info["sent_news"] = user_sent
                    # تحديث إحصائيات المستخدم الشخصية
                    users[str(uid)]["total_news_received"] = users[str(uid)].get("total_news_received", 0) + 1
                # تحديث streak ويوم النشاط
                if sent_to_user > 0:
                    today_str = str(datetime.date.today())
                    last_day = users[str(uid)].get("last_active_day", "")
                    if last_day != today_str:
                        yesterday = str(datetime.date.today() - datetime.timedelta(days=1))
                        if last_day == yesterday:
                            users[str(uid)]["reading_streak"] = users[str(uid)].get("reading_streak", 0) + 1
                        else:
                            users[str(uid)]["reading_streak"] = 1
                        users[str(uid)]["last_active_day"] = today_str
                        users[str(uid)]["last_active"] = today_str
                # إرسال رسالة الدايجست الواحدة
                if digest_mode and digest_lines:
                    now_str = _now_sa().strftime("%H:%M")
                    digest_msg = f"📰 *نشرة أخبار — {now_str}*\n━━━━━━━━━━━━━━\n" + "\n".join(digest_lines)
                    if len(digest_msg) > 4096:
                        digest_msg = digest_msg[:4080] + "\n…"
                    queue_send(uid, digest_msg, parse_mode="Markdown", disable_web_page_preview=True)
                if sent_to_user > 0:
                    users_reached_this_cycle += 1
            except Exception as _per_user_exc:
                # FIX: كان هذا الاستثناء يُبلَع بصمت تماماً بلا أي تسجيل —
                # ما جعل تشخيص "لا أخبار تصل" شبه مستحيل. الآن يُسجَّل صراحة.
                _log_exc(_per_user_exc, f"broadcast_news/user={uid}")
                continue
        if news_sent_this_cycle == 0:
            _pool_debug = {lang: len(new_items_by_lang.get(lang,[])) for lang in list(new_items_by_lang.keys())[:5]}
            _fresh_debug = {lang: len(all_fresh_by_lang.get(lang,[])) for lang in list(all_fresh_by_lang.keys())[:5]}
            _logger.warning(
                "⚠️ broadcast_news: لم يُرسَل أي خبر في هذه الدورة\n"
                "  new_items_by_lang: %s\n"
                "  all_fresh_by_lang: %s\n"
                "  إجمالي المستخدمين الفعّالين: %d",
                _pool_debug, _fresh_debug,
                sum(1 for i in users.values() if i.get("notifications", True) and i.get("lang"))
            )
        _record_broadcast_stat(users_reached=users_reached_this_cycle, news_count=news_sent_this_cycle)
        _log_broadcast_cycle(news_sent_this_cycle)    # ── InsightX Health Monitor ──
        _logger.info(
            "✅ broadcast_news انتهت: أرسلت %d خبر لـ %d مستخدم",
            news_sent_this_cycle, users_reached_this_cycle
        )
        # ─── حفظ user_sent فوراً بعد كل دورة أُرسِل فيها أخبار ────────
        # BUGFIX: _needs_save كان يُعيَّن لكن لا يُستخدم — الآن نحفظ فعلاً
        if news_sent_this_cycle > 0:
            broadcast_news._needs_save = True
            _fn_save = globals().get('_save_users_soon') or globals().get('save_users')
            if _fn_save:
                try:
                    _fn_save()
                except Exception as _sve:
                    _log_exc(_sve)

        # ─── تشخيص ذكي: إذا لم يُرسَل أي خبر منذ 5 دورات — أخبر الأدمن ─────
        if not hasattr(broadcast_news, '_empty_cycles'):
            broadcast_news._empty_cycles = 0
        if news_sent_this_cycle == 0:
            broadcast_news._empty_cycles += 1
            # أرسل تحذيراً كل 20 دورة فارغة (≈10 دقائق) — يتكرر كل 10 دقائق لا مرة واحدة فقط
            if broadcast_news._empty_cycles > 0 and broadcast_news._empty_cycles % 20 == 0:
                total_items_found = sum(len(v) for v in new_items_by_lang.values())
                active_u = sum(1 for i in users.values() if i.get("notifications", True) and i.get("lang"))
                user_sent_total = sum(len(i.get("sent_news", {})) for i in users.values())
                reasons = []
                if not users:
                    reasons.append("❌ لا مستخدمين مسجّلين — أرسل /start لتفعيل الاشتراك")
                elif active_u == 0:
                    reasons.append("❌ كل المستخدمين لا يملكون لغة محددة")
                if total_items_found == 0:
                    reasons.append("❌ لم تجد دورة البث أي أخبار جديدة (كلها في global_sent)")
                if user_sent_total > 400 * max(1, len(users)):
                    reasons.append(f"⚠️ ذاكرة المستخدمين ممتلئة ({user_sent_total} رابط) — الحل: /clearcache")
                if bot_paused:
                    reasons.append("❌ البوت متوقف كلياً (bot_paused=True)")
                if broadcast_paused:
                    reasons.append("❌ البث متوقف (broadcast_paused=True) — اضغط 📡 تشغيل البث في /admin")
                diag = "\n".join(reasons) if reasons else "⚠️ سبب غير معروف — جرّب /debugnews"
                silent_min = broadcast_news._empty_cycles  # كل دورة = ~30-60 ثانية
                # FIX 2026-10-22 (بأمر طه — التنبيه كان يتكرر والبث يعمل): الدورات
                # الفارغة نتيجة طبيعية لبوابات الحداثة و«عراقي فقط»، وليست عطلًا.
                # تُسجَّل في اللوغ فقط، ولا تُرسَل رسالة للأدمن كل ~20 دورة.
                _logger.warning(
                    "⚠️ broadcast_news: %d دورة فارغة متتالية | مستخدمون: %d (فعّال: %d) | أخبار الدورة: %d | %s",
                    silent_min, len(users), active_u, total_items_found, diag)
        else:
            broadcast_news._empty_cycles = 0

        # ══════════════════════════════════════════════════════════════════
        # الخطوة 3: بث القنوات والمجموعات — نفس الأخبار، نفس الوقت تماماً!
        # (القنوات ذات المصادر المخصصة تُعالَج بواسطة broadcast_to_channels)
        # ══════════════════════════════════════════════════════════════════
        ch_changed = False
        ch_total_sent = 0
        _pacing = _load_pacing_state()
        _pace_cfg = _pub_policy.get("pacing") or {}
        for ch in list(channels_groups):
            try:
                if ch.get('paused'):
                    continue
                # القنوات بمصادر مخصصة → broadcast_to_channels تتكفل بها
                if ch.get('custom_sources'):
                    continue
                chat_id = ch["id"]
                lang    = ch.get('lang', 'العربية 🇮🇶')
                # FIX: القنوات تعتمد فقط على new_items (المُفلترة بـ global_sent) —
                # لا نستخدم all_fresh هنا لأنه يحتوي أخبار قديمة سبق بثّها للقنوات
                # سابقاً (global_sent منعها من new_items لهذا السبب بالضبط)، واستخدامه
                # هنا كـ fallback كان يُعيد نشر أخبار قديمة بالقناة بلا داعٍ.
                items = new_items_by_lang.get(lang, [])
                if not items:
                    continue
                # ── كثافة النشر (ملحق 2 §1.3): حالة هذه القناة وحدودها ──
                _pst = _pacing.setdefault(str(chat_id), {"last_ts": 0.0, "hour": [], "day": "", "day_count": 0, "breaking_hour": []})
                _now_p = time.time()
                _pst["hour"] = [t for t in _pst.get("hour", []) if _now_p - t < 3600]
                _pst["breaking_hour"] = [t for t in _pst.get("breaking_hour", []) if _now_p - t < 3600]
                _today_p = time.strftime("%Y-%m-%d")
                if _pst.get("day") != _today_p:
                    _pst["day"] = _today_p
                    _pst["day_count"] = 0
                _gap_ok = (_now_p - float(_pst.get("last_ts", 0.0))) >= float(_pace_cfg.get("min_gap_sec", 120))
                _pace_deferred = []
                ch_sent = set(ch.get('sent_news', []))
                sent_this_ch = 0
                for (lnk, ttl, src, summ, pdt, img) in items:
                    if sent_this_ch >= MAX_NEWS_PER_BROADCAST:
                        break
                    # تطبيع الرابط لمنع التكرار بسبب معاملات URL المتغيرة
                    norm_lnk  = _normalize_news_link(lnk)
                    title_key = ttl.strip()[:70]
                    # FIX 2026-10-22: بصمة عنوان مُطبَّعة (بلا ترقيم/تشكيل/مسافات
                    # زائدة) — نفس الخبر من مصدرين بصياغة مختلفة قليلًا كان يفلت
                    # من title_key الخام فيُنشر مرتين (حصل فعليًا اليوم).
                    title_fp  = "fp:" + _normalize_title_for_dedup(ttl)
                    if norm_lnk in ch_sent or title_key in ch_sent or title_fp in ch_sent:
                        continue
                    # ── قرار كثافة النشر لهذا العنصر (العاجل له حدّ مستقل) ──
                    _is_brk = False
                    try:
                        _imp_p = _news_importance_score(ttl)
                        _age_p = None
                        if pdt:
                            _age_p = (datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None) - pdt).total_seconds() / 60.0
                        _is_brk = (_imp_p >= 2 and _age_p is not None and _age_p <= 10)
                    except Exception:
                        _is_brk = False
                    if _is_brk:
                        if len(_pst["breaking_hour"]) >= int(_pace_cfg.get("breaking_max_per_hour", 3)):
                            _pace_deferred.append(lnk); continue
                    else:
                        if (not _gap_ok) or len(_pst["hour"]) >= int(_pace_cfg.get("max_per_hour", 6)) or int(_pst.get("day_count", 0)) >= int(_pace_cfg.get("max_per_day", 60)):
                            _pace_deferred.append(lnk); continue
                    try:
                        src_name     = get_source_name_from_url(src)
                        pub_time_str = _format_pub_time(pdt, lang=lang)
                        s_emoji      = _sentiment_emoji(ttl)
                        display_ttl  = f"{s_emoji} {ttl}" if s_emoji else ttl
                        latest_label = _LABEL_LATEST.get(lang, "آخر الأخبار")
                        news_text    = format_news_item(
                            latest_label, display_ttl, lang,
                            src_name, pub_time_str, summary=summ
                        )
                        # FIX: طلب المستخدم — نفس أزرار الخاص بالضبط لكل القنوات
                        # والمجموعات (لا فرق بعد الآن)، بدل زر مصدر فقط للقنوات
                        ch_markup = make_news_share_markup(lnk, ttl, lang, summ)
                        # FIX: تباعد بين الأخبار المتعددة لنفس القناة بدورة واحدة (لا تشعر كسبام)
                        _ch_send_delay = sent_this_ch * _NEWS_SPACING_SECONDS
                        # لا صورة من المصدر → شعار الوكالة الافتراضي بدل نص بلا صورة إطلاقاً
                        _ch_img = _resolve_broadcast_image(img, lnk) or DEFAULT_NEWS_IMAGE
                        if _ch_img:
                            queue_send_delayed(chat_id, news_text[:1024], delay=_ch_send_delay, photo=_ch_img,
                                parse_mode="Markdown", reply_markup=ch_markup)
                        else:
                            queue_send_delayed(chat_id, news_text, delay=_ch_send_delay,
                                parse_mode="Markdown", reply_markup=ch_markup, disable_web_page_preview=True)
                        # تسجيل الرابط المُطبَّع والعنوان لمنع إعادة الإرسال
                        ch_sent.add(norm_lnk)
                        ch_sent.add(title_key)
                        ch_sent.add(title_fp)
                        if lnk != norm_lnk:
                            ch_sent.add(lnk)  # الرابط الأصلي أيضاً للتوافق
                        # محاسبة كثافة النشر: كل إرسال فعلي يستهلك من حدود القناة
                        if _is_brk:
                            _pst["breaking_hour"].append(_now_p + _ch_send_delay)
                        _pst["hour"].append(_now_p + _ch_send_delay)
                        _pst["day_count"] = int(_pst.get("day_count", 0)) + 1
                        _pst["last_ts"] = _now_p + _ch_send_delay
                        sent_this_ch += 1
                        ch["news_sent_count"] = ch.get("news_sent_count", 0) + 1
                        time.sleep(0.05)
                    except Exception as send_e:
                        err_s = str(send_e).lower()
                        if any(x in err_s for x in ("kicked", "chat not found", "not a member", "forbidden")):
                            break
                        time.sleep(0.3)
                if sent_this_ch > 0:
                    ch['sent_news'] = list(ch_sent)[-3000:]
                    ch_changed = True
                    ch_total_sent += sent_this_ch
                    # FIX 2026-10-22: حفظ فوري بعد كل قناة — الحفظ بنهاية الدورة
                    # فقط كان يترك نافذة سباق: دورة متداخلة تقرأ السجل القديم
                    # فتُعيد إرسال نفس الأخبار إلى القناة.
                    try:
                        save_channels_groups()
                    except Exception as _sv_e:
                        _log_exc(_sv_e)
                if _pace_deferred:
                    # العناصر المؤجلة بالكثافة لم تُنشر في هذه القناة — تُفكّ من
                    # global_sent لتبقى مؤهلة للدورة التالية بدل أن تُحرق.
                    # (سجل ch_sent الخاص بكل قناة يمنع أي تكرار عند إعادة المحاولة)
                    try:
                        with _global_sent_lock:
                            _ld = _global_sent_news.setdefault(lang, {})
                            for _dl in _pace_deferred:
                                _ld.pop(_normalize_news_link(_dl) or _dl, None)
                                _ld.pop(_dl, None)
                        _save_global_sent_news()
                        _logger.info("⏳ [قنوات %s] أُجّل %d خبر بحدود كثافة النشر — يبقى مؤهلًا للدورة التالية", str(chat_id), len(_pace_deferred))
                    except Exception as _pd_e:
                        _log_exc(_pd_e)
            except Exception:
                continue
        if ch_changed:
            save_channels_groups()
        _save_pacing_state(_pacing)
        # FIX 2026-10-22: إحصائية البث تشمل إرسالات القنوات — كانت تُسجَّل قبل
        # خطوة القنوات وبعدد المستخدمين فقط، فتظنّ أنظمة المراقبة أن البث
        # متوقف بينما القناة تنشر فعليًا، وتطلق دورات إجبارية وتنبيهات كاذبة.
        if ch_total_sent > 0:
            try:
                _record_broadcast_stat(users_reached=0, news_count=ch_total_sent)
            except Exception as _st_e:
                _log_exc(_st_e)

    except Exception as e:
        _record_broadcast_error(f"broadcast_news: {e}")
        _track_error("broadcast_news", e)
        try:
            bot.send_message(ADMIN_ID, f"⚠️ خطأ في broadcast_news: {e}")
        except Exception as _exc:
            _log_exc(_exc)
    finally:
        _broadcast_news_lock.clear()   # تحرير القفل دائماً حتى عند الاستثناء

def _cluster_stories(items, threshold=0.55):
    """
    يجمع الأخبار المتشابهة في مجموعات.
    يعيد قائمة من: (link, title, feed_urls_list, summary)
    حيث feed_urls_list = قائمة كل المصادر التي غطّت القصة.
    """
    if not items:
        return []
    clusters = []
    used = set()
    for i, (link_i, title_i, feed_i, sum_i) in enumerate(items):
        if i in used:
            continue
        group = [(link_i, title_i, feed_i, sum_i)]
        used.add(i)
        for j, (link_j, title_j, feed_j, sum_j) in enumerate(items):
            if j in used:
                continue
            sim = _cosine_similarity_titles(title_i, title_j)
            if sim >= threshold:
                group.append((link_j, title_j, feed_j, sum_j))
                used.add(j)
        # ممثّل المجموعة = أول خبر (الأقدم / الأكثر تفصيلاً)
        rep_link, rep_title, rep_feed, rep_sum = group[0]
        all_feeds = list({g[2] for g in group})
        clusters.append((rep_link, rep_title, all_feeds, rep_sum, len(group)))
    return clusters

