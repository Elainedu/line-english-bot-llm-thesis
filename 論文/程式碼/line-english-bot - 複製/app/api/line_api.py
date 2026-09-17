import os
import json
import traceback
import requests
import time
import random  # 新增：process_topic_fallback 需要使用
import tempfile
import logging
from datetime import datetime
from flask import request, abort, send_from_directory, Blueprint
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import (
    MessageEvent, TextMessage, AudioMessage, TextSendMessage,
    QuickReplyButton, QuickReply, MessageAction, PostbackEvent, PostbackAction,
    RichMenu, RichMenuArea, RichMenuBounds, RichMenuSize, URIAction,
    AudioSendMessage
)
from PIL import Image
import io

# 創建藍圖
line_bp = Blueprint('line', __name__)

# 獲取應用根目錄
basedir = os.path.abspath(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

# 定義統一的音頻文件目錄
STATIC_AUDIO_FOLDER = os.path.join(basedir, 'static', 'audio')
APP_STATIC_AUDIO_FOLDER = os.path.join(basedir, 'app', 'static', 'audio')

# 確保目錄存在
os.makedirs(STATIC_AUDIO_FOLDER, exist_ok=True)
os.makedirs(APP_STATIC_AUDIO_FOLDER, exist_ok=True)

# LINE Bot 初始化
try:
    line_bot_api = LineBotApi(os.getenv('LINE_CHANNEL_ACCESS_TOKEN'))
    handler = WebhookHandler(os.getenv('LINE_CHANNEL_SECRET'))
    logging.info("LINE Bot API 初始化成功")
except Exception as e:
    logging.error(f"LINE Bot API 初始化失敗: {str(e)}")
    raise

# 全局服務變數
conversation_service = None
vocabulary_service = None
shadowing_service = None
listening_service = None

def init_services():
    # 初始化服務
    global conversation_service, vocabulary_service, shadowing_service, listening_service
    
    try:
        # 對話服務
        try:
            from app.features.conversation.service import ConversationService
            logging.info("正在初始化對話服務...")
            conversation_service = ConversationService(line_bot_api, handler)
            
            if hasattr(conversation_service, 'handle_text_message'):
                logging.info("對話服務初始化成功")
            else:
                raise AttributeError("對話服務缺少必要的方法")
                    
        except (ImportError, AttributeError) as e:
            logging.error(f"對話服務初始化失敗: {str(e)}")
            conversation_service = create_dummy_conversation_service()
            logging.info("使用替代對話服務")
        
        # 詞彙服務
        try:
            from app.features.voc.service import VocabularyService
            vocabulary_service = VocabularyService(line_bot_api)
            logging.info("詞彙服務初始化成功")
        except Exception as e:
            logging.error(f"詞彙服務初始化失敗: {str(e)}")
            vocabulary_service = create_dummy_vocabulary_service()
            logging.info("使用替代詞彙服務")
        
        # 跟讀練習服務
        try:
            from app.features.shadowing.service import ShadowingService
            import inspect
            shadowing_params = inspect.signature(ShadowingService.__init__).parameters
            
            if 'audio_folder' in shadowing_params:
                shadowing_service = ShadowingService(line_bot_api, audio_folder=STATIC_AUDIO_FOLDER)
            else:
                shadowing_service = ShadowingService(line_bot_api)
                shadowing_service.audio_folder = STATIC_AUDIO_FOLDER
                
            logging.info("跟讀練習服務初始化成功")
        except Exception as e:
            logging.error(f"跟讀練習服務初始化失敗: {str(e)}")
            shadowing_service = create_dummy_shadowing_service()
            logging.info("使用替代跟讀練習服務")
        
        # 聽力訓練服務
        try:
            from app.features.listening.service import ListeningService
            import inspect
            listening_params = inspect.signature(ListeningService.__init__).parameters
            
            if 'audio_folder' in listening_params:
                listening_service = ListeningService(line_bot_api, audio_folder=STATIC_AUDIO_FOLDER)
            else:
                listening_service = ListeningService(line_bot_api)
                listening_service.audio_folder = STATIC_AUDIO_FOLDER
                
            logging.info("聽力訓練服務初始化成功")
        except Exception as e:
            logging.error(f"聽力訓練服務初始化失敗: {str(e)}")
            listening_service = create_dummy_listening_service()
            logging.info("使用替代聽力訓練服務")
        
        logging.info("所有服務初始化完成")
        
    except Exception as e:
        logging.error(f"服務初始化過程中發生錯誤: {str(e)}")
        traceback.print_exc()

# 創建替代服務的輔助函數
def create_dummy_conversation_service():
    # 創建基本的對話服務替代品
    class DummyConversationService:
        def __init__(self):
            self.user_sessions = {}
            self.audio_folder = STATIC_AUDIO_FOLDER
            self.static_audio_folder = os.path.join(basedir, 'app', 'features', 'conversation', 'audio')
        
        def handle_text_message(self, event):
            topics = ["自我介紹", "旅遊", "餐廳點餐", "購物", "問路"]
            line_bot_api.reply_message(
                event.reply_token,
                [
                    TextSendMessage(text="請選擇您想練習的對話主題："),
                    TextSendMessage(
                        text="對話主題",
                        quick_reply=QuickReply(items=[
                            QuickReplyButton(action=MessageAction(label=topic, text=f"#topic {topic}"))
                            for topic in topics
                        ])
                    )
                ]
            )
        
        def handle_audio_message(self, user_id, audio_file_path, event=None):
            return TextSendMessage(text="目前對話練習暫不支援語音輸入，請使用文字訊息。")
        
        def set_topic(self, user_id, topic, reply_token):
            if topic == "自我介紹":
                self.user_sessions[user_id] = {
                    'state': 'in_conversation',
                    'topic': 'self_intro',
                    'history': [],
                    'difficulty': 'intermediate'
                }
                
                messages = [
                    TextSendMessage(text="主題已設置為: 👋 自我介紹\n難度: Intermediate\n\n請開始您的對話練習!"),
                    TextSendMessage(text="Hi there! I'm your conversation partner today. Can you tell me a little bit about yourself?"),
                    TextSendMessage(
                        text="提示: 您可以用文字回覆。隨時輸入 #end_conversation 結束對話。",
                        quick_reply=QuickReply(items=[
                            QuickReplyButton(action=MessageAction(label="結束對話", text="#end_conversation")),
                            QuickReplyButton(action=MessageAction(label="更換主題", text="#start_conversation"))
                        ])
                    )
                ]
                line_bot_api.reply_message(reply_token, messages)
                return "handled"
            else:
                line_bot_api.reply_message(
                    reply_token,
                    TextSendMessage(text=f"主題 '{topic}' 暫時不可用，請選擇其他主題。")
                )
                return "handled"
    
    return DummyConversationService()

def create_dummy_vocabulary_service():
    # 創建基本的詞彙服務替代品
    class DummyVocabularyService:
        def __init__(self):
            self.user_sessions = {}
            
        def handle_text_message(self, event):
            words = ["apple", "book", "computer", "dog", "education"]
            line_bot_api.reply_message(
                event.reply_token,
                [
                    TextSendMessage(text="請選擇一個單字練習造句："),
                    TextSendMessage(
                        text="單字選擇",
                        quick_reply=QuickReply(items=[
                            QuickReplyButton(action=MessageAction(label=word, text=f"#vocab {word}"))
                            for word in words
                        ])
                    )
                ]
            )
    
    return DummyVocabularyService()

def create_dummy_shadowing_service():
    # 創建基本的跟讀練習服務替代品
    class DummyShadowingService:
        def __init__(self):
            self.audio_folder = STATIC_AUDIO_FOLDER
            self.static_audio_folder = os.path.join(basedir, 'app', 'features', 'shadowing', 'audio')
            
        def handle_text_message(self, event):
            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(text="跟讀練習服務暫時不可用，請稍後再試。")
            )
        
        def start_shadowing_session(self, user_id, difficulty):
            return TextSendMessage(text="跟讀練習準備中... 請選擇其他功能或稍後再試。")
        
        def evaluate_shadowing(self, user_id, audio_file_path):
            return TextSendMessage(text="跟讀練習評估服務暫時不可用，請稍後再試。")
    
    return DummyShadowingService()

