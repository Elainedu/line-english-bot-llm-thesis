from flask import Flask
from dotenv import load_dotenv
import os

def create_app():
    print("Creating Flask app...")
    app = Flask(__name__)
    
    # Load environment variables
    load_dotenv(override=True)
    
    # Check required environment variables
    required_env = [
        'LINE_CHANNEL_ACCESS_TOKEN',
        'LINE_CHANNEL_SECRET',
        'OPENAI_API_KEY',
        'NGROK_URL'
    ]
    
    for env in required_env:
        if not os.getenv(env):
            raise ValueError(f"Missing required environment variable: {env}")
    
    # 解決循環導入問題：延遲導入 setup_routes
    with app.app_context():
        from app.api.line_api import setup_routes
        print("Setting up routes...")
        app = setup_routes(app)
    
    @app.route('/')
    def home():
        return 'LINE Bot Server is running!'
    
    print("App creation complete")
    return app