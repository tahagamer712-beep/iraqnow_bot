# -*- coding: utf-8 -*-
"""
  users_referral.py — نظام الإحالات + المكافآت

  يُصدِّر نظام الإحالات والمكافآت.
  """

import sys as _sys_legacy
import os
# ─── استيراد كل المتغيرات العالمية من bot_legacy ───
from bot_legacy import *
import state as gl  # noqa: F401,F403

def check_referral_rewards(referrer_id, new_member_name=""):
    # حُذف نظام الإحالات (مرحلة 8 — 2026-10-22): لا مكافآت إحالة بعد اليوم
    return
def ref_feature_callback(call):
    uid = call.from_user.id
    data = call.data
    bot.answer_callback_query(call.id)
    feat_key = data.replace("ref_feature_", "")
    if feat_key not in REFERRAL_FEATURES:
        return
    user = users.get(str(uid), {})
    lang = user.get("lang", "English 🇬🇧")
    unlocked = user.setdefault("unlocked_features", [])
    if feat_key in unlocked:
        bot.send_message(uid, _ui("feature_already_unlocked", lang))
        return
    unlocked.append(feat_key)
    users[str(uid)]["unlocked_features"] = unlocked
    _db_save_all_users(users)
    feat_name = REFERRAL_FEATURES[feat_key]
    _unlock_ok = {
        "العربية 🇮🇶":   f"✅ *تم فتح الميزة بنجاح!*\n\n🎁 *{feat_name}*\n\nيمكنك استخدامها الآن من /help.",
        "English 🇬🇧":   f"✅ *Feature unlocked!*\n\n🎁 *{feat_name}*\n\nUse /help to see all features.",
        "Русский 🇷🇺":   f"✅ *Функция разблокирована!*\n\n🎁 *{feat_name}*\n\nИспользуйте /help.",
        "فارسی 🇮🇷":     f"✅ *ویژگی باز شد!*\n\n🎁 *{feat_name}*\n\nاز /help استفاده کنید.",
        "Türkçe 🇹🇷":    f"✅ *Özellik açıldı!*\n\n🎁 *{feat_name}*\n\n/help ile tüm özellikleri görün.",
        "Deutsch 🇩🇪":   f"✅ *Funktion freigeschaltet!*\n\n🎁 *{feat_name}*\n\nNutze /help für alle Funktionen.",
        "Español 🇲🇽":   f"✅ *¡Función desbloqueada!*\n\n🎁 *{feat_name}*\n\nUsa /help para ver todo.",
        "Français 🇫🇷":  f"✅ *Fonctionnalité débloquée!*\n\n🎁 *{feat_name}*\n\nUtilisez /help.",
    }
    bot.send_message(uid, _unlock_ok.get(lang, _unlock_ok["English 🇬🇧"]), parse_mode="Markdown")

@bot.callback_query_handler(func=lambda c: c.data.startswith("prem_") or c.data.startswith("req_premium_") or c.data.startswith("interest_") or c.data == "premium_menu")
def send_top_referrers(uid):
    user = users.get(str(uid))
    lang = user.get("lang", "English 🇬🇧") if user else "English 🇬🇧"
    referral_counts = []
    for user_id, info in list(users.items()):
        refs = info.get("referrals", [])
        if refs:
            name = info.get("name", t(lang, "my_stats_user"))
            referral_counts.append((name, len(refs)))
    referral_counts.sort(key=lambda x: x[1], reverse=True)
    top = referral_counts[:10]
    if not top:
        bot.send_message(uid, t(lang, "top_referrers_empty"))
        return
    medals = ["🥇", "🥈", "🥉"] + ["4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟"]
    invite_word = t(lang, "top_referrers_invite")
    msg = t(lang, "top_referrers_header")
    for i, (name, count) in enumerate(top):
        medal = medals[i] if i < len(medals) else f"{i+1}."
        msg += f"{medal} *{name}* — {count} {invite_word}\n"
    bot.send_message(uid, msg, parse_mode="Markdown")

# ======== تنظيف البيانات التلقائي (Auto-Clean) ========
def send_referral_stats(uid):
    user = users.get(str(uid))
    if not user:
        return
    lang = user.get("lang", "العربية 🇮🇶")
    ref_count = len(user.get("referrals", []))
    invite_link = f"https://t.me/{BOT_USERNAME}?start=ref_{uid}"
    msg = st(lang, "referral_header").format(link=invite_link, count=ref_count)
    markup = types.InlineKeyboardMarkup()
    share_url = f"https://t.me/share/url?url={invite_link}&text=📱 @{BOT_USERNAME}"
    markup.add(types.InlineKeyboardButton(st(lang, "referral_share_btn"), url=share_url))
    bot.send_message(uid, msg, parse_mode="Markdown", reply_markup=markup)

# ======== انشر البوت ========
def send_share_bot(uid):
    user = users.get(str(uid))
    lang = user.get("lang", "English 🇬🇧") if user else "English 🇬🇧"
    invite_link = f"https://t.me/{BOT_USERNAME}"
    msg = t(lang, "share_bot_header").format(username=BOT_USERNAME, link=invite_link)
    markup = types.InlineKeyboardMarkup()
    share_url = f"https://t.me/share/url?url={invite_link}&text=@{BOT_USERNAME}"
    markup.add(
        types.InlineKeyboardButton(t(lang, "share_bot_btn"), url=share_url),
        types.InlineKeyboardButton(t(lang, "open_bot_btn"), url=invite_link)
    )
    bot.send_message(uid, msg, parse_mode="Markdown", reply_markup=markup)

# ======== إحصائيات البوت العامة ========
# حُذفت معالجات الإحالة (cmd_referral / cb_ref_show_list) — مرحلة 8، 2026-10-22