def create_dummy_listening_service():
    # 創建基本的聽力訓練服務替代品
    class DummyListeningService:
        def __init__(self):
            self.audio_folder = STATIC_AUDIO_FOLDER
            self.static_audio_folder = os.path.join(basedir, 'app', 'features', 'listening', 'audio')
            self.user_sessions = {}
            
        def handle_text_message(self, event):
            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(text="聽力訓練服務暫時不可用，請稍後再試。")
            )
        
        def start_listening_session(self, user_id, difficulty):
            return TextSendMessage(text="聽力訓練準備中... 請選擇其他功能或稍後再試。")
        
        def evaluate_listening(self, user_id, audio_file_path):
            return TextSendMessage(text="聽力訓練評估服務暫時不可用，請稍後再試。")
        
        def get_user_session(self, user_id):
            return None
    
    return DummyListeningService()

def diagnose_conversation_service():
    # 診斷 ConversationService 加載問題
    try:
        logging.info("===== 開始診斷 ConversationService =====")
        
        import importlib
        conversation_module = importlib.import_module('app.features.conversation.service')
        logging.info("成功導入模組: app.features.conversation.service")
        
        if hasattr(conversation_module, 'ConversationService'):
            logging.info("模組中存在 ConversationService 類")
            
            import inspect
            init_params = inspect.signature(conversation_module.ConversationService.__init__).parameters
            logging.info(f"ConversationService.__init__ 參數: {list(init_params.keys())}")
            
            try:
                prompts_module = importlib.import_module('app.features.conversation.prompts.menu_prompts')
                logging.info("成功導入提示模組")
                
                if hasattr(prompts_module, 'MAIN_TOPICS'):
                    logging.info(f"提示模組中存在 MAIN_TOPICS，包含 {len(prompts_module.MAIN_TOPICS)} 個主題")
                else:
                    logging.error("提示模組中缺少 MAIN_TOPICS 定義")
                    
            except Exception as prompts_err:
                logging.error(f"導入提示模組時出錯: {str(prompts_err)}")
        else:
            logging.error("模組中不存在 ConversationService 類")
            
        logging.info("===== ConversationService 診斷結束 =====")
    except Exception as e:
        logging.error(f"診斷過程中發生錯誤: {str(e)}")
        traceback.print_exc()

