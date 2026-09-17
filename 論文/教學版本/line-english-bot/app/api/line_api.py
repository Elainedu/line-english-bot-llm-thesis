import os
import tempfile
import traceback
from flask import request, abort, send_from_directory, Blueprint
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import (
    MessageEvent, TextMessage, AudioMessage, TextSendMessage,
    QuickReplyButton, QuickReply, MessageAction, PostbackEvent, PostbackAction
)

# 創建藍圖
line_bp = Blueprint('line', __name__)

# 音頻目錄設置
basedir = os.path.abspath(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
STATIC_AUDIO_FOLDER = os.path.join(basedir, 'app', 'static', 'audio')

# 初始化 LINE Bot
line_bot_api = LineBotApi(os.getenv('LINE_CHANNEL_ACCESS_TOKEN'))
handler = WebhookHandler(os.getenv('LINE_CHANNEL_SECRET'))

# 全局服務變數 - 只保留對話和跟讀
conversation_service = None
shadowing_service = None

def init_services():
    """初始化服務 - 教學版本（僅對話+跟讀）"""
    global conversation_service, shadowing_service
    
    # 初始化對話服務
    try:
        from app.features.conversation.service import ConversationService
        conversation_service = ConversationService(line_bot_api, handler)
        print("✅ 對話服務初始化成功")
    except Exception as e:
        print(f"❌ 對話服務初始化失敗: {str(e)}")
        # 使用簡單的備用服務
        conversation_service = create_dummy_conversation_service()
        
    # 初始化跟讀服務
    try:
        from app.features.shadowing.service import ShadowingService
        shadowing_service = ShadowingService(line_bot_api, audio_folder=STATIC_AUDIO_FOLDER)
        print("✅ 跟讀服務初始化成功")
    except Exception as e:
        print(f"❌ 跟讀服務初始化失敗: {str(e)}")
        # 使用簡單的備用服務
        shadowing_service = create_dummy_shadowing_service()

def create_dummy_conversation_service():
    """創建備用對話服務"""
    class DummyConversationService:
        def __init__(self):
            self.user_sessions = {}
        
        def handle_text_message(self, event):
            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(text="對話服務暫時不可用，請稍後再試。")
            )
        
        def handle_audio_message(self, user_id, audio_file_path, event=None):
            return TextSendMessage(text="語音功能暫時不可用。")
    
    return DummyConversationService()

def create_dummy_shadowing_service():
    """創建備用跟讀服務"""
    class DummyShadowingService:
        def __init__(self):
            self.audio_folder = STATIC_AUDIO_FOLDER
        
        def start_shadowing_session(self, user_id, difficulty):
            return TextSendMessage(text="跟讀練習暫時不可用，請稍後再試。")
        
        def evaluate_shadowing(self, user_id, audio_file_path):
            return TextSendMessage(text="跟讀評估暫時不可用。")
    
    return DummyShadowingService()

def send_main_menu(reply_token):
    """發送主選單 - 只有對話和跟讀"""
    items = [
        QuickReplyButton(action=MessageAction(label="對話練習", text="#start_conversation")),
        QuickReplyButton(action=PostbackAction(label="跟讀練習", data="action=shadowing"))
    ]
    
    message = TextSendMessage(
        text="🎯 英語學習練習 - 教學版\n\n請選擇功能：",
        quick_reply=QuickReply(items=items)
    )
    
    line_bot_api.reply_message(reply_token, message)

def clear_user_state(user_id, keep_activity=None):
    """清理用戶狀態"""
    # 清理對話狀態
    if hasattr(conversation_service, 'user_sessions') and user_id in conversation_service.user_sessions:
        if keep_activity != 'conversation':
            del conversation_service.user_sessions[user_id]
    
    # 清理跟讀狀態
    try:
        from app.features.shadowing.service import UserSession
        if keep_activity != 'shadowing':
            UserSession.delete(user_id)
    except:
        pass

