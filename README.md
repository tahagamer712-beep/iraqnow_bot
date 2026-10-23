<div align="center">

# IraqNow Bot — بوت «عراق الآن»

**بوت تيليغرام إخباري متكامل للعراق: أخبار عاجلة على مدار الساعة، رياضة، طقس، وذكاء اصطناعي — يعمل من هاتف أندرويد عبر Termux**

*A full-featured Iraqi news bot for Telegram: 24/7 breaking news, sports, weather and AI — running from an Android phone via Termux*

[![Python](https://img.shields.io/badge/Python-3.11%2B-3776AB?logo=python&logoColor=white)](https://www.python.org)
[![Telegram](https://img.shields.io/badge/Telegram-Bot-26A5E4?logo=telegram&logoColor=white)](https://telegram.org)
[![Platform](https://img.shields.io/badge/Platform-Termux%20%2F%20Android-A4C639?logo=android&logoColor=white)](#-التثبيت-والتشغيل)
[![Channel](https://img.shields.io/badge/Channel-%40raqnow-26A5E4?logo=telegram&logoColor=white)](https://t.me/raqnow)

[العربية](#-بالعربية) · [English](#-in-english)

</div>

---

# 🇮🇶 بالعربية

## نبذة

**عراق الآن (IraqNow)** بوت أخبار عراقي على تيليغرام يجمع الأخبار من عشرات المصادر العراقية والعربية عبر RSS، يتحقق منها، يزيل المكرر، ثم يبثّها فورًا إلى قناة البوت ومشتركيه — مع صور مختومة بهوية القناة، وملخصات بالذكاء الاصطناعي، وتغطية رياضية حية، ونشرة صوتية.

البوت مصمم ليعمل **بشكل مستقل بالكامل من هاتف أندرويد** عبر Termux (Long Polling — بلا خوادم وبلا Webhook)، مع مراقبة صحية ذاتية واسترداد تلقائي من الأعطال.

## ✨ الميزات

### للمستخدمين
- **أخبار عاجلة لحظة بلحظة** من مصادر عراقية وعربية متعددة، مع كشف التكرار وسياسة حداثة صارمة (لا أخبار قديمة)
- **واجهة بسيطة**: أمر `/start` واحد فقط، وكل شيء آخر عبر أزرار تفاعلية
- **أقسام إخبارية**: سياسة، اقتصاد، أمن، مجتمع، منوعات — مع تخصيص حسب اهتمامات المستخدم
- **رياضة متكاملة**: مباريات حية، نتائج، أخبار رياضية، وتنبيهات للمباريات المهمة
- **طقس ومواقيت صلاة** للمدن العراقية
- **أخبار صوتية وبودكاست** بتقنية تحويل النص إلى كلام (TTS)
- **ذكاء اصطناعي**: تلخيص الأخبار، تحقق من الادعاءات (Fact-Check)، وتحليل وتوقعات
- **بحث واكتشاف**: محرك اكتشاف مصادر يضيف تغذيات جديدة تلقائيًا (منها وكالة الأنباء العراقية INA)

### للإدارة
- **لوحة تحكم كاملة داخل البوت**: إحصائيات، إدارة مستخدمين، إدارة قنوات، إدارة مصادر RSS
- **غرفة أزمات** للتعامل مع الأخبار العاجلة يدويًا عند الحاجة
- **بث يدوي وتلقائي** مع حدود نشر ذكية تمنع الإغراق
- **نشر موازٍ** على فيسبوك وإنستغرام
- **نسخ احتياطي تلقائي** لقناة خاصة + استرداد تلقائي ومراقبة صحة على مدار الساعة

## 🧱 التقنيات

| الطبقة | التقنية |
|---|---|
| اللغة | Python 3.11+ |
| واجهة تيليغرام | pyTelegramBotAPI (Long Polling) |
| الأخبار | feedparser + requests + BeautifulSoup |
| الجدولة | APScheduler |
| التخزين | SQLite + ملفات حالة JSON |
| الصوت | edge-tts / gTTS |
| الذكاء الاصطناعي | Gemini · Groq · OpenRouter · Together · Mistral · Cohere (تعدد مزودين بسقوط تلقائي) |
| بيئة التشغيل | Termux على Android |

## 🚀 التثبيت والتشغيل

### 1) تجهيز Termux

```bash
pkg update && pkg upgrade
pkg install python git
```

### 2) جلب المشروع وتثبيت المتطلبات

```bash
git clone https://github.com/tahagamer712-beep/iraqnow_bot.git
cd iraqnow_bot
pip install -r requirements.txt
```

### 3) الإعداد

```bash
cp .env.example .env
nano .env
```

املأ القيمتين الإلزاميتين على الأقل:

```ini
BOT_TOKEN=توكن_البوت_من_BotFather
ADMIN_ID=رقم_تيليغرام_الأدمن
```

### 4) التشغيل

```bash
bash start.sh
```

أو مباشرة:

```bash
python main.py
```

### التشغيل في الخلفية

```bash
nohup python main.py > iraqnow_bot.log 2>&1 &
```

> دليل مفصّل خطوة بخطوة: [`دليل_التشغيل_على_Termux.md`](دليل_التشغيل_على_Termux.md)

## ⚙️ متغيرات البيئة

| المتغير | إلزامي | الوصف |
|---|:---:|---|
| `BOT_TOKEN` | ✅ | توكن البوت من @BotFather |
| `ADMIN_ID` | ✅ | الرقم الرقمي لحساب الأدمن |
| `WEATHER_KEY` | — | مفتاح OpenWeatherMap |
| `NEWS_KEY` | — | مفتاح NewsAPI |
| `GEMINI_API_KEY` | — | ذكاء اصطناعي — Gemini |
| `GROQ_API_KEY` | — | ذكاء اصطناعي — Groq |
| `OPENROUTER_KEY` | — | ذكاء اصطناعي — OpenRouter |
| `TOGETHER_API_KEY` | — | ذكاء اصطناعي — Together |
| `MISTRAL_API_KEY` | — | ذكاء اصطناعي — Mistral |
| `COHERE_API_KEY` | — | ذكاء اصطناعي — Cohere |
| `FB_PAGE_TOKEN` / `FB_PAGE_ID` | — | النشر على فيسبوك |
| `IG_USER_ID` / `IMGBB_API_KEY` | — | النشر على إنستغرام / رفع الصور |
| `BACKUP_CHANNEL_ID` | — | قناة النسخ الاحتياطي |

> بدائل الذكاء الاصطناعي اختيارية: غيابها يعطّل ميزات AI فقط، وبقية البوت يعمل كاملًا.

## 🗂️ بنية المشروع

```
iraqnow_bot/
├── main.py                  # نقطة الدخول — Long Polling ومعالجة الإشارات
├── config.py                # الإعدادات وأعلام الميزات
├── bot_legacy.py            # النواة المركزية
├── bot_*.py                 # مثيل البوت، الثبات، المهام المجدولة، المالية، الطقس والصلاة
├── handler_*.py             # معالجات: البدء، الأخبار، الرياضة، AI، الصوت، الإعدادات، الإدارة
├── news_*.py                # خط الأخبار: بث، تنسيق، ترشيح، إزالة تكرار، تتبع
├── rss_*.py                 # جلب RSS والتحقق والتخزين المؤقت + discovery.py لاكتشاف المصادر
├── ai_*.py                  # محرك AI: تحليل، تلخيص، تحقق، ذاكرة، RAG، تخصيص
├── sports_*.py              # رياضة: مباريات حية، نتائج، أخبار، تنبيهات
├── admin_*.py               # لوحة الإدارة: إحصاء، مستخدمون، قنوات، RSS، بث، غرفة أزمات
├── db_*.py                  # طبقة البيانات: مخطط، مستخدمون، قنوات، نسخ احتياطي، كاش
├── users_*.py               # المستخدمون: بريميوم، إحالات، إحصاء
├── data_*.py                # بيانات ثابتة: مصادر، ترجمات، واجهة، اهتمامات
└── health_monitor.py        # مراقبة الصحة والاسترداد التلقائي
```

## 📝 ملاحظات

- ملف `.env` الحقيقي **لا يُرفع أبدًا** إلى المستودع — الأسرار تبقى على الجهاز فقط، وفي المستودع `.env.example` نموذجي.
- قواعد البيانات وملفات حالة التشغيل (JSON) بيانات حية محلية، غير مشمولة بالمستودع.
- البوت يعمل بنسخة واحدة منفردة؛ أي نسخة ثانية تسبب تعارض `getUpdates` على تيليغرام.

---

# 🌍 In English

## About

**IraqNow** is an Iraqi news bot for Telegram. It aggregates news from dozens of Iraqi and Arab RSS sources, verifies and deduplicates them, then broadcasts them instantly to the bot's channel and subscribers — with branded news images, AI summaries, live sports coverage, and a voice news briefing.

The bot is designed to run **fully autonomously from an Android phone** via Termux (long polling — no servers, no webhooks), with self health-monitoring and automatic crash recovery.

## ✨ Features

### For users
- **Breaking news in real time** from multiple Iraqi & Arab sources, with deduplication and a strict freshness policy (no stale news)
- **Minimal UI**: a single `/start` command — everything else is inline buttons
- **News sections**: politics, economy, security, society and more, personalized to each user's interests
- **Full sports coverage**: live matches, scores, sports news and big-match alerts
- **Weather & prayer times** for Iraqi cities
- **Voice news & podcasts** via text-to-speech (TTS)
- **AI features**: news summarization, fact-checking, analysis and predictions
- **Source discovery engine** that finds and adds new feeds automatically (including the Iraqi News Agency — INA)

### For admins
- **Full in-bot admin panel**: statistics, user management, channel management, RSS source management
- **Crisis room** for hands-on handling of major breaking stories
- **Manual & automatic broadcasting** with smart rate limits that prevent flooding
- **Cross-posting** to Facebook and Instagram
- **Automatic backups** to a private channel, plus 24/7 health monitoring and auto-recovery

## 🧱 Tech stack

| Layer | Technology |
|---|---|
| Language | Python 3.11+ |
| Telegram API | pyTelegramBotAPI (long polling) |
| News ingestion | feedparser + requests + BeautifulSoup |
| Scheduling | APScheduler |
| Storage | SQLite + JSON state files |
| Voice | edge-tts / gTTS |
| AI | Gemini · Groq · OpenRouter · Together · Mistral · Cohere (multi-provider with automatic fallback) |
| Runtime | Termux on Android |

## 🚀 Installation & running

### 1) Prepare Termux

```bash
pkg update && pkg upgrade
pkg install python git
```

### 2) Clone and install dependencies

```bash
git clone https://github.com/tahagamer712-beep/iraqnow_bot.git
cd iraqnow_bot
pip install -r requirements.txt
```

### 3) Configure

```bash
cp .env.example .env
nano .env
```

Fill in at least the two required values:

```ini
BOT_TOKEN=your_token_from_BotFather
ADMIN_ID=your_numeric_telegram_id
```

### 4) Run

```bash
bash start.sh
```

or directly:

```bash
python main.py
```

### Run in the background

```bash
nohup python main.py > iraqnow_bot.log 2>&1 &
```

## ⚙️ Environment variables

| Variable | Required | Description |
|---|:---:|---|
| `BOT_TOKEN` | ✅ | Bot token from @BotFather |
| `ADMIN_ID` | ✅ | Admin's numeric Telegram ID |
| `WEATHER_KEY` | — | OpenWeatherMap API key |
| `NEWS_KEY` | — | NewsAPI key |
| `GEMINI_API_KEY` | — | AI — Gemini |
| `GROQ_API_KEY` | — | AI — Groq |
| `OPENROUTER_KEY` | — | AI — OpenRouter |
| `TOGETHER_API_KEY` | — | AI — Together |
| `MISTRAL_API_KEY` | — | AI — Mistral |
| `COHERE_API_KEY` | — | AI — Cohere |
| `FB_PAGE_TOKEN` / `FB_PAGE_ID` | — | Facebook cross-posting |
| `IG_USER_ID` / `IMGBB_API_KEY` | — | Instagram cross-posting / image hosting |
| `BACKUP_CHANNEL_ID` | — | Backup channel |

> AI provider keys are optional: without them only the AI features are disabled — the rest of the bot works fully.

## 🗂️ Project structure

```
iraqnow_bot/
├── main.py                  # Entry point — long polling & signal handling
├── config.py                # Settings and feature flags
├── bot_legacy.py            # Central core
├── bot_*.py                 # Bot instance, persistence, scheduled jobs, finance, weather & prayers
├── handler_*.py             # Handlers: start, news, sports, AI, voice, settings, admin
├── news_*.py                # News pipeline: broadcast, formatting, filtering, dedup, tracking
├── rss_*.py                 # RSS fetching, validation, caching + discovery.py source discovery
├── ai_*.py                  # AI engine: analysis, summaries, fact-check, memory, RAG, personalization
├── sports_*.py              # Sports: live matches, fixtures, news, notifications
├── admin_*.py               # Admin panel: stats, users, channels, RSS, broadcast, crisis room
├── db_*.py                  # Data layer: schema, users, channels, backup, cache
├── users_*.py               # Users: premium, referrals, stats
├── data_*.py                # Static data: sources, translations, UI, interests
└── health_monitor.py        # Health monitoring & automatic recovery
```

## 📝 Notes

- The real `.env` file is **never** committed — secrets stay on the device; the repo only carries the `.env.example` template.
- Databases and runtime state files (JSON) are live local data and are not part of the repository.
- The bot runs as a single instance; a second instance causes Telegram `getUpdates` conflicts.

---

<div align="center">

**IraqNow Bot** — أخبار العراق، لحظة بلحظة 🇮🇶
القناة: [@raqnow](https://t.me/raqnow) · البوت: [@Iraqnowbot](https://t.me/Iraqnowbot)

</div>