def reset_and_create_rich_menu():
    # 刪除所有現有的 Rich Menu 並創建新的
    try:
        rich_menu_list = line_bot_api.get_rich_menu_list()
        
        for rich_menu in rich_menu_list:
            try:
                line_bot_api.delete_rich_menu(rich_menu.rich_menu_id)
                logging.info(f"已刪除選單 ID: {rich_menu.rich_menu_id}")
                time.sleep(0.5)
            except Exception as e:
                logging.error(f"刪除選單 {rich_menu.rich_menu_id} 時發生錯誤: {str(e)}")
        
        logging.info("已刪除所有現有選單")
        time.sleep(1)
        
        new_rich_menu_id = create_rich_menu(line_bot_api)
        logging.info(f"已創建新選單，ID: {new_rich_menu_id}")
        
        return new_rich_menu_id
    except Exception as e:
        logging.error(f"重置 Rich Menu 時發生錯誤: {str(e)}")
        traceback.print_exc()
        return None

def send_menu_message(reply_token):
    # 發送主選單訊息
    try:
        items = [
            QuickReplyButton(action=MessageAction(label="對話練習", text="#start_conversation")),
            QuickReplyButton(action=MessageAction(label="詞彙練習", text="#start_vocabulary")),
            QuickReplyButton(action=PostbackAction(label="跟讀練習", data="action=shadowing")),
            QuickReplyButton(action=PostbackAction(label="聽力訓練", data="action=listening"))
        ]
        
        message = TextSendMessage(
            text="請選擇學習功能",
            quick_reply=QuickReply(items=items)
        )
        
        line_bot_api.reply_message(reply_token, message)
        logging.info("主選單訊息發送成功")
    except Exception as e:
        logging.error(f"發送主選單訊息失敗：{str(e)}")
        send_error_message(reply_token)