@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    """處理文字訊息 - 教學版本"""
    try:
        text = event.message.text.strip()
        user_id = event.source.user_id
        
        # 處理命令
        if text.startswith('#') or text in ["選單", "menu"]:
            if text == "#start_conversation":
                clear_user_state(user_id, 'conversation')
                conversation_service.handle_text_message(event)
                return
            elif text in ["#menu", "選單", "menu"]:
                clear_user_state(user_id)
                send_main_menu(event.reply_token)
                return
            elif text.startswith('#topic') or text.startswith('#level'):
                conversation_service.handle_text_message(event)
                return
            elif text == "#end_conversation":
                conversation_service.handle_text_message(event)
                return
        
        # 檢查用戶當前狀態
        if (hasattr(conversation_service, 'user_sessions') and 
            user_id in conversation_service.user_sessions):
            # 用戶在對話中
            conversation_service.handle_text_message(event)
            return
        
        # 檢查用戶是否在跟讀練習中
        try:
            from app.features.shadowing.service import UserSession
            user_session = UserSession.get_by_line_user_id(user_id)
            if user_session and user_session.session_type == "shadowing":
                shadowing_service.handle_text_message(event)
                return
        except:
            pass
        
        # 默認顯示主選單
        clear_user_state(user_id)
        send_main_menu(event.reply_token)
        
    except Exception as e:
        print(f"處理訊息錯誤: {str(e)}")
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text="處理您的要求時發生錯誤，請再試一次。")
        )

@handler.add(MessageEvent, message=AudioMessage)
def handle_audio_message(event):
    """處理音頻訊息 - 教學版本"""
    try:
        user_id = event.source.user_id
        
        # 獲取音頻內容並保存到臨時檔案
        message_content = line_bot_api.get_message_content(event.message.id)
        with tempfile.NamedTemporaryFile(delete=False, suffix='.m4a') as f:
            for chunk in message_content.iter_content():
                f.write(chunk)
            temp_file_path = f.name
        
        # 檢查用戶是否在跟讀練習中
        try:
            from app.features.shadowing.service import UserSession
            user_session = UserSession.get_by_line_user_id(user_id)
            
            if user_session and user_session.session_type == "shadowing":
                result_message = shadowing_service.evaluate_shadowing(user_id, temp_file_path)
                line_bot_api.reply_message(event.reply_token, result_message)
                os.unlink(temp_file_path)
                return
        except Exception as e:
            print(f"跟讀處理錯誤: {str(e)}")
        
        # 檢查用戶是否在對話中
        if (hasattr(conversation_service, 'user_sessions') and 
            user_id in conversation_service.user_sessions and
            conversation_service.user_sessions[user_id].get('state') == 'in_conversation'):
            
            if hasattr(conversation_service, 'handle_audio_message'):
                result_messages = conversation_service.handle_audio_message(user_id, temp_file_path, event)
                if result_messages:
                    if not isinstance(result_messages, list):
                        result_messages = [result_messages]
                    line_bot_api.reply_message(event.reply_token, result_messages)
                os.unlink(temp_file_path)
                return
        
        # 默認回應
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text="請先選擇功能再發送語音訊息。")
        )
        os.unlink(temp_file_path)
        
    except Exception as e:
        print(f"處理音頻錯誤: {str(e)}")
        try:
            if 'temp_file_path' in locals():
                os.unlink(temp_file_path)
        except:
            pass
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text="處理語音訊息時發生錯誤。")
        )

