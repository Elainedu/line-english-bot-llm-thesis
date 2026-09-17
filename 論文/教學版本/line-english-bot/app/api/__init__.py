from flask import Flask
from dotenv import load_dotenv
from app.api.line_api import setup_routes
import os
import logging

def create_app():
    """初始化 Flask 應用 - 教學版本（僅對話+跟讀功能）"""
    
    # 基本日誌設定
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s [%(levelname)s] %(message)s'
    )
    
    # 載入環境變數
    load_dotenv(override=True)
    
    # 檢查必要環境變數
    required_vars = [
        'LINE_CHANNEL_ACCESS_TOKEN',
        'LINE_CHANNEL_SECRET', 
        'OPENAI_API_KEY'
    ]
    
    missing = [var for var in required_vars if not os.getenv(var)]
    if missing:
        raise ValueError(f"缺少環境變數: {', '.join(missing)}")
    
    # 創建必要目錄（只保留對話和跟讀需要的）
    directories = [
        'app/static/audio',                    # 對話語音文件
        'app/features/conversation/audio',     # 對話練習音頻  
        'app/features/shadowing/audio'         # 跟讀練習音頻
    ]
    
    for directory in directories:
        os.makedirs(directory, exist_ok=True)
    
    # 創建 Flask 應用
    app = Flask(__name__)
    
    # 基本路由
    @app.route("/")
    def home():
        return 'LINE Bot 教學版 - 對話練習 + 跟讀練習'
    
    # 設置 LINE Bot 路由
    app = setup_routes(app)
    
    logging.info("✅ 教學版應用初始化完成")
    return app