# -*- coding: utf-8 -*-
"""
brand.py — الهوية المركزية (White Label) + العلامة المائية (مرحلة 7، 2026-10-22)

- إعدادات العلامة في brand.json: الاسم، التوقيع النصي، تفعيل العلامة
  المائية على الصور لكل وجهة (قنوات/مستخدمون).
- العلامة: شارة داكنة نصف شفافة بأسفل يسار الصورة باسم المنصة بخط عربي
  (NotoNaskhArabic-Bold مع RAQM للتشكيل الصحيح) أو DejaVu للأسماء اللاتينية.
- الصور المعالجة تُخزّن مؤقتًا بملفات محلية (مسار الإرسال يقبل ملفًا
  محليًا) مع تنظيف دوري — وأي فشل يعيد الرابط الأصلي كما هو.
"""
import hashlib
import io
import json
import os
import time

_DIR = os.path.dirname(os.path.abspath(__file__))
BRAND_PATH = os.path.join(_DIR, "brand.json")
CACHE_DIR = os.path.join(_DIR, "branded_cache")

DEFAULTS = {
    "name": "العراق الآن",
    "signature": "",
    "brand_channels": True,
    "brand_users": False,
    "position": "bl",
}

_CACHE = {"mtime": 0, "data": None}


def get_brand():
    try:
        mt = os.path.getmtime(BRAND_PATH)
    except Exception:
        mt = 0
    if _CACHE["data"] is None or mt != _CACHE["mtime"]:
        data = dict(DEFAULTS)
        try:
            with io.open(BRAND_PATH, encoding="utf-8") as f:
                saved = json.load(f)
            if isinstance(saved, dict):
                data.update({k: v for k, v in saved.items() if k in DEFAULTS})
        except Exception:
            pass
        _CACHE["data"] = data
        _CACHE["mtime"] = mt
    return dict(_CACHE["data"])


def set_brand(**kw):
    data = get_brand()
    for k, v in kw.items():
        if k in DEFAULTS:
            data[k] = v
    tmp = BRAND_PATH + ".tmp"
    with io.open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
    os.replace(tmp, BRAND_PATH)
    _CACHE["data"] = None
    return data


def brand_name():
    return get_brand().get("name") or DEFAULTS["name"]


# ── العلامة المائية بيوزرات (قرار طه 2026-10-22) ─────────────────────────
# القاعدة: يوزر البوت على كل صورة موسومة؛ وعند النشر لقناة الوكالة يُضاف
# يوزر القناة معه. باقي القنوات (المضافة من المستخدمين وغيرها): يوزر البوت فقط.
BOT_USERNAME = "@Iraqnowbot"
AGENCY_USERNAME = "@raqnow"
AGENCY_CHANNEL_IDS = (-1003800735448,)


def watermark_text(chat_id=None):
    """نص العلامة المائية حسب الوجهة."""
    try:
        cid = int(chat_id)
    except Exception:
        cid = None
    if cid in AGENCY_CHANNEL_IDS or (
            isinstance(chat_id, str) and chat_id.strip().lower() in
            ("@raqnow", "raqnow")):
        return BOT_USERNAME + "  •  " + AGENCY_USERNAME
    return BOT_USERNAME


def apply_text_tokens(text):
    """يستبدل {brand} و{brand_name} باسم المنصة، ويضيف التوقيع النصي
    المضبوط كسطر أخير إن وُجد ولم يكن حاضرًا."""
    if not text:
        return text
    name = brand_name()
    out = text.replace("{brand_name}", name).replace("{brand}", name)
    sig = (get_brand().get("signature") or "").strip()
    if sig and sig not in out:
        out = out.rstrip() + "\n" + sig
    return out


def _font_for(name, size):
    from PIL import ImageFont
    if any("\u0600" <= ch <= "\u06FF" for ch in name):
        path = "/system/fonts/NotoNaskhArabic-Bold.ttf"
    else:
        path = "/data/data/com.termux/files/usr/share/fonts/TTF/DejaVuSans-Bold.ttf"
    return ImageFont.truetype(path, size)


def _process(img_bytes, name):
    from PIL import Image, ImageDraw
    img = Image.open(io.BytesIO(img_bytes)).convert("RGB")
    w, h = img.size
    if w < 240 or h < 180:
        return None
    draw = ImageDraw.Draw(img, "RGBA")
    size = max(15, int(w * 0.038))
    font = _font_for(name, size)
    bbox = draw.textbbox((0, 0), name, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    pad = max(8, size // 3)
    brand = get_brand()
    pos = brand.get("position", "bl")
    margin = max(10, int(w * 0.015))
    if pos == "br":
        x0 = w - tw - pad * 2 - margin
    else:
        x0 = margin
    y0 = h - th - pad * 2 - margin
    draw.rounded_rectangle([x0, y0, x0 + tw + pad * 2, y0 + th + pad * 2],
                           radius=max(6, size // 3), fill=(0, 0, 0, 150))
    draw.text((x0 + pad - bbox[0], y0 + pad - bbox[1]), name, font=font,
              fill=(255, 255, 255, 238))
    out = io.BytesIO()
    img.save(out, "JPEG", quality=86)
    return out.getvalue()


def _cleanup_cache(keep=48):
    try:
        files = [os.path.join(CACHE_DIR, f) for f in os.listdir(CACHE_DIR)
                 if f.endswith(".jpg")]
        if len(files) <= keep:
            return
        files.sort(key=lambda p: os.path.getmtime(p))
        for p in files[:len(files) - keep]:
            try:
                os.remove(p)
            except Exception:
                pass
    except Exception:
        pass


def branded_photo(photo_url, is_channel, chat_id=None):
    """يعيد مسار ملف محلي موسوم أو الرابط الأصلي عند التعطيل/الفشل."""
    try:
        brand = get_brand()
        enabled = brand.get("brand_channels") if is_channel else brand.get("brand_users")
        if not enabled:
            return photo_url
        if not isinstance(photo_url, str) or not photo_url.startswith("http"):
            return photo_url
        os.makedirs(CACHE_DIR, exist_ok=True)
        wm_text = watermark_text(chat_id)
        key = hashlib.md5((photo_url + "|" + wm_text).encode("utf-8")).hexdigest()
        path = os.path.join(CACHE_DIR, key + ".jpg")
        if os.path.exists(path) and os.path.getsize(path) > 1000:
            return path
        import requests
        r = requests.get(photo_url, timeout=5, headers={
            "User-Agent": "Mozilla/5.0 (compatible; IraqNowBot)"})
        if r.status_code != 200 or len(r.content) > 3_500_000 or len(r.content) < 3000:
            return photo_url
        processed = _process(r.content, wm_text)
        if not processed:
            return photo_url
        tmp = path + ".tmp"
        with open(tmp, "wb") as f:
            f.write(processed)
        os.replace(tmp, path)
        _cleanup_cache()
        return path
    except Exception:
        return photo_url


def is_channel_dest(chat_id):
    if isinstance(chat_id, str):
        return chat_id.startswith("@") or chat_id.lstrip("-").isdigit()
    try:
        return int(chat_id) < 0
    except Exception:
        return False
