from flask import Flask
from dotenv import load_dotenv

def create_app():
    # 載入環境變數
    load_dotenv()
    
    # 創建 Flask 應用
    app = Flask(__name__)
    
    # 設置路由
    from app.api.line_api import setup_routes
    app = setup_routes(app)
    
    # 基本路由
    @app.route('/')
    def home():
        return 'LINE Bot Server Running'
    
    return app