def send_error_message(reply_token):
    # 發送錯誤訊息
    try:
        line_bot_api.reply_message(
            reply_token,
            TextSendMessage(text="抱歉，處理您的要求時發生錯誤。請再試一次。")
        )
        logging.info("錯誤訊息發送成功")
    except Exception as e:
        logging.error(f"發送錯誤訊息失敗：{str(e)}")

@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    # 處理文字訊息的主要邏輯
    try:
        text = event.message.text.strip()
        user_id = event.source.user_id
        logging.info(f"收到用戶訊息：{text} (用戶ID：{user_id})")
        
        # 處理命令前先清理用戶狀態
        if text.startswith('#') or text in ["選單", "返回主選單"] or text.lower() == "menu":
            logging.info("檢測到命令或選單請求，清理用戶狀態")
            
            if text == "#end_conversation":
                if hasattr(conversation_service, 'user_sessions') and user_id in conversation_service.user_sessions:
                    conversation_service.handle_text_message(event)
                    return
            
            clear_user_state(user_id)
        
        # 處理難度設置命令
        if text.startswith('#level'):
            conversation_service.handle_text_message(event)
            return

        # 處理跟讀練習相關命令
        elif text.startswith('#shadowing') or text == "跟讀練習":
            clear_user_state(user_id, 'shadowing')
            
            items = [
                QuickReplyButton(action=PostbackAction(label="初級", data="shadowing_level=beginner")),
                QuickReplyButton(action=PostbackAction(label="中級", data="shadowing_level=intermediate")),
                QuickReplyButton(action=PostbackAction(label="高級", data="shadowing_level=advanced"))
            ]
            
            quick_reply = TextSendMessage(
                text="請選擇跟讀練習的難易度：",
                quick_reply=QuickReply(items=items)
            )
            line_bot_api.reply_message(event.reply_token, quick_reply)
            return
           
        # 處理聽力訓練相關命令
        elif text.startswith('#listening') or text == "聽力訓練":
            clear_user_state(user_id, 'listening')
            
            items = [
                QuickReplyButton(action=PostbackAction(label="初級", data="listening_level=beginner")),
                QuickReplyButton(action=PostbackAction(label="中級", data="listening_level=intermediate")),
                QuickReplyButton(action=PostbackAction(label="高級", data="listening_level=advanced"))
            ]
            
            quick_reply = TextSendMessage(
                text="請選擇聽力訓練的難易度：",
                quick_reply=QuickReply(items=items)
            )
            line_bot_api.reply_message(event.reply_token, quick_reply)
            return
           
        # 檢查對話相關指令
        elif text.startswith('#start_conversation'):
            clear_user_state(user_id, 'conversation')
            conversation_service.handle_text_message(event)
            return
           
        # 處理主題設置
        elif text.startswith('#topic'):
            topic_text = text[7:].strip()
            
            if not topic_text:
                conversation_service.start_conversation(user_id, event.reply_token)
                return
            
            try:
                conversation_service.set_topic(user_id, topic_text, event.reply_token)
            except Exception as e:
                logging.error(f"設置主題時發生錯誤: {str(e)}")
                send_error_message(event.reply_token)
            
            return
           
        elif text.startswith('#start_vocabulary') or text.startswith('#vocab'):
            clear_user_state(user_id, 'vocabulary')
            vocabulary_service.handle_text_message(event)
            return
       
        # 明確請求選單
        elif text == "#menu" or text.lower() == "menu" or text == "選單" or text == "返回主選單":
            clear_user_state(user_id)
            send_menu_message(event.reply_token)
            return
       
        # 檢查用戶是否在對話中
        elif hasattr(conversation_service, 'user_sessions') and user_id in conversation_service.user_sessions and \
             conversation_service.user_sessions[user_id].get('state') == 'in_conversation':
            conversation_service.handle_text_message(event)
            return
           
        # 檢查用戶是否在詞彙練習中
        elif hasattr(vocabulary_service, 'user_sessions') and user_id in vocabulary_service.user_sessions:
            vocabulary_service.handle_text_message(event)
            return
           
        # 檢查用戶是否在聽力訓練中
        elif hasattr(listening_service, 'user_sessions') and user_id in listening_service.user_sessions:
            listening_service.handle_text_message(event)
            return
           
        else:
            # 未匹配到指令，發送主選單
            clear_user_state(user_id)
            send_menu_message(event.reply_token)
           
    except Exception as e:
        logging.error(f"處理訊息時發生錯誤：{str(e)}")
        traceback.print_exc()
        send_error_message(event.reply_token)