@handler.add(PostbackEvent)
def handle_postback(event):
    """處理 Postback 事件 - 教學版本"""
    try:
        data = event.postback.data
        user_id = event.source.user_id
        
        # 處理跟讀練習
        if data == 'action=shadowing':
            clear_user_state(user_id)
            items = [
                QuickReplyButton(action=PostbackAction(label="初級", data="shadowing_level=beginner")),
                QuickReplyButton(action=PostbackAction(label="中級", data="shadowing_level=intermediate")),
                QuickReplyButton(action=PostbackAction(label="高級", data="shadowing_level=advanced"))
            ]
            
            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(
                    text="請選擇跟讀練習難度：",
                    quick_reply=QuickReply(items=items)
                )
            )
            
        elif data.startswith('shadowing_level='):
            difficulty = data.split('=')[1]
            clear_user_state(user_id, 'shadowing')
            
            try:
                messages = shadowing_service.start_shadowing_session(user_id, difficulty)
                if not isinstance(messages, list):
                    messages = [messages]
                line_bot_api.reply_message(event.reply_token, messages)
            except Exception as e:
                print(f"啟動跟讀練習錯誤: {str(e)}")
                line_bot_api.reply_message(
                    event.reply_token,
                    TextSendMessage(text="啟動跟讀練習時發生錯誤。")
                )
        
        else:
            # 未知 postback，顯示主選單
            clear_user_state(user_id)
            send_main_menu(event.reply_token)
            
    except Exception as e:
        print(f"處理 Postback 錯誤: {str(e)}")
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text="處理您的要求時發生錯誤。")
        )

@line_bp.route("/callback", methods=['POST'])
def callback():
    """處理 LINE Webhook"""
    signature = request.headers['X-Line-Signature']
    body = request.get_data(as_text=True)
    
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)
    except Exception as e:
        print(f"Webhook 錯誤: {str(e)}")
        abort(500)
        
    return 'OK'

@line_bp.route('/static/audio/<filename>')
def serve_audio(filename):
    """提供音頻檔案"""
    try:
        # 檢查各個可能的音頻目錄
        audio_folders = [
            STATIC_AUDIO_FOLDER,
            getattr(conversation_service, 'audio_folder', None),
            getattr(conversation_service, 'static_audio_folder', None),
            getattr(shadowing_service, 'audio_folder', None)
        ]
        
        for folder in audio_folders:
            if folder and os.path.exists(os.path.join(folder, filename)):
                return send_from_directory(folder, filename, mimetype='audio/mpeg')
        
        return "Audio file not found", 404
        
    except Exception as e:
        print(f"音頻檔案服務錯誤: {str(e)}")
        return "Error serving audio file", 500

@line_bp.route('/test')
def test():
    """測試路由"""
    return '🎯 LINE Bot 教學版運行中 - 對話練習 + 跟讀練習'

def create_simple_rich_menu():
    """創建簡化的 Rich Menu - 只有對話和跟讀"""
    try:
        from linebot.models import RichMenu, RichMenuArea, RichMenuBounds, RichMenuSize
        
        # 簡化的 2 格選單
        rich_menu = RichMenu(
            size=RichMenuSize(width=2500, height=843),  # 高度減半
            selected=True,
            name="English Learning - Teaching Edition",
            chat_bar_text="學習選單",
            areas=[
                # 左半邊：對話練習
                RichMenuArea(
                    bounds=RichMenuBounds(x=0, y=0, width=1250, height=843),
                    action=MessageAction(label="對話練習", text="#start_conversation")
                ),
                # 右半邊：跟讀練習
                RichMenuArea(
                    bounds=RichMenuBounds(x=1250, y=0, width=1250, height=843),
                    action=PostbackAction(label="跟讀練習", data="action=shadowing")
                )
            ]
        )
        
        rich_menu_id = line_bot_api.create_rich_menu(rich_menu=rich_menu)
        line_bot_api.set_default_rich_menu(rich_menu_id)
        print(f"✅ 簡化選單創建成功: {rich_menu_id}")
        
    except Exception as e:
        print(f"創建 Rich Menu 錯誤: {str(e)}")

def setup_routes(app):
    """設置路由 - 教學版本"""
    try:
        # 註冊藍圖
        if line_bp.name not in [b.name for b in app.blueprints.values()]:
            app.register_blueprint(line_bp)
        
        # 初始化服務
        init_services()
        
        # 創建簡化選單
        create_simple_rich_menu()
        
        # 設置音頻目錄
        app.config['STATIC_AUDIO_FOLDER'] = STATIC_AUDIO_FOLDER
        os.makedirs(STATIC_AUDIO_FOLDER, exist_ok=True)
        
        print("✅ 教學版路由設置完成")
        return app
        
    except Exception as e:
        print(f"設置路由錯誤: {str(e)}")
        return app