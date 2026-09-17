import os
import json
import random
import tempfile
import requests
import traceback
import time
from datetime import datetime
from gtts import gTTS
from mutagen.mp3 import MP3
from linebot.models import (
    TextSendMessage, AudioSendMessage, QuickReply, 
    QuickReplyButton, MessageAction, PostbackAction
)

class ConversationService:
    def __init__(self, line_bot_api, handler=None):
        """初始化對話練習服務"""
        self.line_bot_api = line_bot_api
        self.handler = handler
        self.user_sessions = {}
        self._setup_directories()
        self._setup_prompts()
        self._init_whisper()
        self._setup_base_url()

    def _setup_directories(self):
        """設置目錄路徑"""
        current_dir = os.path.dirname(__file__)
        app_dir = os.path.dirname(os.path.dirname(current_dir))
        basedir = os.path.abspath(app_dir)
        
        base = os.path.join(basedir, 'app') if os.path.basename(basedir) != 'app' else basedir
        self.audio_folder = os.path.join(base, 'features', 'conversation', 'audio')
        self.static_audio_folder = os.path.join(base, 'static', 'audio')
        
        os.makedirs(self.audio_folder, exist_ok=True)
        os.makedirs(self.static_audio_folder, exist_ok=True)
        print(f"對話練習音頻目錄: {self.audio_folder}, {self.static_audio_folder}")

    def _init_whisper(self):
        """初始化 Whisper 語音識別模型 (如果可用)"""
        try:
            import whisper
            print("嘗試載入 Whisper 模型...")
            # 使用小模型以提高速度
            self.whisper_model = whisper.load_model("tiny")
            self.using_whisper = True
            print("Whisper 模型載入成功")
        except ImportError:
            print("Whisper 模組未安裝，語音識別功能將被禁用")
            self.using_whisper = False
        except Exception as e:
            print(f"載入 Whisper 模型時發生錯誤: {str(e)}")
            self.using_whisper = False

    def _setup_prompts(self):
        try:
            # 直接從檔案導入主題和提示
            try:
                # 從 menu_prompts.py 導入更新後的內容
                from app.features.conversation.prompts.menu_prompts import (
                    CONVERSATION_TOPICS, 
                    TOPIC_GUIDELINES, 
                    SCENE_DESCRIPTIONS, 
                    CONVERSATION_STARTERS,
                    EXAMPLE_PROMPTS,
                    RESPONSE_EXAMPLES,
                    AI_CONVERSATION_INSTRUCTIONS,
                    generate_conversation_scene,
                    generate_creative_prompt
                )
                
                # 設置主題資訊
                self.TOPICS = list(CONVERSATION_TOPICS.keys())
                self.MAIN_TOPICS = {}
                
                # 將 CONVERSATION_TOPICS 轉換為 MAIN_TOPICS 格式
                for topic_key, topic_data in CONVERSATION_TOPICS.items():
                    self.MAIN_TOPICS[topic_key] = {
                        'icon': topic_data.get('emoji', ''),
                        'description': topic_key,
                        'chinese_name': topic_data.get('zh_name', topic_key)
                    }
                
                # 創建主題名稱到實際主題的映射
                self.topic_mapping = {}
                for topic_key in self.TOPICS:
                    # 添加原始主題名稱
                    self.topic_mapping[topic_key] = topic_key
                    
                    # 添加中文別名
                    if 'zh_name' in CONVERSATION_TOPICS[topic_key]:
                        self.topic_mapping[CONVERSATION_TOPICS[topic_key]['zh_name']] = topic_key
                
                print(f"主題映射表初始化完成，共有 {len(self.topic_mapping)} 個映射項")
                
                # 儲存場景和問題生成函數
                self.generate_scene = generate_conversation_scene
                self.generate_prompt = generate_creative_prompt
                
                # 定義提示生成函數
                def get_topic_prompt(topic, difficulty):
                    # 將難度首字母大寫以匹配 TOPIC_GUIDELINES 的格式
                    difficulty_cap = difficulty.capitalize()
                    
                    # 獲取實際主題鍵
                    actual_topic = self.topic_mapping.get(topic, topic)
                    
                    # 檢查主題是否存在
                    if actual_topic not in self.TOPICS:
                        print(f"警告: 主題 '{actual_topic}' 不在已定義的主題列表中")
                        # 使用默認提示
                        return f"You are helping practice English conversation about {actual_topic} at {difficulty} level."
                    
                    # 從 TOPIC_GUIDELINES 獲取主題指南
                    if actual_topic in TOPIC_GUIDELINES:
                        topic_guide = TOPIC_GUIDELINES[actual_topic]
                        context = topic_guide.get('context', '')
                        level_guide = topic_guide.get(difficulty_cap, {})
                        
                        # 從難度級別指南獲取特定資訊
                        vocabulary = level_guide.get('vocabulary', [])
                        question_types = level_guide.get('question_types', [])
                        complexity = level_guide.get('complexity', '')
                        
                        # 組合系統提示
                        prompt = (
                            f"{AI_CONVERSATION_INSTRUCTIONS}\n\n"
                            f"Topic: {actual_topic}\n"
                            f"Context: {context}\n"
                            f"Difficulty level: {difficulty_cap}\n"
                            f"Recommended vocabulary: {', '.join(vocabulary[:10])}\n"
                            f"Question types to include: {', '.join(question_types)}\n"
                            f"Complexity guidance: {complexity}\n\n"
                            "Remember to maintain a natural conversation flow while helping the user practice their English."
                        )
                        return prompt
                    else:
                        return f"You are helping practice English conversation about {actual_topic} at {difficulty} level. {AI_CONVERSATION_INSTRUCTIONS}"
                
                # 定義問候語生成函數
                def get_greeting(topic):
                    # 獲取實際主題鍵
                    actual_topic = self.topic_mapping.get(topic, topic)
                    
                    # 檢查主題是否存在
                    if actual_topic not in self.TOPICS:
                        print(f"警告: 主題 '{actual_topic}' 不在已定義的主題列表中")
                        return f"Hello! Let's practice English conversation about {topic}. How can I help you today?"
                    
                    # 生成場景描述
                    difficulty = self.user_sessions.get(self.current_user_id, {}).get('difficulty', 'intermediate')
                    scene = self.generate_scene(actual_topic, difficulty)
                    
                    # 從 CONVERSATION_STARTERS 獲取起始問句
                    starter = CONVERSATION_STARTERS.get(actual_topic, {}).get(difficulty, "How can I help you today?")
                    
                    # 組合問候語 - 這裡需要修改
                    topic_icon = CONVERSATION_TOPICS.get(actual_topic, {}).get('emoji', '👋')
                    
                    # 添加場景描述和更自然的問候
                    greeting = f"{topic_icon} [{scene}]\n{starter}"
                    
                    return greeting
                
                self.get_topic_prompt = get_topic_prompt
                self.get_greeting = get_greeting
                self.current_user_id = None  # 用於在 get_greeting 中獲取當前用戶難度
                
                print("對話練習提示模板載入成功")
                print(f"可用主題: {self.TOPICS}")
                
            except ImportError as e:
                print(f"載入對話練習提示模板失敗: {str(e)}")
                traceback.print_exc()
                
                # 設置簡單的備用內容
                self.TOPICS = ["self_intro", "travel", "restaurant", "shopping", "directions"]
                self.MAIN_TOPICS = {
                    'self_intro': {'icon': '👋', 'description': '自我介紹', 'chinese_name': '自我介紹'},
                    'travel': {'icon': '✈️', 'description': '旅遊', 'chinese_name': '旅遊'},
                    'restaurant': {'icon': '🍽️', 'description': '餐廳點餐', 'chinese_name': '餐廳點餐'},
                    'shopping': {'icon': '🛒', 'description': '購物', 'chinese_name': '購物'},
                    'directions': {'icon': '🗺️', 'description': '問路', 'chinese_name': '問路'}
                }
                
                # 創建主題映射表
                self.topic_mapping = {
                    'self_intro': 'self_intro', '自我介紹': 'self_intro',
                    'travel': 'travel', '旅遊': 'travel',
                    'restaurant': 'restaurant', '餐廳點餐': 'restaurant',
                    'shopping': 'shopping', '購物': 'shopping',
                    'directions': 'directions', '問路': 'directions'
                }
                
                # 定義簡單的備用函數
                def simple_topic_prompt(topic, difficulty):
                    actual_topic = self.topic_mapping.get(topic, topic)
                    return f"You are helping practice English conversation about {actual_topic} at {difficulty} level."
                
                def simple_greeting(topic):
                    actual_topic = self.topic_mapping.get(topic, topic)
                    icon = self.MAIN_TOPICS.get(actual_topic, {}).get('icon', '👋')
                    return f"{icon} Let's practice English conversation about {actual_topic}. How can I help you today?"
                
                self.get_topic_prompt = simple_topic_prompt
                self.get_greeting = simple_greeting
                
                print("使用備用主題和提示初始化成功")
                
        except Exception as e:
            print(f"初始化提示時發生錯誤: {str(e)}")
            traceback.print_exc()
            
            # 最基本的備用設置 - 確保即使出錯也能提供基本功能
            self.TOPICS = ["self_intro", "travel", "restaurant", "shopping", "directions"]
            self.MAIN_TOPICS = {
                'self_intro': {'icon': '👋', 'description': '自我介紹', 'chinese_name': '自我介紹'},
                'travel': {'icon': '✈️', 'description': '旅遊', 'chinese_name': '旅遊'},
                'restaurant': {'icon': '🍽️', 'description': '餐廳點餐', 'chinese_name': '餐廳點餐'},
                'shopping': {'icon': '🛒', 'description': '購物', 'chinese_name': '購物'},
                'directions': {'icon': '🗺️', 'description': '問路', 'chinese_name': '問路'}
            }
            
            # 創建最基本的主題映射表
            self.topic_mapping = {
                'self_intro': 'self_intro', '自我介紹': 'self_intro',
                'travel': 'travel', '旅遊': 'travel',
                'restaurant': 'restaurant', '餐廳點餐': 'restaurant',
                'shopping': 'shopping', '購物': 'shopping',
                'directions': 'directions', '問路': 'directions'
            }
            
            def emergency_prompt(topic, difficulty):
                actual_topic = self.topic_mapping.get(topic, topic)
                return f"You are helping practice English conversation about {actual_topic}."
            
            def emergency_greeting(topic):
                actual_topic = self.topic_mapping.get(topic, topic)
                return f"👋 Hello! Let's practice English conversation about {actual_topic}. How can I help you today?"
            
            self.get_topic_prompt = emergency_prompt
            self.get_greeting = emergency_greeting
            
            print("使用緊急備用設置初始化成功")
        
    def _setup_base_url(self):
        """設置基礎 URL"""
        self.base_url = os.getenv('NGROK_URL')
        if not self.base_url:
            self.base_url = self._read_env_file() or "http://localhost:5000"
        self.base_url = self.base_url.rstrip('/').strip()
        print(f"使用的 URL: {self.base_url}")

    def _read_env_file(self):
        """從.env檔案讀取 NGROK_URL"""
        try:
            env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(self.audio_folder))), '.env')
            if os.path.exists(env_path):
                with open(env_path, 'r') as f:
                    for line in f:
                        if line.strip().startswith('NGROK_URL='):
                            return line.strip().split('=', 1)[1].strip().strip('"\'')
        except Exception:
            pass
        return None

    def handle_text_message(self, event):
        try:
            user_id = event.source.user_id
            text = event.message.text.strip()
            reply_token = event.reply_token
            
            print(f"ConversationService 收到訊息: {text} 從用戶: {user_id}")
            
            # 初始化用戶會話資料
            if user_id not in self.user_sessions:
                self.user_sessions[user_id] = {
                    'state': 'init',
                    'topic': None,
                    'history': [],
                    'difficulty': 'intermediate'  # 預設難度
                }
            
            session = self.user_sessions[user_id]
            state = session.get('state', 'init')
            
            print(f"用戶當前狀態: {state}, 主題: {session.get('topic')}")
            
            # 處理特殊命令
            if text.startswith('#'):
                if text == '#start_conversation':
                    # 如果用戶已經在對話中，先詢問是否要結束當前對話
                    if state == 'in_conversation':
                        self.line_bot_api.reply_message(
                            reply_token,
                            TextSendMessage(
                                text="您已經在進行對話了。要切換主題嗎？",
                                quick_reply=QuickReply(items=[
                                    QuickReplyButton(action=MessageAction(label="是，更換主題", text="#start_conversation_force")),
                                    QuickReplyButton(action=MessageAction(label="否，繼續當前對話", text="繼續對話"))
                                ])
                            )
                        )
                        return "handled"
                    
                    # 顯示難度選擇選項
                    items = [
                        QuickReplyButton(action=MessageAction(label="初級", text="#level beginner")),
                        QuickReplyButton(action=MessageAction(label="中級", text="#level intermediate")),
                        QuickReplyButton(action=MessageAction(label="高級", text="#level advanced"))
                    ]
                    
                    quick_reply = TextSendMessage(
                        text="請選擇對話練習的難易度：",
                        quick_reply=QuickReply(items=items)
                    )
                    self.line_bot_api.reply_message(reply_token, quick_reply)
                    return "handled"
                elif text == '#start_conversation_force':
                    # 強制開始新對話 - 先選擇難度
                    items = [
                        QuickReplyButton(action=MessageAction(label="初級", text="#level beginner")),
                        QuickReplyButton(action=MessageAction(label="中級", text="#level intermediate")),
                        QuickReplyButton(action=MessageAction(label="高級", text="#level advanced"))
                    ]
                    
                    quick_reply = TextSendMessage(
                        text="請選擇對話練習的難易度：",
                        quick_reply=QuickReply(items=items)
                    )
                    self.line_bot_api.reply_message(reply_token, quick_reply)
                    return "handled"
                elif text.startswith('#level '):
                    level = text[7:].strip().lower()
                    if level in ['beginner', 'intermediate', 'advanced']:
                        session['difficulty'] = level
                        session['state'] = 'topic_selection'
                        
                        # 顯示主題選擇
                        topic_buttons = []
                        for topic in self.TOPICS:
                            topic_info = self.MAIN_TOPICS.get(topic, {})
                            icon = topic_info.get('icon', '')
                            
                            # 優先使用中文名稱
                            if 'chinese_name' in topic_info:
                                display_name = topic_info['chinese_name']
                            else:
                                display_name = topic_info.get('description', topic)
                                
                            label = f"{icon} {display_name}" if icon else display_name
                            
                            # 確保標籤長度不超過 LINE 的限制
                            if len(label) > 20:
                                label = label[:17] + "..."
                                
                            topic_buttons.append(
                                QuickReplyButton(action=MessageAction(
                                    label=label, 
                                    text=f"#topic {topic}"
                                ))
                            )
                        
                        messages = [
                            TextSendMessage(text=f"難度已設置為: {level.capitalize()}"),
                            TextSendMessage(
                                text="請選擇您想練習的對話主題：",
                                quick_reply=QuickReply(items=topic_buttons)
                            )
                        ]
                        
                        self.line_bot_api.reply_message(reply_token, messages)
                        return "handled"
                    else:
                        self.line_bot_api.reply_message(
                            reply_token,
                            TextSendMessage(text="無效的難度設置。請選擇: beginner, intermediate, advanced")
                        )
                        return "handled"
                elif text.startswith('#topic '):
                    topic = text[7:].strip()
                    # 如果用戶已經在此主題的對話中，提示用戶
                    if state == 'in_conversation' and session.get('topic') == topic:
                        self.line_bot_api.reply_message(
                            reply_token,
                            TextSendMessage(text=f"您已經在 '{topic}' 主題的對話中。請繼續對話或輸入 #end_conversation 結束當前對話。")
                        )
                        return "handled"
                    return self.set_topic(user_id, topic, reply_token)
                elif text == '#end_conversation':
                    return self.end_conversation(user_id, reply_token)
                elif text == '#help':
                    return self.show_help(reply_token)
            
            # 如果用戶輸入「繼續對話」且正在對話中，不做任何處理，繼續對話
            if text == "繼續對話" and state == 'in_conversation':
                self.line_bot_api.reply_message(
                    reply_token,
                    TextSendMessage(text="好的，讓我們繼續對話。")
                )
                return "handled"
            
            # 根據當前狀態處理
            if state == 'init':
                # 用戶尚未開始對話，提供開始選項
                return self.start_conversation(user_id, reply_token)
            elif state == 'topic_selection':
                # 用戶正在選擇主題，把普通文本也當作主題處理
                return self.set_topic(user_id, text, reply_token)
            elif state == 'in_conversation':
                # 用戶在對話中
                return self.process_conversation(user_id, text, reply_token)
            else:
                # 未知狀態，重置對話
                print(f"未知狀態: {state}，重置對話")
                session['state'] = 'init'
                return self.start_conversation(user_id, reply_token)
        
        except Exception as e:
            print(f"處理文字訊息時發生錯誤: {str(e)}")
            traceback.print_exc()
            
            try:
                self.line_bot_api.reply_message(
                    event.reply_token,
                    TextSendMessage(text="處理您的訊息時發生錯誤，請再試一次。")
                )
            except:
                pass
                
    def handle_audio_message(self, user_id, audio_file_path, event=None):
        """處理用戶在對話練習中發送的音頻訊息"""
        try:
            # 確認用戶在對話中
            if user_id not in self.user_sessions or self.user_sessions[user_id].get('state') != 'in_conversation':
                return TextSendMessage(text="請先開始對話練習再發送語音訊息。")
            
            # 使用 Whisper 轉換語音為文字 (如果已安裝)
            user_text = None
            try:
                if hasattr(self, 'using_whisper') and self.using_whisper:
                    # 轉錄音頻
                    result = self.whisper_model.transcribe(audio_file_path)
                    user_text = result["text"]
                    print(f"語音識別結果: {user_text}")
                else:
                    return TextSendMessage(text="很抱歉，語音識別功能未啟用。請使用文字輸入。")
            except Exception as e:
                print(f"語音識別失敗: {str(e)}")
                return TextSendMessage(text="很抱歉，無法識別您的語音訊息。請嘗試使用文字輸入。")
            
            if not user_text:
                return TextSendMessage(text="語音識別未成功，請嘗試使用文字輸入。")
            
            # 獲取當前對話狀態
            session = self.user_sessions[user_id]
            topic = session.get('topic', '一般對話')
            history = session.get('history', [])
            
            # 添加用戶訊息到歷史
            history.append({
                'role': 'user',
                'content': user_text
            })
            
            # 獲取AI回應
            ai_response = self.get_ai_response(user_id, user_text, topic, history)
            
            # 添加AI回應到歷史
            history.append({
                'role': 'assistant',
                'content': ai_response
            })
            
            # 更新會話歷史
            session['history'] = history
            
            # 生成語音回應
            try:
                audio_message = self.text_to_speech(ai_response, user_id)
                return [
                    TextSendMessage(text=f"我聽到了: {user_text}"),
                    TextSendMessage(text=ai_response),
                    audio_message
                ]
            except Exception as audio_err:
                print(f"生成語音時發生錯誤: {str(audio_err)}")
                return [
                    TextSendMessage(text=f"我聽到了: {user_text}"),
                    TextSendMessage(text=ai_response)
                ]
        except Exception as e:
            print(f"處理音頻訊息時發生錯誤: {str(e)}")
            traceback.print_exc()
            return TextSendMessage(text="處理您的語音訊息時發生錯誤，請嘗試使用文字輸入。")

    def start_conversation(self, user_id, reply_token):
        try:
            print(f"開始對話: 用戶ID={user_id}")
            
            # 更新用戶狀態
            current_difficulty = self.user_sessions.get(user_id, {}).get('difficulty', 'intermediate')
            self.user_sessions[user_id] = {
                'state': 'topic_selection',
                'topic': None,
                'history': [],
                'difficulty': current_difficulty  # 保留現有難度設置或使用預設值
            }
            
            # 首先顯示難度選擇
            items = [
                QuickReplyButton(action=MessageAction(label="初級", text="#level beginner")),
                QuickReplyButton(action=MessageAction(label="中級", text="#level intermediate")),
                QuickReplyButton(action=MessageAction(label="高級", text="#level advanced"))
            ]
            
            quick_reply = TextSendMessage(
                text="請選擇對話練習的難易度：",
                quick_reply=QuickReply(items=items)
            )
            
            self.line_bot_api.reply_message(reply_token, [
                TextSendMessage(text="歡迎開始英語對話練習！"),
                quick_reply
            ])
            return "handled"
        except Exception as e:
            print(f"開始對話時發生錯誤: {str(e)}")
            traceback.print_exc()
            self.line_bot_api.reply_message(
                reply_token,
                TextSendMessage(text="開始對話時發生錯誤，請再試一次。")
            )

    def set_topic(self, user_id, topic, reply_token):
        try:
            print(f"設置主題開始: 用戶ID={user_id}, 主題={topic}")
            # 清理主題文本
            if topic.startswith('#topic '):
                topic = topic[7:].strip()
            
            # 檢查主題是否在映射表中
            actual_topic = None
            if topic in self.topic_mapping:
                actual_topic = self.topic_mapping[topic]
                print(f"找到主題映射: {topic} -> {actual_topic}")
            else:
                # 嘗試匹配不區分大小寫
                for key in self.topic_mapping.keys():
                    if key.lower() == topic.lower():
                        actual_topic = self.topic_mapping[key]
                        print(f"找到不區分大小寫主題映射: {topic} -> {actual_topic}")
                        break
            
            # 如果找不到映射，嘗試直接使用原始主題
            if not actual_topic:
                actual_topic = topic
                print(f"未找到主題映射，使用原始主題: {topic}")
                    
                # 檢查原始主題是否在 MAIN_TOPICS 或 TOPICS 中
                if actual_topic not in self.MAIN_TOPICS and actual_topic not in self.TOPICS:
                    print(f"主題既不在主題映射表中也不在已定義主題列表中: {actual_topic}")
                    
                    # 如果是中文主題名稱，嘗試查找對應的英文主題
                    for topic_key, topic_info in self.MAIN_TOPICS.items():
                        if ('chinese_name' in topic_info and topic_info['chinese_name'] == topic) or \
                        ('description' in topic_info and topic_info['description'] == topic):
                            actual_topic = topic_key
                            print(f"通過中文名稱找到主題: {topic} -> {actual_topic}")
                            break
            
            # 確認主題確實存在
            if actual_topic not in self.MAIN_TOPICS and actual_topic not in self.TOPICS:
                print(f"找不到有效的主題: {actual_topic}")
                
                # 顯示可用主題選項
                topic_buttons = []
                for t in self.TOPICS:
                    topic_info = self.MAIN_TOPICS.get(t, {})
                    icon = topic_info.get('icon', '')
                    
                    # 優先使用中文名稱作為顯示
                    if 'chinese_name' in topic_info:
                        display_name = topic_info['chinese_name']
                    else:
                        display_name = topic_info.get('description', t)
                    
                    label = f"{icon} {display_name}" if icon else display_name
                    
                    # 確保標籤長度不超過 LINE 的限制
                    if len(label) > 20:
                        label = label[:17] + "..."
                        
                    topic_buttons.append(
                        QuickReplyButton(action=MessageAction(
                            label=label, 
                            text=f"#topic {t}"
                        ))
                    )
                
                messages = [
                    TextSendMessage(text=f"抱歉，找不到主題「{topic}」。請從以下選項中選擇："),
                    TextSendMessage(
                        text="對話主題",
                        quick_reply=QuickReply(items=topic_buttons)
                    )
                ]
                
                self.line_bot_api.reply_message(reply_token, messages)
                return "handled"
            
            # 獲取當前難度設置
            current_session = self.user_sessions.get(user_id, {})
            difficulty = current_session.get('difficulty', 'intermediate')
            
            # 更新用戶狀態 - 確保創建新的狀態而不是修改現有的
            self.user_sessions[user_id] = {
                'state': 'in_conversation',
                'topic': actual_topic,
                'history': [],
                'difficulty': difficulty
            }

            # 設置當前用戶ID以便在get_greeting中獲取難度
            self.current_user_id = user_id
            
            print(f"用戶狀態已更新: {self.user_sessions[user_id]}")
            
            # 獲取主題相關資訊
            topic_info = self.MAIN_TOPICS.get(actual_topic, {})
            topic_icon = topic_info.get('icon', '')
            
            # 優先使用中文名稱作為顯示名稱
            if 'chinese_name' in topic_info:
                display_name = topic_info['chinese_name']
            else:
                display_name = topic_info.get('description', actual_topic)
            
            # 使用主題對應的提示生成系統訊息
            system_message = self.get_topic_prompt(actual_topic, difficulty)
            
            # 獲取中文場景描述
            difficulty_cap = difficulty.capitalize()
            
            # 從 menu_prompts.py 中導入場景描述
            try:
                from app.features.conversation.prompts.menu_prompts import SCENE_DESCRIPTIONS
                scene_description = SCENE_DESCRIPTIONS.get(actual_topic, {}).get(difficulty_cap, f"{display_name}場景")
            except (ImportError, KeyError):
                # 如果導入失敗或找不到對應描述，使用簡單描述
                scene_description = f"{display_name}場景"
            
            # 獲取問候語
            try:
                from app.features.conversation.prompts.menu_prompts import CONVERSATION_STARTERS
                starters = CONVERSATION_STARTERS.get(actual_topic, {}).get(difficulty_cap, "")
                
                # 如果 starters 是列表，隨機選擇一個
                if isinstance(starters, list) and starters:
                    starter = random.choice(starters)
                elif starters:
                    # 如果是字符串，直接使用
                    starter = starters
                else:
                    # 使用通用問候語
                    starter = "Hello! How are you today?"
                    
            except (ImportError, KeyError):
                # 如果導入失敗或找不到對應問候語，使用簡單問候
                starter = "Hello! How are you today?"
            
            # 組合成顯示的完整問候語（包含場景描述和圖標）
            display_greeting = f"{topic_icon} 【{scene_description}】\n{starter}"
            
            # 用於語音的純問候語（只包含實際對話部分）
            speech_greeting = starter
            
            print(f"系統訊息: {system_message[:50]}...")
            print(f"顯示問候語: {display_greeting}")
            print(f"語音問候語: {speech_greeting}")
            
            # 更新對話歷史 - 使用完整的顯示問候語
            self.user_sessions[user_id]['history'].append({
                'role': 'system',
                'content': system_message
            })
            self.user_sessions[user_id]['history'].append({
                'role': 'assistant',
                'content': display_greeting
            })
            
            # 設置簡化的按鈕選單 - 只有結束對話和更換主題
            quick_reply = QuickReply(items=[
                QuickReplyButton(action=MessageAction(label="結束對話", text="#end_conversation")),
                QuickReplyButton(action=MessageAction(label="更換主題", text="#start_conversation"))
            ])
            
            # 嘗試生成語音版本的問候語 - 只使用純問候語部分
            try:
                print("嘗試生成語音...")
                audio_message = self.text_to_speech(speech_greeting, user_id)
                
                # 修改後的訊息格式
                messages = [
                    TextSendMessage(
                        text=f"主題已設置為: {topic_icon} {display_name}"
                    ),
                    TextSendMessage(
                        text=display_greeting,
                        quick_reply=quick_reply
                    ),
                    audio_message
                ]
                
                self.line_bot_api.reply_message(reply_token, messages)
                print("成功發送帶語音的回覆")
            except Exception as audio_err:
                print(f"生成語音時發生錯誤: {str(audio_err)}")
                traceback.print_exc()
                
                # 如果無法生成語音，只發送文字
                messages = [
                    TextSendMessage(
                        text=f"主題已設置為: {topic_icon} {display_name}\n難度: {difficulty.capitalize()}"
                    ),
                    TextSendMessage(
                        text=display_greeting,
                        quick_reply=quick_reply
                    )
                ]
                
                self.line_bot_api.reply_message(reply_token, messages)
                print("成功發送純文字回覆")
            
            return "handled"
        except Exception as e:
            print(f"設置主題時發生錯誤: {str(e)}")
            traceback.print_exc()
            self.line_bot_api.reply_message(
                reply_token,
                TextSendMessage(text="設置主題時發生錯誤，請再試一次。")
            )

    def process_conversation(self, user_id, text, reply_token):
        try:
            # 獲取當前對話狀態
            session = self.user_sessions[user_id]
            topic = session.get('topic', '一般對話')
            difficulty = session.get('difficulty', 'intermediate')
            history = session.get('history', [])
            
            # 如果用戶請求重複上一句，尋找最後一條AI回應並轉語音重發
            if text.lower() in ["請再說一次", "please repeat", "say again", "repeat", "再說一次"]:
                last_ai_message = None
                last_speech_message = None
                
                for msg in reversed(history):
                    if msg['role'] == 'assistant':
                        last_ai_message = msg['content']
                        # 提取純對話部分
                        if "【" in last_ai_message and "\n" in last_ai_message:
                            parts = last_ai_message.split("\n", 1)
                            if len(parts) > 1:
                                last_speech_message = parts[1]
                        else:
                            last_speech_message = last_ai_message
                        break
                
                if last_ai_message:
                    try:
                        # 使用純對話部分生成語音
                        speech_content = last_speech_message or last_ai_message
                        audio_message = self.text_to_speech(speech_content, user_id)
                        messages = [
                            TextSendMessage(text=last_ai_message),
                            audio_message
                        ]
                        self.line_bot_api.reply_message(reply_token, messages)
                        return "handled"
                    except Exception as audio_err:
                        print(f"重複語音時發生錯誤: {str(audio_err)}")
                        self.line_bot_api.reply_message(
                            reply_token, 
                            TextSendMessage(text=last_ai_message)
                        )
                        return "handled"
            
            # 添加用戶訊息到歷史
            history.append({
                'role': 'user',
                'content': text
            })
            
            # 使用我們的創意問題生成函數生成下一個問題
            # 如果有定義
            if hasattr(self, 'generate_prompt'):
                try:
                    ai_response = self.generate_prompt(topic, difficulty, history)
                    # 如果沒有得到有效回應，回退到標準方法
                    if not ai_response:
                        ai_response = self.get_ai_response(user_id, text, topic, history)
                except Exception as prompt_err:
                    print(f"使用生成函數時發生錯誤: {str(prompt_err)}")
                    ai_response = self.get_ai_response(user_id, text, topic, history)
            else:
                # 否則使用標準方法
                ai_response = self.get_ai_response(user_id, text, topic, history)
            
            # 檢查是否包含場景描述，提取純對話內容用於語音
            speech_response = ai_response
            if "【" in ai_response and "\n" in ai_response:
                # 嘗試分離場景描述和實際對話內容
                parts = ai_response.split("\n", 1)
                if len(parts) > 1:
                    speech_response = parts[1]  # 只使用換行後的部分做語音
            
            # 添加AI回應到歷史
            history.append({
                'role': 'assistant',
                'content': ai_response
            })
            
            # 更新會話歷史
            session['history'] = history
            
            # 生成語音回應 - 只使用純對話部分
            try:
                audio_message = self.text_to_speech(speech_response, user_id)
                messages = [
                    TextSendMessage(text=ai_response),
                    audio_message
                ]
                self.line_bot_api.reply_message(reply_token, messages)
            except Exception as audio_err:
                print(f"生成語音時發生錯誤: {str(audio_err)}")
                # 如果無法生成語音，只發送文字
                self.line_bot_api.reply_message(reply_token, TextSendMessage(text=ai_response))
            
            return "handled"
        except Exception as e:
            print(f"處理對話時發生錯誤: {str(e)}")
            traceback.print_exc()
            self.line_bot_api.reply_message(
                reply_token,
                TextSendMessage(text="處理對話時發生錯誤，請再試一次。")
            )

    def end_conversation(self, user_id, reply_token):
        """結束當前對話並提供總結"""
        try:
            session = self.user_sessions.get(user_id)
            if not session or session.get('state') != 'in_conversation':
                self.line_bot_api.reply_message(
                    reply_token,
                    TextSendMessage(text="您目前沒有進行中的對話。")
                )
                return "handled"
            
            # 獲取對話歷史
            history = session.get('history', [])
            topic = session.get('topic', '一般對話')
            
            # 生成總結
            summary = self.generate_conversation_summary(user_id, history, topic)
            
            # 重置用戶狀態
            self.user_sessions[user_id] = {
                'state': 'init',
                'topic': None,
                'history': [],
                'difficulty': session.get('difficulty', 'intermediate')
            }
            
            # 發送總結
            self.line_bot_api.reply_message(
                reply_token,
                [
                    TextSendMessage(text="對話練習已結束。以下是您的表現總結："),
                    TextSendMessage(text=summary),
                    TextSendMessage(
                        text="您想再次開始對話練習嗎？",
                        quick_reply=QuickReply(items=[
                            QuickReplyButton(action=MessageAction(label="開始對話", text="#start_conversation")),
                            QuickReplyButton(action=MessageAction(label="返回主選單", text="#menu"))
                        ])
                    )
                ]
            )
            return "handled"
        except Exception as e:
            print(f"結束對話時發生錯誤: {str(e)}")
            traceback.print_exc()
            self.line_bot_api.reply_message(
                reply_token,
                TextSendMessage(text="結束對話時發生錯誤，請再試一次。")
            )

    def show_help(self, reply_token):
        """顯示幫助訊息"""
        help_text = (
            "📚 對話練習幫助 📚\n\n"
            "基本命令:\n"
            "- #start_conversation: 開始新對話\n"
            "- #topic [主題名稱]: 設置對話主題\n"
            "- #level [beginner/intermediate/advanced]: 設置難度\n"
            "- #end_conversation: 結束當前對話\n"
            "- #help: 顯示此幫助\n"
            "- #menu: 返回主選單\n\n"
            "使用提示:\n"
            "- 您可以使用文字或語音進行回覆\n"
            "- 對話主題可自由調整\n"
            "- 系統會記錄對話歷史並在結束時給予評估\n"
            "- 如果想聽AI重複最後一句話，可以輸入 \"請再說一次\""
        )
        
        self.line_bot_api.reply_message(
            reply_token,
            TextSendMessage(
                text=help_text,
                quick_reply=QuickReply(items=[
                    QuickReplyButton(action=MessageAction(label="開始對話", text="#start_conversation")),
                    QuickReplyButton(action=MessageAction(label="結束對話", text="#end_conversation")),
                    QuickReplyButton(action=MessageAction(label="返回主選單", text="#menu"))
                ])
            )
        )
        return "handled"

    def get_ai_response(self, user_id, user_text, topic, history):
        """獲取AI回應"""
        try:
            # 嘗試使用 OpenAI API
            openai_api_key = os.getenv('OPENAI_API_KEY')
            if openai_api_key:
                return self.get_openai_response(user_text, history, openai_api_key)
            else:
                return self.get_fallback_response(user_id, user_text, topic)
        except Exception as e:
            print(f"獲取AI回應時發生錯誤: {str(e)}")
            return self.get_fallback_response(user_id, user_text, topic)

    def get_openai_response(self, user_text, history, api_key):
        try:
            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json"
            }
            
            # 準備訊息歷史
            messages = []
            for msg in history:
                if msg['role'] == 'system':
                    # 強化系統提示，添加簡短回覆的指令
                    system_content = msg['content'] + "\n\nIMPORTANT: Keep your responses short and conversational. Aim for 1-3 sentences maximum. Be natural and friendly, but brief. This is a casual conversation, not a detailed explanation."
                    messages.append({
                        "role": "system",
                        "content": system_content
                    })
                else:
                    messages.append({
                        "role": msg['role'],
                        "content": msg['content']
                    })
            
            # 如果沒有系統訊息，添加一個強化的默認系統提示
            if not any(msg['role'] == 'system' for msg in messages):
                messages.insert(0, {
                    "role": "system",
                    "content": "You are a real person in a casual conversation. Keep responses short (1-3 sentences). Be natural and friendly. NEVER mention being an AI or this being language practice."
                })
            
            # 調整參數以增加回應自然度並限制長度
            payload = {
                "model": "gpt-3.5-turbo",
                "messages": messages,
                "temperature": 0.85,  # 增加變異性
                "presence_penalty": 0.7,  # 增加回應多樣性
                "frequency_penalty": 0.5,  # 減少重複表達
                "max_tokens": 50  # 減少到50，限制回應長度
            }
            
            response = requests.post(
                "https://api.openai.com/v1/chat/completions",
                headers=headers,
                data=json.dumps(payload)
            )
            
            if response.status_code == 200:
                response_content = response.json()['choices'][0]['message']['content'].strip()
                return response_content
            else:
                print(f"OpenAI API 錯誤: {response.status_code}, {response.text}")
                raise Exception("API請求失敗")
        except Exception as e:
            print(f"使用OpenAI API時發生錯誤: {str(e)}")
            traceback.print_exc()
            raise

    def generate_conversation_summary(self, user_id, history, topic):
        """生成對話總結和評估"""
        try:
            # 嘗試使用OpenAI API
            openai_api_key = os.getenv('OPENAI_API_KEY')
            if openai_api_key:
                return self.get_openai_summary(history, openai_api_key)
            else:
                return self.get_fallback_summary(history, topic)
        except Exception as e:
            print(f"生成對話總結時發生錯誤: {str(e)}")
            return self.get_fallback_summary(history, topic)

    def get_openai_summary(self, history, api_key):
        """使用OpenAI API生成對話總結"""
        try:
            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json"
            }
            
            # 構建提示
            conversation_text = ""
            for msg in history:
                if msg['role'] != 'system':
                    prefix = "Assistant: " if msg['role'] == 'assistant' else "User: "
                    conversation_text += f"{prefix}{msg['content']}\n"
            
            prompt = (
                "Please analyze the following English conversation and provide feedback:\n\n"
                f"{conversation_text}\n\n"
                "Provide a summary with:\n"
                "1. Overall assessment of the user's English skills\n"
                "2. Strengths demonstrated in the conversation\n"
                "3. Areas for improvement\n"
                "4. Suggestions for further practice\n"
                "Be encouraging and constructive. Format the response clearly with sections."
            )
            
            payload = {
                "model": "gpt-3.5-turbo",
                "messages": [
                    {"role": "system", "content": "You are an English teacher providing feedback on conversations."},
                    {"role": "user", "content": prompt}
                ],
                "temperature": 0.7,
                "max_tokens": 500
            }
            
            response = requests.post(
                "https://api.openai.com/v1/chat/completions",
                headers=headers,
                data=json.dumps(payload)
            )
            
            if response.status_code == 200:
                return response.json()['choices'][0]['message']['content'].strip()
            else:
                print(f"OpenAI API 錯誤: {response.status_code}, {response.text}")
                raise Exception("API請求失敗")
        except Exception as e:
            print(f"使用OpenAI API生成總結時發生錯誤: {str(e)}")
            raise

    def get_fallback_summary(self, history, topic):
        """如果API不可用，提供基本的對話總結"""
        # 計算用戶訊息數量
        user_messages = [msg for msg in history if msg['role'] == 'user']
        user_message_count = len(user_messages)
        
        # 計算平均用戶訊息長度
        total_length = sum(len(msg['content']) for msg in user_messages)
        avg_length = total_length / user_message_count if user_message_count > 0 else 0
        
        # 評估參與度
        if user_message_count >= 10:
            engagement = "excellent"
        elif user_message_count >= 7:
            engagement = "very good"
        elif user_message_count >= 5:
            engagement = "good"
        elif user_message_count >= 3:
            engagement = "fair"
        else:
            engagement = "needs improvement"
        
        # 評估表達能力
        if avg_length >= 50:
            expression = "excellent"
        elif avg_length >= 30:
            expression = "very good"
        elif avg_length >= 20:
            expression = "good"
        elif avg_length >= 10:
            expression = "fair"
        else:
            expression = "needs improvement"
        
        summary = (
            f"📊 對話練習總結 📊\n\n"
            f"主題: {topic}\n"
            f"對話長度: {user_message_count} 次回覆\n\n"
            "整體評估:\n"
            f"- 參與度: {engagement.capitalize()}\n"
            f"- 表達能力: {expression.capitalize()}\n\n"
            "優點:\n"
            "- 您積極參與對話\n"
            "- 您能夠圍繞主題進行討論\n\n"
            "改進建議:\n"
            "- 嘗試使用更多詞彙和不同的句型\n"
            "- 練習提出更多開放式問題\n"
            "- 繼續增加回覆的長度和深度\n\n"
            "學習建議:\n"
            "- 每天固定練習英語對話\n"
            "- 嘗試閱讀與此主題相關的英語文章\n"
            "- 聆聽英語播客或觀看英語影片來提升聽力和表達能力\n\n"
            "感謝您參與對話練習！持續練習是提升英語能力的關鍵。"
        )
        
        return summary
        
    def text_to_speech(self, text, user_id):
        """將文字轉換為語音並返回音頻訊息"""
        try:
            # 生成唯一的文件名
            timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
            audio_filename = f"conversation_{user_id}_{timestamp}.mp3"
            
            # 完整的音頻文件路徑
            audio_file_path = os.path.join(self.static_audio_folder, audio_filename)
            
            # 使用 gTTS 生成音頻
            tts = gTTS(text=text, lang='en')
            tts.save(audio_file_path)
            
            # 計算音頻時長
            try:
                audio = MP3(audio_file_path)
                duration = int(audio.info.length * 1000)  # 轉換為毫秒
            except Exception as e:
                print(f"計算音頻時長時發生錯誤: {str(e)}")
                duration = 5000  # 默認 5 秒
            
            # 創建音頻 URL
            audio_url = f"{self.base_url}/static/audio/{audio_filename}"
            
            # 返回音頻訊息
            return AudioSendMessage(original_content_url=audio_url, duration=duration)
        except Exception as e:
            print(f"生成語音訊息時發生錯誤: {str(e)}")
            traceback.print_exc()
            raise