def clear_user_state(user_id, new_activity=None):
    # 清理用戶所有活動狀態
    try:
        logging.info(f"清理用戶 {user_id} 的狀態，準備開始新活動: {new_activity}")
        
        # 清理對話服務狀態
        if hasattr(conversation_service, 'user_sessions') and user_id in conversation_service.user_sessions:
            if new_activity != 'conversation':
                del conversation_service.user_sessions[user_id]
        
        # 清理詞彙服務狀態
        if hasattr(vocabulary_service, 'user_sessions') and user_id in vocabulary_service.user_sessions:
            if new_activity != 'vocabulary':
                del vocabulary_service.user_sessions[user_id]
        
        # 清理聽力訓練狀態
        if hasattr(listening_service, 'user_sessions') and user_id in listening_service.user_sessions:
            if new_activity != 'listening':
                del listening_service.user_sessions[user_id]
        
        # 清理跟讀練習狀態
        try:
            from app.features.shadowing.service import UserSession
            user_session = UserSession.get_by_line_user_id(user_id)
            
            if user_session and hasattr(user_session, 'session_type') and user_session.session_type == "shadowing":
                if new_activity != 'shadowing':
                    UserSession.delete(user_id)
        except (ImportError, Exception) as e:
            logging.debug(f"清理跟讀練習狀態時發生錯誤: {str(e)}")
        
        logging.info(f"用戶 {user_id} 狀態清理完成")
        
    except Exception as e:
        logging.error(f"清理用戶狀態時發生錯誤: {str(e)}")
        traceback.print_exc()

@handler.add(MessageEvent, message=AudioMessage)
def handle_audio_message(event):
    # 處理音頻消息
    try:
        user_id = event.source.user_id
        logging.info(f"收到用戶音頻：用戶ID {user_id}")
        
        message_id = event.message.id
        message_content = line_bot_api.get_message_content(message_id)
        
        with tempfile.NamedTemporaryFile(delete=False, suffix='.m4a') as f:
            for chunk in message_content.iter_content():
                f.write(chunk)
            temp_file_path = f.name
        
        logging.info(f"音頻已保存到臨時文件: {temp_file_path}")
        
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
            logging.debug(f"檢查跟讀練習狀態時發生錯誤: {str(e)}")

        # 檢查用戶是否在聽力訓練中
        if hasattr(listening_service, 'user_sessions') and user_id in listening_service.user_sessions:
            result_message = listening_service.evaluate_listening(user_id, temp_file_path)
            line_bot_api.reply_message(event.reply_token, result_message)
            os.unlink(temp_file_path)
            return
        
        # 檢查用戶是否在對話練習中
        if hasattr(conversation_service, 'user_sessions') and user_id in conversation_service.user_sessions and \
             conversation_service.user_sessions[user_id].get('state') == 'in_conversation':
            
            if hasattr(conversation_service, 'handle_audio_message'):
                try:
                    result_message = conversation_service.handle_audio_message(user_id, temp_file_path, event)
                    
                    if result_message:
                        if not isinstance(result_message, list):
                            result_message = [result_message]
                        line_bot_api.reply_message(event.reply_token, result_message)
                    
                    os.unlink(temp_file_path)
                    return
                except Exception as e:
                    logging.error(f"對話服務處理音頻時發生錯誤: {str(e)}")
                    line_bot_api.reply_message(
                        event.reply_token,
                        TextSendMessage(text="處理您的語音訊息時發生錯誤，請嘗試使用文字輸入。")
                    )
                    os.unlink(temp_file_path)
                    return
        
        # 用戶不在任何訓練中
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text="收到您的語音訊息，但目前沒有進行中的練習環節。請從選單中選擇相應功能開始練習。")
        )
        os.unlink(temp_file_path)
        
    except Exception as e:
        logging.error(f"處理音頻訊息時發生錯誤：{str(e)}")
        traceback.print_exc()
        
        try:
            if 'temp_file_path' in locals() and os.path.exists(temp_file_path):
                os.unlink(temp_file_path)
        except Exception as clean_err:
            logging.error(f"清理臨時文件時發生錯誤: {str(clean_err)}")
        
        send_error_message(event.reply_token)

