from flask import Flask
from dotenv import load_dotenv
from app.api.line_api import setup_routes
import os
import logging

def configure_logging():
    """Configure logging settings"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s [%(levelname)s] %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

def check_environment_variables():
    """Check and validate required environment variables"""
    required_env = [
        'LINE_CHANNEL_ACCESS_TOKEN',
        'LINE_CHANNEL_SECRET',
        'OPENAI_API_KEY',
        'NGROK_URL'
    ]
    
    missing_vars = []
    for env in required_env:
        if not os.getenv(env):
            missing_vars.append(env)
    
    if missing_vars:
        raise ValueError(f"Missing required environment variables: {', '.join(missing_vars)}")

def create_directories():
    """Create necessary directories if they don't exist"""
    directories = [
        'app/static',
        'app/static/audio',
        'app/features/listening/audio',  # 新增聽力訓練的音頻目錄
    ]
    
    for directory in directories:
        if not os.path.exists(directory):
            os.makedirs(directory)
            logging.info(f"Created directory: {directory}")

def create_app():
    """Initialize Flask application"""
    try:
        print("Creating Flask app...")
        app = Flask(__name__)
        
        # 配置日誌
        configure_logging()
        logging.info("Logging configured")
        
        # 載入環境變數
        logging.info("Loading environment variables...")
        load_dotenv(override=True)
        
        # 檢查環境變數
        logging.info("Checking environment variables...")
        check_environment_variables()
        
        # 創建必要的目錄
        logging.info("Creating necessary directories...")
        create_directories()
        
        # 設置路由
        logging.info("Setting up routes...")
        app = setup_routes(app)
        
        @app.route("/")
        def home():
            return 'LINE Bot is running!'
        
        logging.info("App creation complete")
        return app
        
    except Exception as e:
        logging.error(f"Error during app creation: {str(e)}")
        raise

def init_app():
    """Application factory function"""
    try:
        app = create_app()
        logging.info("Application initialized successfully")
        return app
    except Exception as e:
        logging.critical(f"Failed to initialize application: {str(e)}")
        raise