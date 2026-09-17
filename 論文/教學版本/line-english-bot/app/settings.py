import os
from pathlib import Path

# 專案路徑設定
BASE_DIR = Path(__file__).resolve().parent
AUDIO_FOLDER = BASE_DIR / 'features' / 'conversation' / 'audio'

# 確保音檔目錄存在
AUDIO_FOLDER.mkdir(parents=True, exist_ok=True)

# 外部訪問 URL 設定
TUNNEL_URL = os.getenv('TUNNEL_URL', '').rstrip('/')
NGROK_URL = os.getenv('NGROK_URL', '').rstrip('/')

# 使用 TUNNEL_URL 優先，否則使用 NGROK_URL
WEBHOOK_URL = TUNNEL_URL or NGROK_URL

# API 金鑰設定
LINE_CHANNEL_ACCESS_TOKEN = os.getenv('LINE_CHANNEL_ACCESS_TOKEN')
LINE_CHANNEL_SECRET = os.getenv('LINE_CHANNEL_SECRET')
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')