@handler.add(PostbackEvent)
def handle_postback(event):
    # 處理 Postback 事件
    try:
        data = event.postback.data
        user_id = event.source.user_id
        logging.info(f"收到 Postback：{data} (用戶ID：{user_id})")
        
        # 處理跟讀練習
        if data == 'action=shadowing':
            clear_user_state(user_id)
            
            items = [
                QuickReplyButton(action=PostbackAction(label="初級", data="shadowing_level=beginner")),
                QuickReplyButton(action=PostbackAction(label="中級", data="shadowing_level=intermediate")),
                QuickReplyButton(action=PostbackAction(label="高級", data="shadowing_level=advanced"))
            ]
            
            quick_reply = TextSendMessage(
                text="請選擇跟讀練習的難易度：",
                quick_reply=QuickReply(items=items)
            )
            line_bot_api.reply_message(event.reply_token, quick_reply)
            
        elif data.startswith('shadowing_level='):
            difficulty = data.split('=')[1]
            clear_user_state(user_id, 'shadowing')
            
            try:
                messages = shadowing_service.start_shadowing_session(user_id, difficulty)
                
                if messages is None:
                    send_error_message(event.reply_token)
                    return
                
                if not isinstance(messages, list):
                    messages = [messages]
                
                line_bot_api.reply_message(event.reply_token, messages)
                logging.info(f"已啟動難度為 {difficulty} 的跟讀練習")
            except Exception as e:
                logging.error(f"啟動跟讀練習時發生錯誤: {str(e)}")
                send_error_message(event.reply_token)
        
        # 處理聽力訓練
        elif data == 'action=listening':
            clear_user_state(user_id)
            
            items = [
                QuickReplyButton(action=PostbackAction(label="初級", data="listening_level=beginner")),
                QuickReplyButton(action=PostbackAction(label="中級", data="listening_level=intermediate")),
                QuickReplyButton(action=PostbackAction(label="高級", data="listening_level=advanced"))
            ]
            
            quick_reply = TextSendMessage(
                text="請選擇聽力訓練的難易度：",
                quick_reply=QuickReply(items=items)
            )
            line_bot_api.reply_message(event.reply_token, quick_reply)
            
        elif data.startswith('listening_level='):
            difficulty = data.split('=')[1]
            clear_user_state(user_id, 'listening')
            
            try:
                messages = listening_service.start_listening_session(user_id, difficulty)
                
                if messages is None:
                    send_error_message(event.reply_token)
                    return
                
                if not isinstance(messages, list):
                    messages = [messages]
                
                line_bot_api.reply_message(event.reply_token, messages)
                logging.info(f"已啟動難度為 {difficulty} 的聽力訓練")
            except Exception as e:
                logging.error(f"啟動聽力訓練時發生錯誤: {str(e)}")
                send_error_message(event.reply_token)
                
        else:
            logging.info(f"未處理的 Postback：{data}")
            clear_user_state(user_id)
            send_menu_message(event.reply_token)
            
    except Exception as e:
        logging.error(f"處理 Postback 事件時發生錯誤：{str(e)}")
        traceback.print_exc()
        send_error_message(event.reply_token)

@line_bp.route("/callback", methods=['POST'])
def callback():
    # 處理 LINE Webhook
    signature = request.headers['X-Line-Signature']
    body = request.get_data(as_text=True)
    
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        logging.error("無效的簽名")
        abort(400)
    except Exception as e:
        logging.error(f"處理 webhook 時發生錯誤：{str(e)}")
        traceback.print_exc()
        abort(500)
        
    return 'OK'

