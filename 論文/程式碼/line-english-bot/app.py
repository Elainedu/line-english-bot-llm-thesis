import os
import logging
from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from app.api.line_api import line_bp, handler, setup_routes

# 設置日誌
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def create_app():
    """創建並配置應用"""
    try:
        # 創建 Flask 應用實例
        app = Flask(__name__)
        
        # 設置應用配置
        app.config.from_mapping(
            SECRET_KEY=os.environ.get('SECRET_KEY', 'dev'),
        )
        
        # 設定靜態資源路徑
        app.static_folder = 'static'
        
        # 輸出環境變數檢查（不包含敏感資訊）
        logger.info("檢查關鍵環境變數:")
        logger.info(f"LINE_CHANNEL_ID 已設置: {'LINE_CHANNEL_ID' in os.environ}")
        logger.info(f"LINE_CHANNEL_SECRET 已設置: {'LINE_CHANNEL_SECRET' in os.environ}")
        logger.info(f"LINE_CHANNEL_ACCESS_TOKEN 已設置: {'LINE_CHANNEL_ACCESS_TOKEN' in os.environ}")
        
        # 在主應用中直接添加 /callback 路由
        @app.route("/callback", methods=['POST'])
        def callback():
            """主應用中直接處理 LINE Webhook"""
            logger.info("\n====== 主應用 Webhook 處理開始 ======")
            
            signature = request.headers.get('X-Line-Signature', '')
            body = request.get_data(as_text=True)
            logger.info(f"收到 webhook 請求：{body}")
            
            try:
                handler.handle(body, signature)
            except InvalidSignatureError:
                logger.error("無效的簽名")
                abort(400)
            except Exception as e:
                logger.error(f"處理 webhook 時發生錯誤：{str(e)}")
                abort(500)
            finally:
                logger.info("====== 主應用 Webhook 處理結束 ======\n")
                
            return 'OK'
        
        # 設置路由和初始化 LINE Bot
        app = setup_routes(app)
        
        # 添加一個簡單的測試路由
        @app.route('/test')
        def test():
            return 'LINE Bot 主應用測試路由正常運行！'
        
        # 添加一個路由檢查路由
        @app.route('/routes')
        def list_routes():
            routes = []
            for rule in app.url_map.iter_rules():
                routes.append({
                    "endpoint": rule.endpoint,
                    "methods": list(rule.methods),
                    "rule": str(rule)
                })
            return {"routes": routes}
        
        logger.info("應用創建成功")
        return app
    except Exception as e:
        logger.error(f"創建應用時發生錯誤: {str(e)}", exc_info=True)
        # 即使出錯，也返回一個基本應用
        app = Flask(__name__)
        return app

# 當文件直接運行時
if __name__ == '__main__':
    app = create_app()
    
    # 獲取端口設置，默認為 5000
    port = int(os.environ.get('PORT', 5000))
    
    # 決定是否使用調試模式
    debug_mode = os.environ.get('FLASK_ENV', 'development') == 'development'
    
    logger.info(f"應用啟動於端口 {port}，調試模式: {debug_mode}")
    app.run(host='0.0.0.0', port=port, debug=debug_mode)