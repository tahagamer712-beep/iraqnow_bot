# -*- coding: utf-8 -*-
"""
  handler_start.py — /start + رسالة الترحيب + لوحة رئيسية

  يُصدِّر معالج أمر /start ودوال الترحيب.
  """

import sys as _sys_legacy
import os
# ─── استيراد كل المتغيرات العالمية من bot_legacy ───
from bot_legacy import *
import state as gl  # noqa: F401,F403

def send_first_time_welcome(uid, name):
    markup = types.InlineKeyboardMarkup(row_width=2)
    for _li, _lang_name in enumerate(languages.values()):
        markup.add(types.InlineKeyboardButton(_lang_name, callback_data=f"pick:lang:{_li}"))
    sent = bot.send_message(uid, LANG_SELECT_MSG, parse_mode="Markdown", reply_markup=markup)
    try:
        bot.pin_chat_message(uid, sent.message_id, disable_notification=True)
    except Exception as _exc:
        _log_exc(_exc)

# ======== رسالة الترحيب (اختيار اللغة) ========
def welcome_user(uid):
    markup = types.InlineKeyboardMarkup(row_width=2)
    for _li, _lang_name in enumerate(languages.values()):
        markup.add(types.InlineKeyboardButton(_lang_name, callback_data=f"pick:lang:{_li}"))
    sent = bot.send_message(uid, LANG_SELECT_MSG, parse_mode="Markdown", reply_markup=markup)
    try:
        bot.pin_chat_message(uid, sent.message_id, disable_notification=True)
    except Exception as _exc:
        _log_exc(_exc)

# ======== تلميح الاستخدام ========
def send_main_menu(uid):
    """القائمة الرئيسية — لوحة أزرار إنلاين داخل المحادثة (حُوّلت من الكيبورد السفلي 2026-10-22)."""
    lang = users[str(uid)].get("lang", "English 🇬🇧")
    btn = BUTTONS.get(lang, BUTTONS["English 🇬🇧"])
    notif_on = users[str(uid)].get("notifications", True)
    notif_label = btn["notif_on"] if notif_on else btn["notif_off"]
    # ── ترحيل لمرة واحدة: إزالة لوحة المفاتيح السفلية القديمة من شاشة المستخدم ──
    if not users[str(uid)].get("kb_inline_v2"):
        users[str(uid)]["kb_inline_v2"] = True
        try:
            _db_save_all_users(users)
        except Exception as _exc:
            _log_exc(_exc)
        _notice = {
            "العربية 🇮🇶": "✨ حدّثنا القائمة: صارت أزرارًا داخل المحادثة بدل لوحة المفاتيح 👇",
            "English 🇬🇧": "✨ Menu updated: the buttons now live inside the chat 👇",
        }
        try:
            bot.send_message(uid, _notice.get(lang, _notice["English 🇬🇧"]),
                             reply_markup=types.ReplyKeyboardRemove())
        except Exception as _exc:
            _log_exc(_exc)
    _IB = types.InlineKeyboardButton
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(_IB(btn.get("news_select", "📋 اختيار الأخبار"), callback_data="m:news_select"))
    markup.add(
        _IB(btn.get("mode30", "⚡ وضع 30 ثانية"), callback_data="m:mode30"),
        _IB(btn.get("noanalysis", "😐 بدون تحليل"), callback_data="m:noanalysis"),
    )
    markup.add(
        _IB(btn.get("zbda", "💡 زبدة الموضوع"), callback_data="m:zbda"),
        _IB(btn.get("before_happen", "🔮 قبل ما يصير"), callback_data="m:before_happen"),
    )
    markup.add(
        _IB(btn.get("imgcard", "🖼 خبر بصورة"), callback_data="m:imgcard"),
        _IB(btn.get("deepsearch", "🧠 بحث عميق"), callback_data="m:deepsearch"),
    )
    markup.add(
        _IB(btn["news"], callback_data="m:news"),
        _IB(btn["search"], callback_data="m:search"),
    )
    markup.add(
        _IB(btn["daily_summary"], callback_data="m:daily_summary"),
        _IB(btn.get("trending", "🔥 الأكثر تداولاً"), callback_data="m:trending"),
    )
    markup.add(
        _IB(btn["weather"], callback_data="m:weather"),
        _IB(btn["prayer"], callback_data="m:prayer"),
    )
    markup.add(
        _IB(btn["currency"], callback_data="m:currency"),
        _IB(btn["crypto"], callback_data="m:crypto"),
    )
    markup.add(
        _IB("💹 الأسواق", callback_data="run:markets"),
        _IB("🤖 اسأل الذكاء", callback_data="run:ask"),
    )
    markup.add(
        _IB("❓ مساعدة", callback_data="run:help"),
        _IB("🧩 كل الميزات", callback_data="grid:features"),
    )
    markup.add(
        _IB(notif_label, callback_data="m:notif"),
        _IB(btn["settings"], callback_data="m:settings"),
    )
    markup.add(_IB("💬 تواصل / Contact", url=CONTACT_LINK))
    bot.send_message(uid, btn["choose"], reply_markup=markup)

