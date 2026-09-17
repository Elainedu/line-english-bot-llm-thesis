import os
import json
import traceback
import requests
import time
from flask import request, abort, send_from_directory, Blueprint
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import (
    MessageEvent, TextMessage, AudioMessage, TextSendMessage,
    QuickReplyButton, QuickReply, MessageAction, PostbackEvent, PostbackAction,
    RichMenu, RichMenuArea, RichMenuBounds, URIAction
)
from linebot.models import (
    RichMenu, RichMenuArea, RichMenuBounds, MessageAction, RichMenuSize
)
import tempfile
from PIL import Image
import io
from datetime import datetime

# 創建藍圖
line_bp = Blueprint('line', __name__)

# 獲取應用根目錄
basedir = os.path.abspath(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

# 定義統一的音頻文件目錄
STATIC_AUDIO_FOLDER = os.path.join(basedir, 'static', 'audio')
APP_STATIC_AUDIO_FOLDER = os.path.join(basedir, 'app', 'static', 'audio')

# 確保這些目錄存在
os.makedirs(STATIC_AUDIO_FOLDER, exist_ok=True)
os.makedirs(APP_STATIC_AUDIO_FOLDER, exist_ok=True)

# LINE Bot setup
try:
    line_bot_api = LineBotApi(os.getenv('LINE_CHANNEL_ACCESS_TOKEN'))
    handler = WebhookHandler(os.getenv('LINE_CHANNEL_SECRET'))
    print("LINE Bot API 初始化成功")
except Exception as e:
    print(f"LINE Bot API 初始化失敗: {str(e)}")
    raise

# 全局服務變數
conversation_service = None
vocabulary_service = None
shadowing_service = None
listening_service = None

def init_services():
    """初始化服務"""
    global conversation_service, vocabulary_service, shadowing_service, listening_service
    
    try:
        # 延遲導入服務 - 解決循環導入問題
        try:
            # 嘗試導入 ConversationService
            try:
                from app.features.conversation.service import ConversationService
                print("正在初始化對話服務...")
                conversation_service = ConversationService(line_bot_api, handler)
                
                # 測試服務是否正常運作
                if hasattr(conversation_service, 'handle_text_message'):
                    print("對話服務初始化成功")
                else:
                    raise AttributeError("對話服務缺少必要的方法")
                    
            except (ImportError, AttributeError) as e:
                print(f"對話服務初始化失敗: {str(e)}")
                traceback.print_exc()
                
                # 創建一個有基本功能的替代服務類
                class DummyConversationService:
                    def __init__(self):
                        self.user_sessions = {}
                        self.audio_folder = STATIC_AUDIO_FOLDER
                        self.static_audio_folder = os.path.join(basedir, 'app', 'features', 'conversation', 'audio')
                    
                    def handle_text_message(self, event):
                        # 提供一個簡單的回復而不是錯誤信息
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
                        # 為自我介紹主題創建硬編碼回應
                        if topic == "自我介紹":
                            # 更新用戶狀態
                            self.user_sessions[user_id] = {
                                'state': 'in_conversation',
                                'topic': 'self_intro',
                                'history': [],
                                'difficulty': 'intermediate'
                            }
                            
                            # 發送固定回應
                            messages = [
                                TextSendMessage(
                                    text="主題已設置為: 👋 自我介紹\n難度: Intermediate\n\n請開始您的對話練習!"
                                ),
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
                
                conversation_service = DummyConversationService()
                print("使用替代對話服務初始化成功")
        except Exception as e:
            print(f"對話服務初始化過程中發生全局錯誤: {str(e)}")
            traceback.print_exc()
            # 確保至少有一個基本的服務實例
            class EmergencyConversationService:
                def __init__(self):
                    self.user_sessions = {}
                    self.audio_folder = STATIC_AUDIO_FOLDER
                    self.static_audio_folder = os.path.join(basedir, 'app', 'features', 'conversation', 'audio')
                def handle_text_message(self, event):
                    line_bot_api.reply_message(
                        event.reply_token,
                        TextSendMessage(text="對話服務初始化時發生錯誤，請稍後再試或聯繫管理員。")
                    )
                def handle_audio_message(self, user_id, audio_file_path, event=None):
                    return TextSendMessage(text="語音功能暫時不可用，請使用文字輸入。")
            conversation_service = EmergencyConversationService()
            print("使用緊急對話服務初始化成功")
        
        # 詞彙服務
        try:
            from app.features.voc.service import VocabularyService
            vocabulary_service = VocabularyService(line_bot_api)
            print("詞彙服務初始化成功")
        except Exception as e:
            print(f"詞彙服務初始化失敗: {str(e)}")
            traceback.print_exc()
            # 創建一個空的服務類
            class DummyVocabularyService:
                def __init__(self):
                    self.user_sessions = {}
                def handle_text_message(self, event):
                    # 生成示例單詞
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
            vocabulary_service = DummyVocabularyService()
            print("使用替代詞彙服務初始化成功")
        
        # 跟讀練習服務
        try:
            from app.features.shadowing.service import ShadowingService
            # 檢查初始化參數是否需要 audio_folder
            import inspect
            shadowing_params = inspect.signature(ShadowingService.__init__).parameters
            if 'audio_folder' in shadowing_params:
                shadowing_service = ShadowingService(line_bot_api, audio_folder=STATIC_AUDIO_FOLDER)
            else:
                shadowing_service = ShadowingService(line_bot_api)
                # 手動設置 audio_folder 屬性
                shadowing_service.audio_folder = STATIC_AUDIO_FOLDER
                shadowing_service.static_audio_folder = os.path.join(basedir, 'app', 'features', 'shadowing', 'audio')
            print("跟讀練習服務初始化成功")
        except Exception as e:
            print(f"跟讀練習服務初始化失敗: {str(e)}")
            traceback.print_exc()
            # 創建一個空的服務類
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
                    # 提供一個簡單的訊息而不是錯誤
                    return TextSendMessage(
                        text="跟讀練習準備中... 請選擇其他功能或稍後再試。"
                    )
                def evaluate_shadowing(self, user_id, audio_file_path):
                    return TextSendMessage(text="跟讀練習評估服務暫時不可用，請稍後再試。")
            shadowing_service = DummyShadowingService()
            print("使用替代跟讀練習服務初始化成功")
        
        # 聽力訓練服務
        try:
            from app.features.listening.service import ListeningService
            # 檢查初始化參數是否需要 audio_folder
            import inspect
            listening_params = inspect.signature(ListeningService.__init__).parameters
            if 'audio_folder' in listening_params:
                listening_service = ListeningService(line_bot_api, audio_folder=STATIC_AUDIO_FOLDER)
            else:
                listening_service = ListeningService(line_bot_api)
                # 手動設置 audio_folder 屬性
                listening_service.audio_folder = STATIC_AUDIO_FOLDER
                listening_service.static_audio_folder = os.path.join(basedir, 'app', 'features', 'listening', 'audio')
            print("聽力訓練服務初始化成功")
        except Exception as e:
            print(f"聽力訓練服務初始化失敗: {str(e)}")
            traceback.print_exc()
            # 創建一個空的服務類
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
                    # 提供一個簡單的訊息而不是錯誤
                    return TextSendMessage(
                        text="聽力訓練準備中... 請選擇其他功能或稍後再試。"
                    )
                def evaluate_listening(self, user_id, audio_file_path):
                    return TextSendMessage(text="聽力訓練評估服務暫時不可用，請稍後再試。")
                def get_user_session(self, user_id):
                    return None
            listening_service = DummyListeningService()
            print("使用替代聽力訓練服務初始化成功")
        
        print("所有服務初始化完成")
        
    except Exception as e:
        print(f"服務初始化過程中發生全局錯誤: {str(e)}")
        traceback.print_exc()

def diagnose_conversation_service():
    """診斷 ConversationService 加載失敗的原因"""
    try:
        print("\n===== 開始診斷 ConversationService =====")
        
        # 檢查模組路徑是否正確
        try:
            import importlib
            conversation_module = importlib.import_module('app.features.conversation.service')
            print("成功導入模組: app.features.conversation.service")
            
            if hasattr(conversation_module, 'ConversationService'):
                print("模組中存在 ConversationService 類")
                
                # 檢查 __init__ 函數的參數
                import inspect
                init_params = inspect.signature(conversation_module.ConversationService.__init__).parameters
                print(f"ConversationService.__init__ 參數: {list(init_params.keys())}")
                
                # 檢查提示文件
                try:
                    prompts_module = importlib.import_module('app.features.conversation.prompts.menu_prompts')
                    print("成功導入提示模組: app.features.conversation.prompts.menu_prompts")
                    
                    if hasattr(prompts_module, 'MAIN_TOPICS'):
                        print(f"提示模組中存在 MAIN_TOPICS，包含 {len(prompts_module.MAIN_TOPICS)} 個主題")
                    else:
                        print("錯誤: 提示模組中缺少 MAIN_TOPICS 定義")
                        
                    if hasattr(prompts_module, 'TOPIC_PROMPTS'):
                        print(f"提示模組中存在 TOPIC_PROMPTS，包含 {len(prompts_module.TOPIC_PROMPTS)} 個主題提示")
                    else:
                        print("錯誤: 提示模組中缺少 TOPIC_PROMPTS 定義")
                except Exception as prompts_err:
                    print(f"導入提示模組時出錯: {str(prompts_err)}")
                    traceback.print_exc()
            else:
                print("錯誤: 模組中不存在 ConversationService 類")
        except Exception as module_err:
            print(f"導入模組時出錯: {str(module_err)}")
            traceback.print_exc()
        
        print("===== ConversationService 診斷結束 =====\n")
    except Exception as e:
        print(f"診斷過程中發生錯誤: {str(e)}")
        traceback.print_exc()

def reset_and_create_rich_menu():
    """刪除所有現有的 Rich Menu 並創建新的"""
    try:
        # 獲取所有 Rich Menu
        rich_menu_list = line_bot_api.get_rich_menu_list()
        
        # 刪除所有現有的 Rich Menu，加入延遲避免觸發 API 限制
        for rich_menu in rich_menu_list:
            try:
                line_bot_api.delete_rich_menu(rich_menu.rich_menu_id)
                print(f"已刪除選單 ID: {rich_menu.rich_menu_id}")
                # 添加延遲，避免 API 請求頻率過高
                time.sleep(0.5)
            except Exception as e:
                print(f"刪除選單 {rich_menu.rich_menu_id} 時發生錯誤: {str(e)}")
        
        print("已刪除所有現有選單")
        
        # 添加延遲，確保刪除操作已完成
        time.sleep(1)
        
        # 重新創建 Rich Menu
        new_rich_menu_id = create_rich_menu(line_bot_api)
        print(f"已創建新選單，ID: {new_rich_menu_id}")
        
        return new_rich_menu_id
    except Exception as e:
        print(f"重置 Rich Menu 時發生錯誤: {str(e)}")
        traceback.print_exc()
        return None

def send_menu_message(reply_token):
    """發送主選單訊息"""
    try:
        items = [
            QuickReplyButton(
                action=MessageAction(
                    label="對話練習",
                    text="#start_conversation"
                )
            ),
            QuickReplyButton(
                action=MessageAction(
                    label="詞彙練習",
                    text="#start_vocabulary"
                )
            ),
            QuickReplyButton(
                action=PostbackAction(
                    label="跟讀練習",
                    data="action=shadowing"
                )
            ),
            QuickReplyButton(
                action=PostbackAction(
                    label="聽力訓練",
                    data="action=listening"
                )
            )
        ]
        
        # 使用更簡潔的提示文字
        message = TextSendMessage(
            text="請選擇學習功能",
            quick_reply=QuickReply(items=items)
        )
        
        line_bot_api.reply_message(reply_token, message)
        print("主選單訊息發送成功")
    except Exception as e:
        print(f"發送主選單訊息失敗：{str(e)}")
        send_error_message(reply_token)

def send_error_message(reply_token):
    """發送錯誤訊息"""
    try:
        line_bot_api.reply_message(
            reply_token,
            TextSendMessage(text="抱歉，處理您的要求時發生錯誤。請再試一次。")
        )
        print("錯誤訊息發送成功")
    except Exception as e:
        print(f"發送錯誤訊息失敗：{str(e)}")

@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
   """處理文字訊息的主要邏輯"""
   try:
       text = event.message.text.strip()
       user_id = event.source.user_id
       print("\n====== 訊息處理開始 ======")
       print(f"收到用戶訊息：{text}")
       print(f"用戶ID：{user_id}")
       
       # 輸出用戶當前狀態（調試用）
       if hasattr(conversation_service, 'user_sessions') and user_id in conversation_service.user_sessions:
           print(f"用戶在對話服務狀態: {conversation_service.user_sessions[user_id]}")
       if hasattr(vocabulary_service, 'user_sessions') and user_id in vocabulary_service.user_sessions:
           print(f"用戶在詞彙服務狀態: {vocabulary_service.user_sessions[user_id]}")
       
       # 檢查用戶是否在跟讀練習中
       try:
           from app.features.shadowing.service import UserSession
           user_session = UserSession.get_by_line_user_id(user_id)
           if user_session and user_session.session_type == "shadowing":
               print(f"用戶正在跟讀練習中: {user_session.session_data}")
       except ImportError:
           print("跟讀練習模組未完全實現或無法導入")
           user_session = None
       except Exception as e:
           print(f"檢查跟讀練習狀態時發生錯誤: {str(e)}")
           user_session = None
           
       # 檢查用戶是否在聽力訓練中
       try:
           from app.features.listening.service import UserSession as ListeningUserSession
           listening_user_session = ListeningUserSession.get_by_line_user_id(user_id)
           if listening_user_session and listening_user_session.session_type == "listening":
               print(f"用戶正在聽力訓練中: {listening_user_session.session_data}")
       except ImportError:
           print("聽力訓練模組未完全實現或無法導入")
           listening_user_session = None
       except Exception as e:
           print(f"檢查聽力訓練狀態時發生錯誤: {str(e)}")
           listening_user_session = None

       # 處理所有命令和選單操作前，先清理用戶狀態
       if text.startswith('#') or text == "選單" or text == "返回主選單" or text.lower() == "menu":
           print("檢測到命令或選單請求，清理用戶狀態")
           # 特殊處理 #end_conversation，因為這需要結束對話後的特殊操作
           if text == "#end_conversation":
               if hasattr(conversation_service, 'user_sessions') and user_id in conversation_service.user_sessions:
                   conversation_service.handle_text_message(event)
                   return
           # 其他所有命令和選單請求都清理狀態後再處理
           clear_user_state(user_id)
       
       # 處理難度設置命令
       if text.startswith('#level'):
           print("檢測到難度設置指令")
           conversation_service.handle_text_message(event)
           return

       # 處理跟讀練習相關命令
       elif text.startswith('#shadowing') or text == "跟讀練習":
           print("檢測到跟讀練習指令，清理用戶狀態")
           clear_user_state(user_id, 'shadowing')
           
           print("顯示跟讀練習難度選擇")
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
           print("檢測到聽力訓練指令，清理用戶狀態")
           clear_user_state(user_id, 'listening')
           
           print("顯示聽力訓練難度選擇")
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
           print("檢測到開始對話指令，清理用戶狀態")
           clear_user_state(user_id, 'conversation')
           conversation_service.handle_text_message(event)
           return
           
       # 處理主題設置
       elif text.startswith('#topic'):
           print("\n===== 處理主題設置指令 =====")
           print(f"檢測到對話主題設置指令: {text}")
           
           # 從指令中提取主題
           topic_text = text[7:].strip()
           print(f"提取的主題文本: '{topic_text}'")
           
           # 檢查主題是否為空
           if not topic_text:
               print("主題為空，顯示主題選擇")
               conversation_service.start_conversation(user_id, event.reply_token)
               return
           
           # 檢查映射表
           if hasattr(conversation_service, 'topic_mapping'):
               print(f"主題映射表: {conversation_service.topic_mapping}")
               if topic_text in conversation_service.topic_mapping:
                   actual_topic = conversation_service.topic_mapping[topic_text]
                   print(f"主題 '{topic_text}' 在映射表中，映射到 '{actual_topic}'")
               else:
                   print(f"主題 '{topic_text}' 不在映射表中")
           else:
               print("警告: conversation_service 沒有 topic_mapping 屬性")
           
           # 嘗試設置主題
           try:
               print(f"嘗試設置主題: {topic_text}")
               conversation_service.set_topic(user_id, topic_text, event.reply_token)
               print("主題設置完成")
           except Exception as e:
               print(f"設置主題時發生錯誤: {str(e)}")
               traceback.print_exc()
               send_error_message(event.reply_token)
           
           print("===== 主題設置指令處理完成 =====\n")
           return
           
       elif text.startswith('#start_vocabulary') or text.startswith('#vocab'):
           print("檢測到詞彙練習指令，清理用戶狀態")
           clear_user_state(user_id, 'vocabulary')
           vocabulary_service.handle_text_message(event)
           return
       
       # 明確請求選單或結束當前活動的情況
       elif text == "#menu" or text.lower() == "menu" or text == "選單" or text == "返回主選單":
           print("用戶請求主選單，清理所有狀態")
           clear_user_state(user_id)
           send_menu_message(event.reply_token)
           return
       
       # 檢查用戶是否在對話中
       elif hasattr(conversation_service, 'user_sessions') and user_id in conversation_service.user_sessions and \
            conversation_service.user_sessions[user_id].get('state') == 'in_conversation':
           print("用戶正在對話中，轉發到 ConversationService")
           conversation_service.handle_text_message(event)
           return
           
       # 檢查用戶是否在詞彙練習中
       elif hasattr(vocabulary_service, 'user_sessions') and user_id in vocabulary_service.user_sessions:
           print("用戶正在詞彙練習中")
           vocabulary_service.handle_text_message(event)
           return
           
       # 檢查用戶是否在聽力訓練中
       elif hasattr(listening_service, 'user_sessions') and user_id in listening_service.user_sessions:
           print("用戶正在聽力訓練中")
           listening_service.handle_text_message(event)
           return
           
       # 檢查用戶是否在跟讀練習中 (使用 UserSession 模式)
       elif user_session and user_session.session_type == "shadowing":
           print("用戶正在跟讀練習中 (UserSession)")
           shadowing_service.handle_text_message(event)
           return
           
       # 檢查用戶是否在聽力訓練中 (使用 UserSession 模式)
       elif listening_user_session and listening_user_session.session_type == "listening":
           print("用戶正在聽力訓練中 (UserSession)")
           listening_service.handle_text_message(event)
           return
           
       else:
           # 如果都不匹配，清理所有狀態並發送主選單
           print("未匹配到指令或活動狀態，清理用戶狀態並發送主選單")
           clear_user_state(user_id)
           send_menu_message(event.reply_token)
           
   except Exception as e:
       print(f"處理訊息時發生錯誤：{str(e)}")
       traceback.print_exc()
       send_error_message(event.reply_token)
   finally:
       print("====== 訊息處理結束 ======\n")

def debug_all_services():
    """打印所有服務的關鍵屬性"""
    print("\n==== 服務調試信息 ====")
    
    # 檢查對話服務
    print("\n對話服務:")
    if not conversation_service:
        print("  對話服務未初始化")
    else:
        print(f"  已初始化對話服務的類型: {type(conversation_service)}")
        if hasattr(conversation_service, 'topic_mapping'):
            print(f"  主題映射表大小: {len(conversation_service.topic_mapping)}")
            print(f"  '自我介紹' 在映射表中: {'自我介紹' in conversation_service.topic_mapping}")
            if '自我介紹' in conversation_service.topic_mapping:
                print(f"  '自我介紹' 映射到: {conversation_service.topic_mapping['自我介紹']}")
        else:
            print("  缺少 topic_mapping 屬性")
            
        if hasattr(conversation_service, 'TOPICS'):
            print(f"  主題列表: {conversation_service.TOPICS}")
        else:
            print("  缺少 TOPICS 屬性")
    
    # 檢查其他服務...
    
    print("==== 調試信息結束 ====\n")

def clear_user_state(user_id, new_activity=None):
    """清理用戶所有活動狀態，為開始新活動做準備"""
    try:
        print(f"清理用戶 {user_id} 的狀態，準備開始新活動: {new_activity}")
        
        # 保存清理前的狀態（用於日誌）
        old_states = {}
        
        # 清理對話服務狀態
        if hasattr(conversation_service, 'user_sessions') and user_id in conversation_service.user_sessions:
            old_states['conversation'] = conversation_service.user_sessions[user_id]
            print(f"清理對話服務狀態: {old_states['conversation']}")
            if new_activity != 'conversation':
                del conversation_service.user_sessions[user_id]
        
        # 清理詞彙服務狀態
        if hasattr(vocabulary_service, 'user_sessions') and user_id in vocabulary_service.user_sessions:
            old_states['vocabulary'] = vocabulary_service.user_sessions[user_id]
            print(f"清理詞彙服務狀態: {old_states['vocabulary']}")
            if new_activity != 'vocabulary':
                del vocabulary_service.user_sessions[user_id]
        
        # 清理聽力訓練狀態
        if hasattr(listening_service, 'user_sessions') and user_id in listening_service.user_sessions:
            old_states['listening'] = listening_service.user_sessions[user_id]
            print(f"清理聽力訓練狀態: {old_states['listening']}")
            if new_activity != 'listening':
                del listening_service.user_sessions[user_id]
        
        # 清理跟讀練習狀態 (使用文件或資料庫)
        try:
            from app.features.shadowing.service import UserSession
            
            # 嘗試獲取會話
            user_session = UserSession.get_by_line_user_id(user_id)
            
            if user_session and hasattr(user_session, 'session_type') and user_session.session_type == "shadowing":
                if hasattr(user_session, 'session_data'):
                    old_states['shadowing'] = user_session.session_data
                    print(f"清理跟讀練習狀態: {old_states['shadowing']}")
                
                if new_activity != 'shadowing':
                    # 使用類方法刪除會話
                    result = UserSession.delete(user_id)
                    print(f"刪除跟讀練習UserSession: {'成功' if result else '失敗'}")
        except ImportError:
            print("跟讀練習模組未完全實現，無法清理狀態")
        except Exception as e:
            print(f"清理跟讀練習狀態時發生錯誤: {str(e)}")
            traceback.print_exc()
        
        # 清理聽力訓練狀態 (使用同樣的 UserSession 類)
        try:
            from app.features.shadowing.service import UserSession
            
            # 檢查會話類型是否為 listening
            user_session = UserSession.get_by_line_user_id(user_id)
            
            if user_session and hasattr(user_session, 'session_type') and user_session.session_type == "listening":
                if hasattr(user_session, 'session_data'):
                    old_states['listening_session'] = user_session.session_data
                    print(f"清理聽力訓練狀態 (UserSession): {old_states['listening_session']}")
                
                if new_activity != 'listening':
                    # 使用類方法刪除會話
                    result = UserSession.delete(user_id)
                    print(f"刪除聽力訓練UserSession: {'成功' if result else '失敗'}")
        except ImportError:
            print("聽力訓練模組未完全實現，無法清理狀態")
        except Exception as e:
            print(f"清理聽力訓練狀態時發生錯誤: {str(e)}")
            traceback.print_exc()
        
        # 確認清理成功並繼續處理...
        # [保留其餘代碼不變]
        
        print(f"用戶 {user_id} 狀態清理完成，準備開始新活動: {new_activity}")
        print(f"清理前的舊狀態: {old_states}")
        
    except Exception as e:
        print(f"清理用戶狀態時發生錯誤: {str(e)}")
        traceback.print_exc()

@handler.add(MessageEvent, message=AudioMessage)
def handle_audio_message(event):
   """處理音頻消息"""
   try:
       user_id = event.source.user_id
       print(f"\n====== 音頻訊息處理開始 ======")
       print(f"收到用戶音頻：用戶ID {user_id}")
       
       # 獲取音頻內容
       message_id = event.message.id
       message_content = line_bot_api.get_message_content(message_id)
       
       # 創建臨時文件保存音頻
       with tempfile.NamedTemporaryFile(delete=False, suffix='.m4a') as f:
           for chunk in message_content.iter_content():
               f.write(chunk)
           temp_file_path = f.name
       
       print(f"音頻已保存到臨時文件: {temp_file_path}")
       
       # 首先檢查用戶是否在跟讀練習中 (優先檢查，因為跟讀練習的主要輸入是音頻)
       try:
           from app.features.shadowing.service import UserSession
           user_session = UserSession.get_by_line_user_id(user_id)
           
           if user_session and user_session.session_type == "shadowing":
               print("用戶正在跟讀練習中，處理音頻...")
               
               # 使用跟讀練習服務評估表現
               result_message = shadowing_service.evaluate_shadowing(user_id, temp_file_path)
               
               # 回覆評估結果
               line_bot_api.reply_message(event.reply_token, result_message)
               
               # 清理臨時文件
               os.unlink(temp_file_path)
               print("臨時音頻文件已刪除")
               return
       except Exception as e:
           print(f"檢查跟讀練習狀態時發生錯誤: {str(e)}")
           traceback.print_exc()

       # 檢查用戶是否在聽力訓練中 (使用 UserSession 模式)
       try:
           from app.features.listening.service import UserSession as ListeningUserSession
           listening_user_session = ListeningUserSession.get_by_line_user_id(user_id)
           
           if listening_user_session and listening_user_session.session_type == "listening":
               print("用戶正在聽力訓練中 (UserSession)，處理音頻...")
               
               # 使用聽力訓練服務評估表現
               result_message = listening_service.evaluate_listening(user_id, temp_file_path)
               
               # 回覆評估結果
               line_bot_api.reply_message(event.reply_token, result_message)
               
               # 清理臨時文件
               os.unlink(temp_file_path)
               print("臨時音頻文件已刪除")
               return
       except Exception as e:
           print(f"檢查聽力訓練狀態時發生錯誤: {str(e)}")
           traceback.print_exc()
       
       # 檢查用戶是否在聽力訓練中 (使用 user_sessions)
       if hasattr(listening_service, 'user_sessions') and user_id in listening_service.user_sessions:
           print("用戶正在聽力訓練中，處理音頻...")
           
           # 使用聽力訓練服務評估表現
           result_message = listening_service.evaluate_listening(user_id, temp_file_path)
           
           # 回覆評估結果
           line_bot_api.reply_message(event.reply_token, result_message)
           
           # 清理臨時文件
           os.unlink(temp_file_path)
           print("臨時音頻文件已刪除")
           return
       
       # 最後檢查用戶是否在對話練習中
       if hasattr(conversation_service, 'user_sessions') and user_id in conversation_service.user_sessions and \
            conversation_service.user_sessions[user_id].get('state') == 'in_conversation':
           print("用戶正在對話練習中，處理音頻...")
           
           # 使用對話練習服務處理音頻
           if hasattr(conversation_service, 'handle_audio_message'):
               try:
                   result_message = conversation_service.handle_audio_message(user_id, temp_file_path, event)
                   
                   # 如果返回了消息，則回覆
                   if result_message:
                       if not isinstance(result_message, list):
                           result_message = [result_message]
                       line_bot_api.reply_message(event.reply_token, result_message)
                   
                   # 清理臨時文件
                   os.unlink(temp_file_path)
                   print("臨時音頻文件已刪除")
                   return
               except Exception as e:
                   print(f"對話服務處理音頻時發生錯誤: {str(e)}")
                   traceback.print_exc()
                   line_bot_api.reply_message(
                       event.reply_token,
                       TextSendMessage(text="處理您的語音訊息時發生錯誤，請嘗試使用文字輸入。")
                   )
                   os.unlink(temp_file_path)
                   return
           else:
               print("對話服務缺少 handle_audio_message 方法")
               line_bot_api.reply_message(
                   event.reply_token,
                   TextSendMessage(text="目前對話練習暫不支援語音輸入，請使用文字訊息。")
               )
               os.unlink(temp_file_path)
               return
       
       # 如果用戶不在任何特定訓練中
       print("用戶未在任何語音相關訓練中，發送提示訊息")
       line_bot_api.reply_message(
           event.reply_token,
           TextSendMessage(text="收到您的語音訊息，但目前沒有進行中的對話練習、跟讀練習或聽力訓練環節。請從選單中選擇相應功能開始練習。")
       )
       
       # 清理臨時文件
       os.unlink(temp_file_path)
       print("臨時音頻文件已刪除")
       
   except Exception as e:
       print(f"處理音頻訊息時發生錯誤：{str(e)}")
       traceback.print_exc()
       
       # 嘗試清理臨時文件
       try:
           if 'temp_file_path' in locals() and os.path.exists(temp_file_path):
               os.unlink(temp_file_path)
               print("臨時音頻文件已刪除")
       except Exception as clean_err:
           print(f"清理臨時文件時發生錯誤: {str(clean_err)}")
       
       send_error_message(event.reply_token)
   finally:
       print("====== 音頻訊息處理結束 ======\n")

@handler.add(PostbackEvent)
def handle_postback(event):
    """處理 Postback 事件"""
    try:
        # 確保導入所需的類
        from linebot.models import (
            TextSendMessage, AudioSendMessage, QuickReply, 
            QuickReplyButton, MessageAction, PostbackAction
        )
        
        data = event.postback.data
        user_id = event.source.user_id
        print(f"\n====== Postback 處理開始 ======")
        print(f"收到 Postback：{data}")
        print(f"用戶ID：{user_id}")
        
        # 增加更多的調試信息
        print(f"Postback 數據類型：{type(data)}")
        print(f"Postback 數據內容詳情：{repr(data)}")
        
        # 處理跟讀練習相關的 postback
        if data == 'action=shadowing':
            print("確認匹配：跟讀練習")
            # 清理用戶所有活動狀態，為開始跟讀練習做準備
            clear_user_state(user_id)
            
            # 顯示難度選擇
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
            # 解析選擇的難度
            difficulty = data.split('=')[1]
            print(f"用戶選擇的跟讀練習難度：{difficulty}")
            
            # 再次確保清理狀態
            clear_user_state(user_id, 'shadowing')
            
            try:
                # 使用跟讀練習服務開始新環節
                messages = shadowing_service.start_shadowing_session(user_id, difficulty)
                
                # 如果返回 None，發送錯誤消息
                if messages is None:
                    send_error_message(event.reply_token)
                    return
                
                # 如果是單一訊息，轉換為列表
                if not isinstance(messages, list):
                    messages = [messages]
                
                # 回覆訊息
                line_bot_api.reply_message(event.reply_token, messages)
                print(f"已啟動難度為 {difficulty} 的跟讀練習環節")
            except Exception as e:
                print(f"啟動跟讀練習環節時發生錯誤: {str(e)}")
                traceback.print_exc()
                send_error_message(event.reply_token)
        
        # 處理聽力訓練相關的 postback
        elif data == 'action=listening':
            print("確認匹配：聽力訓練")
            # 清理用戶所有活動狀態，為開始聽力訓練做準備
            clear_user_state(user_id)
            
            # 顯示難度選擇
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
            # 解析選擇的難度
            difficulty = data.split('=')[1]
            print(f"用戶選擇的聽力訓練難度：{difficulty}")
            
            # 再次確保清理狀態
            clear_user_state(user_id, 'listening')
            
            try:
                # 使用聽力訓練服務開始新環節
                messages = listening_service.start_listening_session(user_id, difficulty)
                
                print(f"start_listening_session 返回值類型: {type(messages)}")
                if messages is None:
                    print("警告: start_listening_session 返回了 None")
                    send_error_message(event.reply_token)
                    return
                
                # 如果是單一訊息，轉換為列表
                if not isinstance(messages, list):
                    print(f"將單一訊息轉換為列表: {messages}")
                    messages = [messages]
                
                # 檢查訊息內容
                for i, msg in enumerate(messages):
                    print(f"訊息 {i+1} 類型: {type(msg)}")
                    if hasattr(msg, 'type'):
                        print(f"訊息 {i+1} 類型: {msg.type}")
                
                # 回覆訊息
                line_bot_api.reply_message(event.reply_token, messages)
                print(f"已啟動難度為 {difficulty} 的聽力訓練環節")
            except Exception as e:
                print(f"啟動聽力訓練環節時發生錯誤: {str(e)}")
                traceback.print_exc()
                send_error_message(event.reply_token)
                
        # 處理詞彙練習相關的 postback
        elif data.startswith('vocabulary_level='):
            # 解析選擇的難度
            level_map = {
                'beginner': '初級',
                'intermediate': '中級',
                'advanced': '高級'
            }
            difficulty = level_map.get(data.split('=')[1], '初級')
            print(f"用戶選擇的詞彙練習難度：{difficulty}")
            
            # 再次確保清理狀態
            clear_user_state(user_id, 'vocabulary')
            
            try:
                # 檢查詞彙服務是否有 start_vocabulary_session 方法
                if hasattr(vocabulary_service, 'start_vocabulary_session'):
                    # 使用詞彙練習服務開始新環節
                    vocabulary_service.start_vocabulary_session(user_id, difficulty, event.reply_token)
                    print(f"已啟動難度為 {difficulty} 的詞彙練習環節")
                else:
                    # 如果沒有該方法，使用臨時解決方案
                    print("詞彙服務缺少 start_vocabulary_session 方法，使用基本方法處理")
                    self._start_vocabulary_session_basic(user_id, difficulty, event.reply_token)
            except Exception as e:
                print(f"啟動詞彙練習環節時發生錯誤: {str(e)}")
                traceback.print_exc()
                send_error_message(event.reply_token)
            
        # 處理其他 postback 事件...
        else:
            print(f"未處理的 Postback：{data}")
            # 清理用戶狀態並發送主選單
            clear_user_state(user_id)
            send_menu_message(event.reply_token)
            
    except Exception as e:
        print(f"處理 Postback 事件時發生錯誤：{str(e)}")
        traceback.print_exc()
        send_error_message(event.reply_token)
    finally:
        print("====== Postback 處理結束 ======\n")

def _start_vocabulary_session_basic(user_id, difficulty, reply_token):
    """基本的詞彙練習啟動函數（備用）"""
    try:
        # 根據難度選擇單詞列表
        if difficulty == "初級":
            words = ["apple", "book", "cat", "dog", "egg"]
        elif difficulty == "中級":
            words = ["adventure", "beautiful", "conversation", "development", "environment"]
        else:  # 高級
            words = ["assimilation", "bureaucracy", "comprehensive", "disproportionate", "entrepreneurship"]
        
        # 更新用戶會話狀態
        if hasattr(vocabulary_service, 'user_sessions'):
            vocabulary_service.user_sessions[user_id] = {
                'state': 'in_vocabulary',
                'difficulty': difficulty,
                'words': words,
                'current_word': words[0]
            }
        
        # 發送訊息
        line_bot_api.reply_message(
            reply_token,
            [
                TextSendMessage(text=f"已選擇{difficulty}難度的詞彙練習。"),
                TextSendMessage(text=f"您的第一個單字是: {words[0]}"),
                TextSendMessage(
                    text="請使用這個單字造一個句子。",
                    quick_reply=QuickReply(items=[
                        QuickReplyButton(action=MessageAction(label="更換單字", text="#change_word")),
                        QuickReplyButton(action=MessageAction(label="結束練習", text="#end_vocabulary"))
                    ])
                )
            ]
        )
        print(f"已使用基本方法啟動難度為 {difficulty} 的詞彙練習")
    except Exception as e:
        print(f"使用基本方法啟動詞彙練習時發生錯誤: {str(e)}")
        send_error_message(reply_token)

def _start_vocabulary_session_basic(user_id, difficulty, reply_token):
    """基本的詞彙練習啟動函數（備用）"""
    try:
        # 根據難度選擇單詞列表
        if difficulty == "初級":
            words = ["apple", "book", "cat", "dog", "egg"]
        elif difficulty == "中級":
            words = ["adventure", "beautiful", "conversation", "development", "environment"]
        else:  # 高級
            words = ["assimilation", "bureaucracy", "comprehensive", "disproportionate", "entrepreneurship"]
        
        # 更新用戶會話狀態
        if hasattr(vocabulary_service, 'user_sessions'):
            vocabulary_service.user_sessions[user_id] = {
                'state': 'in_vocabulary',
                'difficulty': difficulty,
                'words': words,
                'current_word': words[0]
            }
        
        # 發送訊息
        line_bot_api.reply_message(
            reply_token,
            [
                TextSendMessage(text=f"已選擇{difficulty}難度的詞彙練習。"),
                TextSendMessage(text=f"您的第一個單字是: {words[0]}"),
                TextSendMessage(
                    text="請使用這個單字造一個句子。",
                    quick_reply=QuickReply(items=[
                        QuickReplyButton(action=MessageAction(label="更換單字", text="#change_word")),
                        QuickReplyButton(action=MessageAction(label="結束練習", text="#end_vocabulary"))
                    ])
                )
            ]
        )
        print(f"已使用基本方法啟動難度為 {difficulty} 的詞彙練習")
    except Exception as e:
        print(f"使用基本方法啟動詞彙練習時發生錯誤: {str(e)}")
        send_error_message(reply_token)

@line_bp.route("/callback", methods=['POST'])
def callback():
    """處理 LINE Webhook"""
    print("\n====== Webhook 處理開始 ======")
    
    signature = request.headers['X-Line-Signature']
    body = request.get_data(as_text=True)
    print(f"收到 webhook 請求：{body}")
    
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        print("無效的簽名")
        abort(400)
    except Exception as e:
        print(f"處理 webhook 時發生錯誤：{str(e)}")
        traceback.print_exc()
        abort(500)
    finally:
        print("====== Webhook 處理結束 ======\n")
        
    return 'OK'

@line_bp.route('/static/audio/<filename>')
def serve_static_audio(filename):
    """處理靜態音頻檔案請求"""
    try:
        print(f"提供靜態音頻文件請求: {filename}")
        
        # 檢查主靜態音頻目錄
        if os.path.exists(os.path.join(STATIC_AUDIO_FOLDER, filename)):
            print(f"在主靜態音頻目錄找到文件: {os.path.join(STATIC_AUDIO_FOLDER, filename)}")
            return send_from_directory(STATIC_AUDIO_FOLDER, filename, mimetype='audio/mpeg')
        
        # 檢查應用靜態音頻目錄
        if os.path.exists(os.path.join(APP_STATIC_AUDIO_FOLDER, filename)):
            print(f"在應用靜態音頻目錄找到文件: {os.path.join(APP_STATIC_AUDIO_FOLDER, filename)}")
            return send_from_directory(APP_STATIC_AUDIO_FOLDER, filename, mimetype='audio/mpeg')
        
        # 檢查服務特定的靜態音頻目錄
        services = [
            ("ConversationService", getattr(conversation_service, 'audio_folder', None)),
            ("ShadowingService", getattr(shadowing_service, 'audio_folder', None)),
            ("ListeningService", getattr(listening_service, 'audio_folder', None)),
            ("ShadowingService Static", getattr(shadowing_service, 'static_audio_folder', None)),
            ("ListeningService Static", getattr(listening_service, 'static_audio_folder', None)),
            ("ConversationService Static", getattr(conversation_service, 'static_audio_folder', None))
        ]
        
        for service_name, folder in services:
            if folder and os.path.exists(os.path.join(folder, filename)):
                print(f"在 {service_name} 音頻目錄找到文件: {os.path.join(folder, filename)}")
                return send_from_directory(folder, filename, mimetype='audio/mpeg')
        
        # 找不到文件
        print(f"靜態音頻文件不存在: {filename}")
        print(f"已檢查主目錄: {STATIC_AUDIO_FOLDER}")
        print(f"已檢查應用目錄: {APP_STATIC_AUDIO_FOLDER}")
        for service_name, folder in services:
            if folder:
                print(f"已檢查 {service_name} 目錄: {folder}")
        
        return "Static audio file not found", 404
    except Exception as e:
        print(f"處理靜態音頻檔案請求時發生錯誤：{str(e)}")
        traceback.print_exc()
        return "Error serving static audio file", 500

@line_bp.route('/audio/<filename>')
def serve_audio(filename):
    """處理音頻檔案請求 (用於向後兼容)"""
    try:
        print(f"提供音頻文件請求: {filename}")
        
        # 檢查跟讀練習音頻目錄
        if hasattr(shadowing_service, 'audio_folder'):
            shadowing_path = os.path.join(shadowing_service.audio_folder, filename)
            if os.path.exists(shadowing_path):
                print(f"在跟讀練習音頻目錄找到文件: {shadowing_path}")
                return send_from_directory(shadowing_service.audio_folder, filename, mimetype='audio/mpeg')
            
         # 然後檢查聽力訓練音頻目錄
        if hasattr(listening_service, 'audio_folder'):
            listening_path = os.path.join(listening_service.audio_folder, filename)
            if os.path.exists(listening_path):
                print(f"在聽力訓練音頻目錄找到文件: {listening_path}")
                return send_from_directory(listening_service.audio_folder, filename, mimetype='audio/mpeg')
        
        # 然後檢查對話服務音頻目錄
        if hasattr(conversation_service, 'audio_folder'):
            conversation_path = os.path.join(conversation_service.audio_folder, filename)
            if os.path.exists(conversation_path):
                print(f"在對話服務音頻目錄找到文件: {conversation_path}")
                return send_from_directory(conversation_service.audio_folder, filename, mimetype='audio/mpeg')
        
        # 檢查主靜態音頻目錄
        if os.path.exists(os.path.join(STATIC_AUDIO_FOLDER, filename)):
            print(f"在主靜態音頻目錄找到文件: {os.path.join(STATIC_AUDIO_FOLDER, filename)}")
            return send_from_directory(STATIC_AUDIO_FOLDER, filename, mimetype='audio/mpeg')
        
        # 找不到文件，嘗試重定向到靜態音頻路由
        print(f"音頻文件不存在，嘗試重定向到靜態路由: {filename}")
        return serve_static_audio(filename)
    except Exception as e:
        print(f"處理音頻檔案請求時發生錯誤：{str(e)}")
        traceback.print_exc()
        return "Error serving audio file", 500

@line_bp.route('/audio-debug')
def audio_debug():
    """音頻路徑調試"""
    try:
        # 對話音頻目錄
        conv_audio_folder = getattr(conversation_service, 'audio_folder', 'Not defined')
        conv_files = os.listdir(conv_audio_folder) if os.path.exists(conv_audio_folder) else []
        
        # 對話靜態音頻目錄
        conv_static_audio_folder = getattr(conversation_service, 'static_audio_folder', 'Not defined')
        conv_static_files = os.listdir(conv_static_audio_folder) if os.path.exists(conv_static_audio_folder) else []
        
        # 跟讀練習音頻目錄
        shadowing_audio_folder = getattr(shadowing_service, 'audio_folder', 'Not defined')
        shadowing_files = os.listdir(shadowing_audio_folder) if os.path.exists(shadowing_audio_folder) else []
        
        # 聽力訓練音頻目錄
        listening_audio_folder = getattr(listening_service, 'audio_folder', 'Not defined')
        listening_files = os.listdir(listening_audio_folder) if os.path.exists(listening_audio_folder) else []
        
        # 靜態音頻目錄
        static_files = os.listdir(STATIC_AUDIO_FOLDER) if os.path.exists(STATIC_AUDIO_FOLDER) else []
        app_static_files = os.listdir(APP_STATIC_AUDIO_FOLDER) if os.path.exists(APP_STATIC_AUDIO_FOLDER) else []
        
        # 環境配置
        ngrok_url = os.getenv('NGROK_URL')
        
        return {
            "basedir": basedir,
            "conversation_audio_folder": conv_audio_folder,
            "conversation_static_audio_folder": conv_static_audio_folder,
            "shadowing_audio_folder": shadowing_audio_folder,
            "listening_audio_folder": listening_audio_folder,
            "static_audio_folder": STATIC_AUDIO_FOLDER,
            "app_static_audio_folder": APP_STATIC_AUDIO_FOLDER,
            
            "conversation_folder_exists": os.path.exists(conv_audio_folder),
            "conversation_static_folder_exists": os.path.exists(conv_static_audio_folder),
            "shadowing_folder_exists": os.path.exists(shadowing_audio_folder),
            "listening_folder_exists": os.path.exists(listening_audio_folder),
            "static_folder_exists": os.path.exists(STATIC_AUDIO_FOLDER),
            "app_static_folder_exists": os.path.exists(APP_STATIC_AUDIO_FOLDER),
            
            "conversation_files": conv_files,
            "conversation_static_files": conv_static_files,
            "shadowing_files": shadowing_files,
            "listening_files": listening_files,
            "static_files": static_files,
            "app_static_files": app_static_files,
            
            "current_directory": os.getcwd(),
            "ngrok_url": ngrok_url
        }
    except Exception as e:
        return {"error": str(e), "traceback": traceback.format_exc()}

@line_bp.route('/test')
def test():
    """測試路由"""
    return 'LINE Bot is running!'

def create_rich_menu(line_bot_api):
    try:
        # 定義選單 - 按照圖片的四分格設計
        rich_menu = RichMenu(
            size=RichMenuSize(width=2500, height=1686),  # 設定尺寸
            selected=True,  # 默認選擇狀態
            name="English Practice Platform",  # 選單名稱
            chat_bar_text="功能選單",  # 選單按鈕顯示文字
            areas=[  # 定義選單區域 - 四個主要功能
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
        
        # 創建選單
        rich_menu_id = line_bot_api.create_rich_menu(rich_menu=rich_menu)
        print(f"選單已創建，ID: {rich_menu_id}")
        
        # 找到圖片路徑
        basedir = os.path.abspath(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
        
        # 定義可能的圖片路徑
        possible_paths = [
            os.path.join(basedir, 'static', 'images', 'rich_menu.png'),
            os.path.join(basedir, 'app', 'static', 'images', 'rich_menu.png'),
            os.path.join(basedir, 'app', 'static', 'rich_menu.png')
        ]
        
        # 查找第一個存在的圖片路徑
        image_path = None
        for path in possible_paths:
            if os.path.exists(path):
                image_path = path
                break
                
        if not image_path:
            print("找不到選單圖片，請確保圖片位於正確路徑")
            return rich_menu_id
        
        print(f"找到選單圖片: {image_path}")
        
        # 圖片壓縮代碼
        try:
            # 打開並處理圖片
            img = Image.open(image_path)
            img = img.resize((2500, 1686), Image.LANCZOS)
            
            # 使用BytesIO來存儲壓縮後的圖片
            buffer = io.BytesIO()
            img.save(buffer, format="PNG", optimize=True, quality=30)
            compressed_image = buffer.getvalue()
            
            print(f"原始圖片大小: {os.path.getsize(image_path)} 字節")
            print(f"壓縮後大小: {len(compressed_image)} 字節")
            
            # 如果仍然超過1MB，更激進地壓縮
            if len(compressed_image) > 1000000:  # 1MB限制
                buffer = io.BytesIO()
                # 轉為RGB模式（去除透明度）
                if img.mode in ('RGBA', 'LA'):
                    background = Image.new("RGB", img.size, (255, 255, 255))
                    background.paste(img, mask=img.split()[3])
                    img = background
                
                # 以JPEG格式保存（更小但無透明度）
                img.save(buffer, format="JPEG", optimize=True, quality=65)
                compressed_image = buffer.getvalue()
                print(f"JPEG壓縮後大小: {len(compressed_image)} 字節")
                content_type = 'image/jpeg'
            else:
                content_type = 'image/png'
            
            # 上傳壓縮後的圖片
            headers = {
                'Authorization': f'Bearer {os.environ.get("LINE_CHANNEL_ACCESS_TOKEN")}',
                'Content-Type': content_type
            }
            url = f'https://api-data.line.me/v2/bot/richmenu/{rich_menu_id}/content'
            
            print(f"使用requests發送壓縮後圖片 (大小: {len(compressed_image)} 字節)")
            response = requests.post(url, headers=headers, data=compressed_image)
            
            # 檢查響應
            print(f"圖片上傳響應狀態碼: {response.status_code}")
            if response.status_code == 200:
                print("圖片上傳成功")
                # 設置為默認選單
                line_bot_api.set_default_rich_menu(rich_menu_id)
                print("已設定為預設選單")
            else:
                print(f"圖片上傳失敗: {response.status_code} {response.text}")
        
        except Exception as e:
            print(f"處理圖片時發生錯誤: {str(e)}")
            traceback.print_exc()
            
        return rich_menu_id
        
    except Exception as e:
        print(f"創建選單時發生錯誤: {str(e)}")
        return None

def generate_audio_message(text, user_id):
    """生成語音訊息（備用函數，當服務的 text_to_speech 無法使用時）"""
    try:
        # 設置基礎 URL
        base_url = os.getenv('NGROK_URL')
        if not base_url:
            base_url = "http://localhost:5000"
        base_url = base_url.rstrip('/').strip()
        
        # 生成唯一的文件名
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        audio_filename = f"conversation_{user_id}_{timestamp}.mp3"
        
        # 完整的音頻文件路徑
        audio_file_path = os.path.join(STATIC_AUDIO_FOLDER, audio_filename)
        
        # 使用 gTTS 生成音頻
        from gtts import gTTS
        tts = gTTS(text=text, lang='en')
        tts.save(audio_file_path)
        
        # 計算音頻時長
        try:
            from mutagen.mp3 import MP3
            audio = MP3(audio_file_path)
            duration = int(audio.info.length * 1000)  # 轉換為毫秒
        except Exception as e:
            print(f"計算音頻時長時發生錯誤: {str(e)}")
            duration = 5000  # 默認 5 秒
        
        # 創建音頻 URL
        audio_url = f"{base_url}/static/audio/{audio_filename}"
        
        # 返回音頻訊息
        return AudioSendMessage(original_content_url=audio_url, duration=duration)
    except Exception as e:
        print(f"生成語音訊息時發生錯誤: {str(e)}")
        traceback.print_exc()
        raise

def process_topic_fallback(user_id, topic_text, reply_token):
    """當 conversation_service 缺少 set_topic 方法時的備用處理"""
    try:
        # 檢查用戶會話
        if not hasattr(conversation_service, 'user_sessions'):
            conversation_service.user_sessions = {}
            
        # 映射主題名稱
        topic_mapping = {
            '自我介紹': 'self_intro',
            '旅遊': 'travel',
            '餐廳點餐': 'restaurant',
            '購物': 'shopping',
            '問路': 'directions'
        }
        
        actual_topic = topic_mapping.get(topic_text, 'self_intro')  # 默認使用自我介紹
        
        # 更新用戶狀態
        conversation_service.user_sessions[user_id] = {
            'state': 'in_conversation',
            'topic': actual_topic,
            'history': [],
            'difficulty': 'intermediate'  # 預設難度
        }
        
        # 獲取主題圖標
        topic_icons = {
            'self_intro': '👋',
            'travel': '✈️',
            'restaurant': '🍽️',
            'shopping': '🛒',
            'directions': '🗺️'
        }
        
        topic_icon = topic_icons.get(actual_topic, '👋')
        display_name = topic_text
        
        # AI問候語
        greetings = {
            'self_intro': [
                "Hi there! I'm your conversation partner today. Can you tell me a little bit about yourself?",
                "Hello! I'd love to know more about you. Could you introduce yourself?",
                "Hi! Let's practice introductions. What's your name and what do you do?"
            ],
            'travel': [
                "Hello! I heard you're interested in traveling. Have you visited any interesting places recently?",
                "Hi there! If you could go anywhere in the world, where would you travel to?",
                "Good day! I love talking about travel. What's your dream destination?"
            ],
            'restaurant': [
                "Welcome to our restaurant! What would you like to order today?",
                "Good evening! Today we have some special dishes on our menu. Would you like me to recommend something?",
                "Hello! Have you decided what you'd like to eat, or do you need more time with the menu?"
            ],
            'shopping': [
                "Welcome to the store! What are you looking for today?",
                "Hello! We're having a special sale today. Is there anything specific you're interested in?",
                "Hi there! Can I help you find something in our shop?"
            ],
            'directions': [
                "Excuse me, you look lost. Can I help you find your way?",
                "Hello! Are you trying to get somewhere? I might be able to help with directions.",
                "Hi there! Where are you trying to go? Maybe I can point you in the right direction."
            ]
        }
        
        ai_greeting = random.choice(greetings.get(actual_topic, greetings['self_intro']))
        
        # 設置快速回覆按鈕
        quick_reply = QuickReply(items=[
            QuickReplyButton(action=MessageAction(label="結束對話", text="#end_conversation")),
            QuickReplyButton(action=MessageAction(label="更換主題", text="#start_conversation"))
        ])
        
        # 生成語音消息
        try:
            audio_message = generate_audio_message(ai_greeting, user_id)
            messages = [
                TextSendMessage(
                    text=f"主題已設置為: {topic_icon} {display_name}\n難度: Intermediate\n\n請開始您的對話練習!"
                ),
                TextSendMessage(text=ai_greeting),
                audio_message,
                TextSendMessage(
                    text="提示: 您可以用文字或語音回覆。隨時輸入 #end_conversation 結束對話。",
                    quick_reply=quick_reply
                )
            ]
        except Exception as e:
            print(f"生成語音訊息失敗: {str(e)}")
            messages = [
                TextSendMessage(
                    text=f"主題已設置為: {topic_icon} {display_name}\n難度: Intermediate\n\n請開始您的對話練習!"
                ),
                TextSendMessage(text=ai_greeting),
                TextSendMessage(
                    text="提示: 您可以用文字回覆。隨時輸入 #end_conversation 結束對話。",
                    quick_reply=quick_reply
                )
            ]
        
        line_bot_api.reply_message(reply_token, messages)
    except Exception as e:
        print(f"備用主題設置處理時發生錯誤: {str(e)}")
        traceback.print_exc()
        send_error_message(reply_token)
        
def setup_routes(app):
    """Setup all routes and initialize LINE Bot"""
    try:
        # 檢查藍圖是否已註冊
        registered_blueprints = [b.name for b in app.blueprints.values()] if hasattr(app, 'blueprints') else []
        
        if line_bp.name not in registered_blueprints:
            # 註冊藍圖
            app.register_blueprint(line_bp)
            print("藍圖註冊成功")
        else:
            print(f"藍圖 '{line_bp.name}' 已經註冊，跳過註冊步驟")
        
        # 初始化服務
        init_services()

        # 進行診斷，幫助排除問題
        diagnose_conversation_service()
        debug_all_services()
        
        # 設置全局音頻文件目錄
        app.config['STATIC_AUDIO_FOLDER'] = STATIC_AUDIO_FOLDER
        app.config['APP_STATIC_AUDIO_FOLDER'] = APP_STATIC_AUDIO_FOLDER
        
        # 確保音頻目錄存在
        os.makedirs(app.config['STATIC_AUDIO_FOLDER'], exist_ok=True)
        os.makedirs(app.config['APP_STATIC_AUDIO_FOLDER'], exist_ok=True)
        
        # 重置並創建新的 Rich Menu
        reset_and_create_rich_menu()
        
        return app
    except Exception as e:
        print(f"設置路由時發生錯誤：{str(e)}")
        traceback.print_exc()
        # 即使出錯，也返回應用實例
        return app