@line_bp.route('/static/audio/<filename>')
def serve_static_audio(filename):
    # 處理靜態音頻檔案請求
    try:
        # 檢查主靜態音頻目錄
        if os.path.exists(os.path.join(STATIC_AUDIO_FOLDER, filename)):
            return send_from_directory(STATIC_AUDIO_FOLDER, filename, mimetype='audio/mpeg')
        
        # 檢查應用靜態音頻目錄
        if os.path.exists(os.path.join(APP_STATIC_AUDIO_FOLDER, filename)):
            return send_from_directory(APP_STATIC_AUDIO_FOLDER, filename, mimetype='audio/mpeg')
        
        # 檢查服務特定的音頻目錄
        services = [
            getattr(conversation_service, 'audio_folder', None),
            getattr(shadowing_service, 'audio_folder', None),
            getattr(listening_service, 'audio_folder', None)
        ]
        
        for folder in services:
            if folder and os.path.exists(os.path.join(folder, filename)):
                return send_from_directory(folder, filename, mimetype='audio/mpeg')
        
        logging.error(f"靜態音頻文件不存在: {filename}")
        return "Static audio file not found", 404
    except Exception as e:
        logging.error(f"處理靜態音頻檔案請求時發生錯誤：{str(e)}")
        return "Error serving static audio file", 500

@line_bp.route('/audio/<filename>')
def serve_audio(filename):
    # 處理音頻檔案請求 (向後兼容)
    try:
        # 檢查各服務的音頻目錄
        services = [
            ('shadowing', getattr(shadowing_service, 'audio_folder', None)),
            ('listening', getattr(listening_service, 'audio_folder', None)),
            ('conversation', getattr(conversation_service, 'audio_folder', None))
        ]
        
        for service_name, folder in services:
            if folder:
                file_path = os.path.join(folder, filename)
                if os.path.exists(file_path):
                    return send_from_directory(folder, filename, mimetype='audio/mpeg')
        
        # 檢查主靜態目錄
        if os.path.exists(os.path.join(STATIC_AUDIO_FOLDER, filename)):
            return send_from_directory(STATIC_AUDIO_FOLDER, filename, mimetype='audio/mpeg')
        
        # 重定向到靜態音頻路由
        return serve_static_audio(filename)
    except Exception as e:
        logging.error(f"處理音頻檔案請求時發生錯誤：{str(e)}")
        return "Error serving audio file", 500

@line_bp.route('/audio-debug')
def audio_debug():
    # 音頻路徑調試
    try:
        return {
            "basedir": basedir,
            "static_audio_folder": STATIC_AUDIO_FOLDER,
            "app_static_audio_folder": APP_STATIC_AUDIO_FOLDER,
            "conversation_audio_folder": getattr(conversation_service, 'audio_folder', 'Not defined'),
            "shadowing_audio_folder": getattr(shadowing_service, 'audio_folder', 'Not defined'),
            "listening_audio_folder": getattr(listening_service, 'audio_folder', 'Not defined'),
            "current_directory": os.getcwd(),
            "ngrok_url": os.getenv('NGROK_URL')
        }
    except Exception as e:
        return {"error": str(e), "traceback": traceback.format_exc()}

@line_bp.route('/test')
def test():
    # 測試路由
    return 'LINE Bot is running!'