# ======== /start — المعالج الحقيقي (FIX: لم يكن مربوطاً بأي ديكوريتور أصلاً) ========
@bot.message_handler(commands=['start'])
def start(message):
    uid = message.from_user.id
    if uid in banned:
        _ban_lang = users.get(str(uid), {}).get("lang", "العربية 🇮🇶")
        bot.send_message(uid, _ui("user_banned", _ban_lang))
        return
    if bot_paused and not is_admin(uid):
        _pause_lang = users.get(str(uid), {}).get("lang", "العربية 🇮🇶")
        bot.send_message(uid, _ui("bot_paused", _pause_lang) if not pause_message or pause_message == "🔧 البوت متوقف مؤقتاً، سيعود قريباً." else pause_message)
        return
    username = message.from_user.username or "لا يوزر"
    args = message.text.split()
    referrer_id = None
    if len(args) > 1 and args[1].startswith("ref_"):
        try:
            referrer_id = int(args[1][4:])
        except Exception as _exc:
            _log_exc(_exc)
    is_new = str(uid) not in users
    if is_new:
        users[str(uid)] = {
            "name": message.from_user.first_name,
            "first_name": message.from_user.first_name or "",
            "last_name": message.from_user.last_name or "",
            "username": message.from_user.username or "",
            "telegram_lang": message.from_user.language_code or "",
            "sent_news": {},
            "first_visit": True,
            "referrals": [],
            "join_date": _now_sa().strftime("%Y-%m-%d"),
            "last_command": "/start"
        }
        # ─── تتبع المستخدمين الجدد للتقرير اليومي ────────────────────
        with _daily_new_users_lock:
            _daily_new_users.append(uid)
        # نظام الإحالات حُذف بقرار طه (مرحلة 8 — 2026-10-22): روابط ref تُعامل كبدء عادي بلا اعتماد ولا مكافآت
        _db_save_all_users(users)
        update_stats("new_user", uid=uid)
        all_admins = [ADMIN_ID] + extra_admins
        referrer_name = None
        if referrer_id and str(referrer_id) in users:
            referrer_name = users[str(referrer_id)].get("name", str(referrer_id))
        join_time = _now_sa().strftime("%H:%M - %d/%m/%Y")
        new_user_msg = (
            f"🆕 *مستخدم جديد انضم!*\n"
            f"━━━━━━━━━━━━━━\n"
            f"👤 الاسم: *{message.from_user.first_name}*\n"
            f"🆔 ID: `{uid}`\n"
            f"📛 اليوزر: @{username}\n"
            f"⏰ وقت الانضمام: `{join_time}`\n"
            f"👈 جاء عبر: {('دعوة من *' + referrer_name + '*') if referrer_name else 'مباشر'}\n"
            f"━━━━━━━━━━━━━━\n"
            f"👥 إجمالي المستخدمين: `{len(users)}`"
        )
        quick_markup = types.InlineKeyboardMarkup(row_width=2)
        quick_markup.add(
            types.InlineKeyboardButton("👤 عرض ملفه", callback_data=f"admin_view_{uid}"),
            types.InlineKeyboardButton("🚫 حظر", callback_data=f"quick_ban_{uid}"),
            types.InlineKeyboardButton("📢 راسله", url=f"tg://user?id={uid}"),
        )
        for admin_id in all_admins:
            try:
                bot.send_message(admin_id, new_user_msg, parse_mode="Markdown", reply_markup=quick_markup)
            except Exception as _exc:
                _log_exc(_exc)
        send_first_time_welcome(uid, message.from_user.first_name)
    else:
        users[str(uid)]["name"] = message.from_user.first_name
        users[str(uid)]["first_name"] = message.from_user.first_name or ""
        users[str(uid)]["last_name"] = message.from_user.last_name or ""
        users[str(uid)]["username"] = message.from_user.username or ""
        users[str(uid)]["telegram_lang"] = message.from_user.language_code or ""
        users[str(uid)]["last_command"] = "/start"
        # FIX: إعادة تفعيل البث إذا كان المستخدم حظر البوت ثم فتحه مجدداً
        if not users[str(uid)].get("notifications", True):
            users[str(uid)]["notifications"] = True
            _logger.info("🔔 أُعيد تفعيل notifications للمستخدم %s بعد /start", uid)
        user = users[str(uid)]
        lang = user.get("lang", "English 🇬🇧")
        user_feeds = RSS.get(lang, [])
        if user_feeds:
            # BUGFIX: ensure current_sent is always dict before merging
            current_sent = user.get("sent_news", {})
            if not isinstance(current_sent, dict):
                current_sent = {}
            fresh_links = prefill_sent_news(user_feeds)  # now returns dict
            users[str(uid)]["sent_news"] = {**current_sent, **fresh_links}
        _db_save_all_users(users)
        _send_welcome_greeting(uid, message.from_user.first_name, lang)
        # طلب طه (2026-10-22): /start للأدمن يعرض الترحيب + لوحة الأدمن مباشرة
        if is_admin(uid):
            try:
                admin_panel(uid)
            except Exception as _exc:
                _log_exc(_exc)

