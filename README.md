# LINE English-Learning Bot (LLM-Powered)

An interactive English-learning LINE chatbot backed by a large language model.
Users chat with the bot in Chinese/English; the bot responds with lesson content,
pronunciation audio, and conversational practice.

> Code artefact of the master's thesis:
> *"LINE Bot 結合大型語言模型之英語學習系統設計與實作"*
> (Design and Implementation of an English-Learning System Combining a LINE Bot with a Large Language Model).

## Features

- Free-form English conversation practice with an LLM back end
- Pre-generated MP3 pronunciation audio for lesson vocabulary
- LINE Messaging API integration (webhooks + rich messages)
- Multiple bot iterations kept side-by-side for comparison:
  - `programming/line-english-bot/` — main version
  - `programming/line-english-bot - copy/` — experimental branch
  - `programming/backup-line-english-bot/` — earlier stable snapshot
  - `teaching-version/line-english-bot/` — classroom-oriented cut

## Repository Layout

```
line-english-bot-llm-thesis/
├── 論文/                       # thesis-related code (translated: "thesis")
│   ├── 程式碼/                 # code (translated: "source code")
│   │   ├── line-english-bot/
│   │   ├── line-english-bot - 複製/
│   │   └── 備份line-english-bot/
│   └── 教學版本/               # teaching version
│       └── line-english-bot/
└── (Chinese folder names preserved from original project layout)
```

## Tech Stack

- **Python 3** with Flask (LINE webhook server)
- **LINE Messaging API SDK** (`line-bot-sdk`)
- **Large Language Model** for open-ended conversation (OpenAI / other API)
- **ngrok** for local webhook tunnelling during development
- **MP3 audio** pre-generated per vocabulary item

## Requirements

Each bot subfolder has its own `requirements.txt`. Typical install:

```bash
cd 論文/程式碼/line-english-bot
pip install -r requirements.txt
```

## Configuration

Create a `.env` file in each bot's root (**not committed to git**) with:

```
LINE_CHANNEL_ACCESS_TOKEN=your_line_bot_token
LINE_CHANNEL_SECRET=your_line_channel_secret
OPENAI_API_KEY=your_openai_key
# ...other keys as required by app.py
```

## Running Locally

```bash
# 1. Start the Flask webhook server
python app.py

# 2. Expose it publicly via ngrok
./ngrok http 5000

# 3. Paste the ngrok HTTPS URL into the LINE Developers console
#    as the Webhook URL for your Messaging API channel.
```

## What's Not in the Repo

To keep the repo lean and safe, the following are excluded via `.gitignore`:

- `.env` — secrets / API keys (rotate if ever accidentally leaked)
- `*.exe` — ngrok and other binaries; download separately
- Presentation slides, PDFs, DOCX of the thesis itself (kept locally)
- `.MTS` and other large video files

## Academic Context

This repository holds only the **code artefact** of the thesis. Papers, slides,
supervisor letters, defence forms, and other academic paperwork are kept
outside git.

## License

Educational / non-commercial. Original research work — please cite the thesis
if you build on this code.