def create_rich_menu(line_bot_api):
    # 創建 Rich Menu
    try:
        rich_menu = RichMenu(
            size=RichMenuSize(width=2500, height=1686),
            selected=True,
            name="English Practice Platform",
            chat_bar_text="功能選單",
            areas=[
                RichMenuArea(
                    bounds=RichMenuBounds(x=0, y=0, width=1250, height=843),
                    action=MessageAction(label="英語對話練習", text="#start_conversation")
                ),
                RichMenuArea(
                    bounds=RichMenuBounds(x=1250, y=0, width=1250, height=843),
                    action=MessageAction(label="單字造句", text="#start_vocabulary")
                ),
                RichMenuArea(
                    bounds=RichMenuBounds(x=0, y=843, width=1250, height=843),
                    action=PostbackAction(label="跟讀練習", data="action=shadowing")
                ),
                RichMenuArea(
                    bounds=RichMenuBounds(x=1250, y=843, width=1250, height=843),
                    action=PostbackAction(label="聽力練習", data="action=listening")
                )
            ]
        )
        
        rich_menu_id = line_bot_api.create_rich_menu(rich_menu=rich_menu)
        logging.info(f"選單已創建，ID: {rich_menu_id}")
        
        # 找到圖片路徑
        possible_paths = [
            os.path.join(basedir, 'static', 'images', 'rich_menu.png'),
            os.path.join(basedir, 'app', 'static', 'images', 'rich_menu.png'),
            os.path.join(basedir, 'app', 'static', 'rich_menu.png')
        ]
        
        image_path = None
        for path in possible_paths:
            if os.path.exists(path):
                image_path = path
                break
                
        if not image_path:
            logging.warning("找不到選單圖片")
            return rich_menu_id
        
        logging.info(f"找到選單圖片: {image_path}")
        
        # 處理並上傳圖片
        try:
            img = Image.open(image_path)
            img = img.resize((2500, 1686), Image.LANCZOS)
            
            buffer = io.BytesIO()
            img.save(buffer, format="PNG", optimize=True, quality=30)
            compressed_image = buffer.getvalue()
            
            # 如果超過1MB，轉換為JPEG
            if len(compressed_image) > 1000000:
                buffer = io.BytesIO()
                if img.mode in ('RGBA', 'LA'):
                    background = Image.new("RGB", img.size, (255, 255, 255))
                    background.paste(img, mask=img.split()[3])
                    img = background
                
                img.save(buffer, format="JPEG", optimize=True, quality=65)
                compressed_image = buffer.getvalue()
                content_type = 'image/jpeg'
            else:
                content_type = 'image/png'
            
            # 上傳圖片
            headers = {
                'Authorization': f'Bearer {os.environ.get("LINE_CHANNEL_ACCESS_TOKEN")}',
                'Content-Type': content_type
            }
            url = f'https://api-data.line.me/v2/bot/richmenu/{rich_menu_id}/content'
            
            response = requests.post(url, headers=headers, data=compressed_image)
            
            if response.status_code == 200:
                logging.info("圖片上傳成功")
                line_bot_api.set_default_rich_menu(rich_menu_id)
                logging.info("已設定為預設選單")
            else:
                logging.error(f"圖片上傳失敗: {response.status_code} {response.text}")
        
        except Exception as e:
            logging.error(f"處理圖片時發生錯誤: {str(e)}")
            traceback.print_exc()
            
        return rich_menu_id
        
    except Exception as e:
        logging.error(f"創建選單時發生錯誤: {str(e)}")
        return None

def generate_audio_message(text, user_id):
    # 生成語音訊息（備用函數）
    try:
        base_url = os.getenv('NGROK_URL', "http://localhost:5000").rstrip('/').strip()
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        audio_filename = f"conversation_{user_id}_{timestamp}.mp3"
        audio_file_path = os.path.join(STATIC_AUDIO_FOLDER, audio_filename)
        
        from gtts import gTTS
        tts = gTTS(text=text, lang='en')
        tts.save(audio_file_path)
        
        try:
            from mutagen.mp3 import MP3
            audio = MP3(audio_file_path)
            duration = int(audio.info.length * 1000)
        except Exception:
            duration = 5000
        
        audio_url = f"{base_url}/static/audio/{audio_filename}"
        return AudioSendMessage(original_content_url=audio_url, duration=duration)
    except Exception as e:
        logging.error(f"生成語音訊息時發生錯誤: {str(e)}")
        raise

def setup_routes(app):
    # 設置所有路由並初始化 LINE Bot
    try:
        registered_blueprints = [b.name for b in app.blueprints.values()] if hasattr(app, 'blueprints') else []
        
        if line_bp.name not in registered_blueprints:
            app.register_blueprint(line_bp)
            logging.info("藍圖註冊成功")
        else:
            logging.info(f"藍圖 '{line_bp.name}' 已經註冊")
        
        # 初始化服務
        init_services()
        diagnose_conversation_service()
        
        # 設置音頻目錄
        app.config['STATIC_AUDIO_FOLDER'] = STATIC_AUDIO_FOLDER
        app.config['APP_STATIC_AUDIO_FOLDER'] = APP_STATIC_AUDIO_FOLDER
        
        os.makedirs(app.config['STATIC_AUDIO_FOLDER'], exist_ok=True)
        os.makedirs(app.config['APP_STATIC_AUDIO_FOLDER'], exist_ok=True)
        
        # 重置並創建 Rich Menu
        reset_and_create_rich_menu()
        
        return app
    except Exception as e:
        logging.error(f"設置路由時發生錯誤：{str(e)}")
        traceback.print_exc()
        return app