def _send_welcome_greeting(uid, name, lang="English 🇬🇧"):
    """رسالة الترحيب والتواصل فقط — بدون إعادة إعداد."""
    try:
        import brand as _brand_greet
        _bn = _brand_greet.brand_name()
    except Exception:
        _bn = "العراق الآن"
    contact_markup = types.InlineKeyboardMarkup()
    contact_markup.add(types.InlineKeyboardButton("🏠 القائمة الرئيسية", callback_data="menu_main"))
    contact_markup.add(types.InlineKeyboardButton("💬 تواصل / Contact", url=CONTACT_LINK))
    greetings = {
        "العربية 🇮🇶":   f"👋 *أهلاً {name}!*\n\n*{_bn}* 🇮🇶 — _أخبار العراق لحظة بلحظة_\n\n",
        "English 🇬🇧":  f"👋 *Welcome back, {name}!*\n\nGlad to see you at *{_bn}* 🌍\n\n",
        "Русский 🇷🇺":  f"👋 *С возвращением, {name}!*\n\nРады видеть вас снова! 🌍\n\n",
        "فارسی 🇮🇷":    f"👋 *خوش آمدید، {name}!*\n\nخوشحالیم که برگشتید! 🌍\n\n",
        "हिन्दी 🇮🇳":   f"👋 *वापस स्वागत है, {name}!*\n\nआपको देखकर खुशी हुई! 🌍\n\n",
        "Português 🇧🇷": f"👋 *Bem-vindo de volta, {name}!*\n\nFeliz em vê-lo novamente! 🌍\n\n",
        "Türkçe 🇹🇷":   f"👋 *Tekrar hoş geldiniz, {name}!*\n\nSizi yeniden görmekten mutluyuz! 🌍\n\n",
        "اردو 🇵🇰":     f"👋 *خوش آمدید، {name}!*\n\nآپ کو دوبارہ دیکھ کر خوشی ہوئی! 🌍\n\n",
        "Deutsch 🇩🇪":  f"👋 *Willkommen zurück, {name}!*\n\nSchön, Sie wiederzusehen! 🌍\n\n",
        "Українська 🇺🇦": f"👋 *З поверненням, {name}!*\n\nРаді бачити вас знову! 🌍\n\n",
        "Italiano 🇮🇹": f"👋 *Bentornato, {name}!*\n\nFelici di rivederti! 🌍\n\n",
        "Español 🇲🇽":  f"👋 *¡Bienvenido de nuevo, {name}!*\n\n¡Feliz de verte de nuevo! 🌍\n\n",
    }
    body_lines = {
        "العربية 🇮🇶": (
            "شنو راح تلقى هنا؟\n\n"
            "📰 *آخر الأخبار* — العاجل والمحلي والعالمي أول بأول\n"
            "🌤 *حالة الطقس* — طقس مدينتك بالتفصيل\n"
            "💰 *الأسواق والعملات* — الدولار والذهب والنفط والأسهم\n"
            "🏅 *الرياضة* — نتائج وأخبار المباريات\n"
            "🤖 *تحليل ذكي وبحث عميق* — اسأل عن أي موضوع\n"
            "🔖 *محفوظاتك وملخص الصباح* — أخبارك المحفوظة وملخص يومي\n\n"
            "اضغط «🏠 القائمة الرئيسية» واختر قسمك 👇"
        ),
        "English 🇬🇧": (
            "📰 Live world news\n"
            "🌤 Weather for your city\n"
            "💱 Currency & stock rates\n"
            "📊 /chart — Interactive chart\n"
            "❓ /help — Full commands guide\n"
            "🔄 /restart — Reset your settings"
        ),
        "Русский 🇷🇺": (
            "📰 Мировые новости в реальном времени\n"
            "🌤 Погода в вашем городе\n"
            "💱 Курсы валют и акций\n"
            "📊 /chart — Интерактивный график\n"
            "❓ /help — Полное руководство\n"
            "🔄 /restart — Перезапустить настройки"
        ),
        "فارسی 🇮🇷": (
            "📰 اخبار جهانی لحظهای\n"
            "🌤 آبوهوای شهر شما\n"
            "💱 نرخ ارز و سهام\n"
            "📊 /chart — نمودار تعاملی\n"
            "❓ /help — راهنمای کامل دستورات\n"
            "🔄 /restart — بازنشانی تنظیمات"
        ),
        "हिन्दी 🇮🇳": (
            "📰 लाइव विश्व समाचार\n"
            "🌤 आपके शहर का मौसम\n"
            "💱 मुद्रा और शेयर दरें\n"
            "📊 /chart — इंटरैक्टिव चार्ट\n"
            "❓ /help — पूरी कमांड गाइड\n"
            "🔄 /restart — सेटिंग्स रीसेट करें"
        ),
        "Português 🇧🇷": (
            "📰 Notícias mundiais ao vivo\n"
            "🌤 Clima para sua cidade\n"
            "💱 Taxas de câmbio e ações\n"
            "📊 /chart — Gráfico interativo\n"
            "❓ /help — Guia completo de comandos\n"
            "🔄 /restart — Redefinir configurações"
        ),
        "Türkçe 🇹🇷": (
            "📰 Canlı dünya haberleri\n"
            "🌤 Şehrinizin hava durumu\n"
            "💱 Döviz ve hisse senedi kurları\n"
            "📊 /chart — Etkileşimli grafik\n"
            "❓ /help — Tam komut rehberi\n"
            "🔄 /restart — Ayarları sıfırla"
        ),
        "اردو 🇵🇰": (
            "📰 لائیو عالمی خبریں\n"
            "🌤 آپ کے شہر کا موسم\n"
            "💱 کرنسی اور اسٹاک ریٹس\n"
            "📊 /chart — انٹرایکٹو چارٹ\n"
            "❓ /help — مکمل کمانڈ گائیڈ\n"
            "🔄 /restart — ترتیبات ری سیٹ کریں"
        ),
        "Deutsch 🇩🇪": (
            "📰 Live-Weltnachrichten\n"
            "🌤 Wetter für Ihre Stadt\n"
            "💱 Währungs- und Aktienkurse\n"
            "📊 /chart — Interaktives Diagramm\n"
            "❓ /help — Vollständige Befehlsanleitung\n"
            "🔄 /restart — Einstellungen zurücksetzen"
        ),
        "Українська 🇺🇦": (
            "📰 Світові новини в реальному часі\n"
            "🌤 Погода у вашому місті\n"
            "💱 Курси валют та акцій\n"
            "📊 /chart — Інтерактивний графік\n"
            "❓ /help — Повний посібник команд\n"
            "🔄 /restart — Скинути налаштування"
        ),
        "Italiano 🇮🇹": (
            "📰 Notizie mondiali in tempo reale\n"
            "🌤 Meteo per la tua città\n"
            "💱 Tassi di cambio e azioni\n"
            "📊 /chart — Grafico interattivo\n"
            "❓ /help — Guida completa ai comandi\n"
            "🔄 /restart — Reimposta le impostazioni"
        ),
        "Español 🇲🇽": (
            "📰 Noticias mundiales en vivo\n"
            "🌤 Clima para tu ciudad\n"
            "💱 Tasas de cambio y acciones\n"
            "📊 /chart — Gráfico interactivo\n"
            "❓ /help — Guía completa de comandos\n"
            "🔄 /restart — Restablecer configuración"
        ),
    }
    contact_labels = {
        "العربية 🇮🇶": "للتواصل",
        "English 🇬🇧": "Contact us",
        "Русский 🇷🇺": "Связаться",
        "فارسی 🇮🇷": "تماس با ما",
        "हिन्दी 🇮🇳": "संपर्क करें",
        "Português 🇧🇷": "Contato",
        "Türkçe 🇹🇷": "İletişim",
        "اردو 🇵🇰": "رابطہ کریں",
        "Deutsch 🇩🇪": "Kontakt",
        "Українська 🇺🇦": "Зв'язатися",
        "Italiano 🇮🇹": "Contattaci",
        "Español 🇲🇽": "Contacto",
    }
    greeting = greetings.get(lang, greetings["English 🇬🇧"])
    body = body_lines.get(lang, body_lines["English 🇬🇧"])
    contact_label = contact_labels.get(lang, contact_labels["English 🇬🇧"])
    text = (
        greeting
        + "━━━━━━━━━━━━━━━\n"
        + body + "\n"
        + "━━━━━━━━━━━━━━━\n"
        + f"💬 {contact_label}: {CONTACT_LINK}"
    )
    bot.send_message(uid, text, parse_mode="Markdown", reply_markup=contact_markup)

