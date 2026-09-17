# settings.py
import os
from pathlib import Path

# 專案根目錄
BASE_DIR = Path(__file__).resolve().parent

# 音訊檔案存放路徑
AUDIO_FOLDER = os.path.join(BASE_DIR, 'features', 'conversation', 'audio')

# 確保必要的目錄存在
os.makedirs(AUDIO_FOLDER, exist_ok=True)

# NGROK URL 設定（必須以 https:// 開頭）
NGROK_URL = os.getenv('NGROK_URL', '').rstrip('/')
if NGROK_URL and not NGROK_URL.startswith('https://'):
    raise ValueError("NGROK_URL must start with https://")

# LINE Bot 設定
LINE_CHANNEL_ACCESS_TOKEN = os.getenv('LINE_CHANNEL_ACCESS_TOKEN')
LINE_CHANNEL_SECRET = os.getenv('LINE_CHANNEL_SECRET')

# OpenAI 設定
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')