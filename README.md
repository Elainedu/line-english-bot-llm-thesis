# LINE English-Learning Bot — LLM-Powered

An interactive English-learning chatbot on the LINE messaging platform, backed
by a large language model (OpenAI). Learners chat with the bot to practise
four core language skills:

| Feature | What it does |
|---|---|
| **Conversation** | Free-form English conversation practice with an LLM tutor |
| **Vocabulary (voc)** | Personalised vocabulary drills with pronunciation audio |
| **Listening** | Listening comprehension tasks with edge-TTS generated audio |
| **Shadowing** | Sentence-level pronunciation shadowing practice |

> **Academic context:** This is the code artefact of a master's thesis —
> *"LINE Bot 結合大型語言模型之英語學習系統設計與實作"* (Design and
> Implementation of an English-Learning System Combining a LINE Bot with a
> Large Language Model).

---

## Table of Contents

- [System Architecture](#system-architecture)
- [Repository Layout](#repository-layout)
- [Feature Module Anatomy](#feature-module-anatomy)
- [Message & Event Flow](#message--event-flow)
- [Tech Stack](#tech-stack)
- [Requirements](#requirements)
- [Configuration](#configuration)
- [Running Locally](#running-locally)
- [Deployment Notes](#deployment-notes)
- [What's Not in the Repo](#whats-not-in-the-repo)
- [License & Citation](#license--citation)

---

## System Architecture

```
                       ┌─────────────────┐
                       │   LINE User     │
                       │  (mobile app)   │
                       └────────┬────────┘
                                │  text / audio message
                                ▼
                       ┌─────────────────┐
                       │  LINE Platform  │  (LINE Messaging API)
                       └────────┬────────┘
                                │  Webhook POST /callback
                                ▼
    ┌───────────────────────────────────────────────────────┐
    │  Flask App  (app.py — create_app factory)             │
    │                                                       │
    │  ┌─────────────────────────────────────────────────┐  │
    │  │  Blueprint: app/api/line_api.py                 │  │
    │  │  • Verify X-Line-Signature                      │  │
    │  │  • Route MessageEvent / PostbackEvent           │  │
    │  │  • Dispatch to feature services                 │  │
    │  └───┬───────┬───────┬───────┬─────────────────────┘  │
    │      │       │       │       │                        │
    │      ▼       ▼       ▼       ▼                        │
    │    Conv.   Voc.  Listen.  Shadow.   ← feature svc     │
    │      │       │       │       │                        │
    │      └───────┴───┬───┴───────┘                        │
    │                  │                                    │
    │                  ▼                                    │
    │          ┌───────────────┐    ┌──────────────────┐    │
    │          │  OpenAI API   │    │   edge-tts       │    │
    │          │  (chat / gen) │    │  (text-to-MP3)   │    │
    │          └───────────────┘    └────────┬─────────┘    │
    │                                        │              │
    │                                        ▼              │
    │                            static/audio/*.mp3         │
    │                            (served via /audio route)  │
    └───────────────────────────────────────────────────────┘
                                │
                                │  reply (TextSendMessage /
                                │         AudioSendMessage /
                                │         Rich menu / QuickReply)
                                ▼
                       LINE Platform → user's LINE app
```

### Key architectural decisions

- **Factory pattern** (`create_app()` in `app.py`) — makes the app testable
  and lets configuration flow through env vars.
- **Blueprint modularisation** — LINE webhook logic is isolated in
  `app/api/line_api.py`; features live in `app/features/<feature>/`.
- **Feature service pattern** — each learning feature (conversation, voc,
  listening, shadowing) has its own `service.py` + `prompts/` folder,
  making it easy to add / remove skills without touching the routing layer.
- **Local audio cache** — TTS-generated MP3s are cached under
  `static/audio/` and re-used for future messages to save API calls.

---

## Repository Layout

The repo preserves the original Chinese folder names from the thesis.
Four parallel bot versions are kept side-by-side for comparison:

```
line-english-bot-llm-thesis/
├── 論文/                                # (thesis) — top-level bucket
│   ├── 程式碼/                          # (source code)
│   │   ├── line-english-bot/            # ← MAIN version (most complete)
│   │   ├── line-english-bot - 複製/     # experimental branch (copy)
│   │   └── 備份line-english-bot/        # earlier stable snapshot
│   └── 教學版本/                        # teaching / classroom version
│       └── line-english-bot/            # simplified cut used in lectures
└── README.md
```

Each bot folder has the same internal structure (documented below).

---

## Feature Module Anatomy

Inside a single bot version (`line-english-bot/`):

```
line-english-bot/
├── app.py                       # Flask entry — create_app() + /callback
├── requirements.txt             # Python deps
├── .env                         # (gitignored) LINE + OpenAI credentials
├── ngrok.exe                    # (gitignored) local webhook tunnelling
│
├── app/                         # main package
│   ├── __init__.py
│   ├── settings.py              # global config, constants
│   ├── compress_image.py        # image utility (Rich Menu images)
│   │
│   ├── api/
│   │   ├── __init__.py
│   │   └── line_api.py          # ★ LINE webhook Blueprint
│   │                            #   - TextMessage / AudioMessage handlers
│   │                            #   - Rich Menu setup
│   │                            #   - Postback dispatch
│   │
│   ├── features/                # per-skill services
│   │   ├── conversation/
│   │   │   ├── service.py       # ConversationService
│   │   │   ├── prompts/menu_prompts.py
│   │   │   └── audio/           # cached MP3
│   │   ├── voc/
│   │   │   ├── service.py       # VocabularyService
│   │   │   └── prompts/voc_prompts.py
│   │   ├── listening/
│   │   │   ├── service.py       # ListeningService
│   │   │   ├── prompts/listening_prompts.py
│   │   │   ├── audio/
│   │   │   └── static/
│   │   └── shadowing/
│   │       ├── service.py       # ShadowingService
│   │       ├── prompts/shadowing_prompts.py
│   │       ├── audio/
│   │       └── static/
│   │
│   ├── models/                  # data models (light — sessions on disk)
│   ├── templates/line/msg.py    # reusable LINE reply builders
│   │                            # (Flex/QuickReply/RichMenu templates)
│   ├── data/sessions/           # per-user session state (JSON on disk)
│   └── static/audio/            # bot-served MP3 assets
│
├── static/audio/                # top-level static, served at /audio/<file>
└── temp/                        # experimental scripts
    ├── app1.py                  # architecture prototypes
    ├── app2.py
    ├── app4.py
    └── test_openai.py
```

---

## Message & Event Flow

The core loop, from a user tapping "start listening practice" to hearing
audio:

1. **User taps a Rich Menu button** in LINE → LINE sends a **`PostbackEvent`**
   to `/callback`.
2. `line_api.py` verifies `X-Line-Signature` against `LINE_CHANNEL_SECRET`,
   then hands the event to the registered handler.
3. Handler inspects `postback.data`, matches a feature (e.g. `listening`),
   and calls the appropriate service method
   (`ListeningService.start_session(user_id)`).
4. Service does:
   - Loads / creates the user's session state from
     `app/data/sessions/<user_id>.json`.
   - Builds a prompt using templates in `prompts/listening_prompts.py`.
   - Calls **OpenAI** to generate a lesson passage.
   - Calls **edge-tts** to convert the passage to MP3, saved into
     `app/features/listening/audio/<hash>.mp3` and served via
     `/audio/<filename>` (registered in `line_api.py`).
5. Service returns a **reply payload** (`TextSendMessage`,
   `AudioSendMessage`, optional `QuickReply` buttons).
6. `line_api.py` calls `line_bot_api.reply_message(reply_token, payload)`.
7. LINE delivers the reply back to the user; audio streams from the Flask
   server's static URL.

For **plain text messages** (free conversation): step 3 skips postback
matching and instead routes to `ConversationService`, which maintains a
short rolling chat history per user and feeds it to OpenAI as a
`messages=[...]` list.

---

## Tech Stack

| Layer | Choice | Why |
|---|---|---|
| Language | Python 3.10+ | matches LINE SDK & OpenAI SDK requirements |
| Web framework | **Flask** | minimal, easy to expose a single `/callback` |
| Messaging | **line-bot-sdk** | official LINE Messaging API SDK |
| LLM | **OpenAI Chat Completions** | conversation + lesson generation |
| TTS | **edge-tts** | free Microsoft Edge voices, high-quality, no key |
| Audio meta | **mutagen** | MP3 metadata / duration reading |
| Config | **python-dotenv** | load `.env` at start-up |
| Tunnelling | **ngrok** | expose local `:5000` to LINE for dev |
| Deploy | any WSGI host — Render / Railway / Heroku / etc. |

`requirements.txt` (main):

```
python-dotenv
flask
line-bot-sdk
openai
edge-tts
mutagen
requests
```

---

## Requirements

- **Python 3.10+** (3.11 tested)
- A **LINE Messaging API channel** (create at
  https://developers.line.biz/console/)
- **OpenAI API key** with access to `gpt-3.5-turbo` or newer
- **ngrok** binary in the bot folder (`ngrok.exe` on Windows) for local dev
- ~100 MB of free disk for cached MP3 audio (grows over time)

---

## Configuration

Create a `.env` file in each bot's root (**never committed**):

```dotenv
# LINE Bot channel (from LINE Developers console)
LINE_CHANNEL_ID=xxxxxxxxxx
LINE_CHANNEL_SECRET=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
LINE_CHANNEL_ACCESS_TOKEN=xxxxxxxxxxxxxxxxxxxxxxxxxx...

# OpenAI
OPENAI_API_KEY=sk-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx

# Flask
SECRET_KEY=any-random-string
```

The app logs whether each of `LINE_CHANNEL_ID`, `LINE_CHANNEL_SECRET`,
`LINE_CHANNEL_ACCESS_TOKEN` are set (values are **not** printed), so you
can quickly confirm your `.env` is loaded on start-up.

---

## Running Locally

```bash
# 1. Enter one of the bot versions (main is recommended)
cd 論文/程式碼/line-english-bot

# 2. Set up a virtualenv & install deps
python -m venv venv
venv\Scripts\activate         # Windows
pip install -r requirements.txt

# 3. Prepare .env (see Configuration above)

# 4. Start Flask
python app.py                 # listens on http://localhost:5000

# 5. Expose the local server to LINE via ngrok (separate terminal)
ngrok http 5000

# 6. Copy the ngrok HTTPS URL into the LINE Developers console
#    → your channel → Messaging API → Webhook URL:
#         https://<random>.ngrok-free.app/callback
#    Also click "Verify" — you should see "Success".

# 7. Add the LINE bot as a friend from the QR code in the console
#    and start chatting.
```

First launch takes a few seconds while services are lazily imported to
avoid circular imports (see `init_services()` in `line_api.py`).

---

## Deployment Notes

For production hosting (Render / Railway / Heroku / any WSGI host):

1. Use `gunicorn` instead of `flask run`:
   ```
   gunicorn -w 2 -b 0.0.0.0:$PORT "app:create_app()"
   ```
2. Set env vars in the platform's dashboard (do **not** upload `.env`).
3. Set the Webhook URL in LINE Developers to your platform's HTTPS URL
   + `/callback`.
4. The `static/audio/` folder grows over time — either:
   - use a persistent disk / bucket (recommended for long-term
     deployments), or
   - clear old MP3s on a schedule.
5. `mutagen` and `edge-tts` are pure-Python, no native deps to worry about.

---

## What's Not in the Repo

To keep the repo lean and safe:

| Excluded | Why | Where to get it |
|---|---|---|
| `.env` | secrets | create your own — see Configuration |
| `*.exe` (ngrok) | binary, per-OS | https://ngrok.com/download |
| `*.pdf` / `*.docx` / `*.pptx` | thesis paperwork, not code | kept locally |
| `*.MTS` / `*.mp4` | large demo videos | kept locally |

> **Security note:** the `.env` files were briefly tracked in an early
> commit and later removed via `git rm --cached`. If you ever committed
> real credentials from this fork, **rotate them** — the values still
> exist in git history until history is rewritten.

---

## License & Citation

Educational / non-commercial use. If you build on this code for research,
please cite the thesis:

> Elaine Du. *LINE Bot 結合大型語言模型之英語學習系統設計與實作* (Design
> and Implementation of an English-Learning System Combining a LINE Bot
> with a Large Language Model). Master's thesis, [Your University],
> [Year].