# ======== /reset — إعادة الإعداد من الصفر ========
@bot.message_handler(commands=["reset"])
def cmd_reset(m):
    uid = m.from_user.id
    if uid in banned:
        lang = users.get(str(uid), {}).get("lang", "العربية 🇮🇶")
        bot.send_message(uid, _ui("user_banned", lang))
        return
    if str(uid) not in users:
        welcome_user(uid)
        return
    user = users[str(uid)]
    kept = {
        "name": user.get("name", ""),
        "first_name": user.get("first_name", ""),
        "last_name": user.get("last_name", ""),
        "username": user.get("username", ""),
        "sent_news": {},
        "referrals": user.get("referrals", []),
        "referred_by": user.get("referred_by"),
        "join_date": user.get("join_date", ""),
        "unlocked_features": user.get("unlocked_features", []),
        "premium": user.get("premium", False),
    }
    kept = {k: v for k, v in kept.items() if v is not None}
    users[str(uid)] = kept
    _db_save_all_users(users)
    lang_map = {
        "العربية 🇮🇶":   "♻️ *تم إعادة ضبط البوت!*\n\nاختر لغتك من جديد 👇",
        "English 🇬🇧":  "♻️ *Bot has been reset!*\n\nPlease choose your language again 👇",
        "Русский 🇷🇺":  "♻️ *Бот сброшен!*\n\nПожалуйста, выберите язык снова 👇",
        "فارسی 🇮🇷":    "♻️ *ربات ریست شد!*\n\nلطفاً دوباره زبان خود را انتخاب کنید 👇",
        "हिन्दी 🇮🇳":   "♻️ *बॉट रीसेट हो गया!*\n\nकृपया फिर से अपनी भाषा चुनें 👇",
        "Português 🇧🇷":"♻️ *Bot foi redefinido!*\n\nPor favor, escolha seu idioma novamente 👇",
        "Türkçe 🇹🇷":   "♻️ *Bot sıfırlandı!*\n\nLütfen tekrar dilinizi seçin 👇",
        "اردو 🇵🇰":     "♻️ *بوٹ ری سیٹ ہو گیا!*\n\nبراہ کرم دوبارہ اپنی زبان منتخب کریں 👇",
        "Deutsch 🇩🇪":  "♻️ *Bot wurde zurückgesetzt!*\n\nBitte wählen Sie erneut Ihre Sprache 👇",
        "Українська 🇺🇦":"♻️ *Бота скинуто!*\n\nБудь ласка, виберіть мову знову 👇",
        "Italiano 🇮🇹": "♻️ *Bot reimpostato!*\n\nSi prega di scegliere di nuovo la lingua 👇",
        "Español 🇲🇽":  "♻️ *Bot restablecido!*\n\nPor favor, elige tu idioma nuevamente 👇",
    }
    reset_msg = lang_map.get(user.get("lang", "English 🇬🇧"), lang_map["English 🇬🇧"])
    bot.send_message(uid, reset_msg, parse_mode="Markdown")
    welcome_user(uid)


