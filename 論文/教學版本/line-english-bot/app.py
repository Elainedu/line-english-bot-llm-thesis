import os
import logging
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

from flask import Flask, request, abort, send_from_directory
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from app.api.line_api import line_bp, handler, setup_routes

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def create_app():
    """創建 Flask 應用"""
    try:
        app = Flask(__name__)
        app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev')
        app.static_folder = 'static'
        
        # 檢查環境變數
        required_vars = ['LINE_CHANNEL_ACCESS_TOKEN', 'LINE_CHANNEL_SECRET', 'OPENAI_API_KEY']
        missing_vars = [var for var in required_vars if not os.getenv(var)]
        
        if missing_vars:
            raise ValueError(f"缺少環境變數: {missing_vars}")
        
        # LINE Webhook
        @app.route("/callback", methods=['POST'])
        def callback():
            signature = request.headers.get('X-Line-Signature', '')
            body = request.get_data(as_text=True)
            
            try:
                handler.handle(body, signature)
            except InvalidSignatureError:
                abort(400)
            except Exception as e:
                logger.error(f"處理錯誤: {e}")
                abort(500)
                
            return 'OK'
        
        # 健康檢查
        @app.route('/health')
        def health():
            return {'status': 'ok'}
        
        # 對話練習音檔
        @app.route('/static/conversation_audio/<filename>')
        def serve_conversation_audio(filename):
            audio_dir = os.path.join(app.root_path, 'features', 'conversation', 'audio')
            return send_from_directory(audio_dir, filename)
        
        # 跟讀練習音檔
        @app.route('/static/shadowing_audio/<filename>')
        def serve_shadowing_audio(filename):
            audio_dir = os.path.join(app.root_path, 'features', 'shadowing', 'audio')
            return send_from_directory(audio_dir, filename)
        
        # 基本路由
        @app.route('/')
        def home():
            return 'LINE Bot Running'
        
        app = setup_routes(app)
        return app
        
    except Exception as e:
        logger.error(f"創建應用失敗: {e}")
        return Flask(__name__)

if __name__ == '__main__':
    try:
        app = create_app()
        port = int(os.environ.get('PORT', 5000))
        debug = os.environ.get('FLASK_ENV') == 'development'
        
        print(f"啟動於: http://localhost:{port}")
        app.run(host='0.0.0.0', port=port, debug=debug)
        
    except Exception as e:
        logger.error(f"啟動失敗: {e}")