# ======== /restart — إعادة ضبط إعدادات المستخدم دون حذف بياناته ========

  # ═══════════════════════════════════════════════════════════════════════
# HEROKU: /setup_backup — إعداد قناة البكاب
# ═══════════════════════════════════════════════════════════════════════
def _send_main_menu_msg(chat_id, lang, text=None):
    lbl = _MENU_LABELS.get(lang, _MENU_LABELS["English 🇬🇧"])
    if not text:
        text = lbl.get("title", "🏠 القائمة الرئيسية")
    kb = _build_main_menu(lang)
    bot.send_message(chat_id, text, reply_markup=kb, parse_mode="Markdown")

# ─── معالجات القائمة ────────────────────────────────────────────
@bot.message_handler(commands=['menu'])
def handle_menu_cmd(message):
    uid = str(message.from_user.id)
    lang = users.get(uid, {}).get('lang', 'العربية 🇮🇶')
    _send_main_menu_msg(message.chat.id, lang)

@bot.callback_query_handler(func=lambda c: c.data == "menu_main")
def cb_menu_main(call):
    lang = users.get(str(call.from_user.id), {}).get('lang', 'العربية 🇮🇶')
    kb = _build_main_menu(lang)
    # SPEED 2026-10-23: إجابة الـcallback أولاً (يختفي مؤشر الانتظار فورًا) ثم تعديل الأزرار
    try: bot.answer_callback_query(call.id)
    except Exception: pass
    try:
        bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id, reply_markup=kb)
    except Exception:
        _send_main_menu_msg(call.message.chat.id, lang)

@bot.callback_query_handler(func=lambda c: c.data == "back_main")
def cb_back_main(call):
    """رجوع للقائمة الرئيسية من أي مكان"""
    lang = users.get(str(call.from_user.id), {}).get('lang', 'العربية 🇮🇶')
    kb = _build_main_menu(lang)
    # SPEED 2026-10-23: إجابة الـcallback أولاً (يختفي مؤشر الانتظار فورًا) ثم تعديل الأزرار
    try: bot.answer_callback_query(call.id)
    except Exception: pass
    try:
        bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id, reply_markup=kb)
    except Exception:
        _send_main_menu_msg(call.message.chat.id, lang)

