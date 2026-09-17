import os
import json
import requests
import tempfile
from datetime import datetime
from gtts import gTTS
from mutagen.mp3 import MP3
from linebot.models import (
    TextSendMessage, AudioSendMessage, QuickReply, 
    QuickReplyButton, MessageAction
)

class ConversationService:
    def __init__(self, line_bot_api, handler=None):
        self.line_bot_api = line_bot_api
        self.handler = handler
        self.user_sessions = {}
        self._setup_directories()
        self._setup_topics()
        self._init_whisper()
        self._setup_base_url()

    def _setup_directories(self):
        # 設置音檔目錄
        current_dir = os.path.dirname(__file__)
        self.audio_folder = os.path.join(current_dir, 'audio')
        os.makedirs(self.audio_folder, exist_ok=True)
        
        # 啟動時清理舊音檔
        self._cleanup_old_audio_files()

    def _cleanup_old_audio_files(self):
        # 清理超過1小時的音檔
        try:
            import time
            current_time = time.time()
            for filename in os.listdir(self.audio_folder):
                if filename.endswith('.mp3'):
                    file_path = os.path.join(self.audio_folder, filename)
                    file_time = os.path.getmtime(file_path)
                    # 刪除超過1小時的檔案
                    if current_time - file_time > 3600:
                        os.remove(file_path)
                        print(f"刪除舊音檔: {filename}")
        except Exception as e:
            print(f"清理音檔錯誤: {e}")

    def _setup_topics(self):
        # 只保留點餐和興趣兩個主題
        self.TOPICS = {
            'restaurant': {
                'icon': '🍽️',
                'name': '點餐',
                'prompt': 'You are helping practice English conversation at a restaurant. Keep responses short and natural.',
                'greeting': 'Welcome to our restaurant! What would you like to order today?'
            },
            'hobbies': {
                'icon': '🎯',
                'name': '興趣愛好',
                'prompt': 'You are helping practice English conversation about hobbies and interests. Keep responses short and natural.',
                'greeting': 'Hi there! What hobbies or interests do you enjoy in your free time?'
            }
        }

    def _init_whisper(self):
        # 初始化 Whisper 語音識別
        try:
            import whisper
            self.whisper_model = whisper.load_model("tiny")
            self.using_whisper = True
        except ImportError:
            self.using_whisper = False

    def _setup_base_url(self):
        # 設置外部 URL
        self.base_url = os.getenv('TUNNEL_URL') or os.getenv('NGROK_URL') or "http://localhost:5000"
        self.base_url = self.base_url.rstrip('/')

    def handle_text_message(self, event):
        try:
            user_id = event.source.user_id
            text = event.message.text.strip()
            reply_token = event.reply_token
            
            # 初始化用戶會話
            if user_id not in self.user_sessions:
                self.user_sessions[user_id] = {
                    'state': 'init',
                    'topic': None,
                    'history': []
                }
            
            session = self.user_sessions[user_id]
            
            # 處理命令
            if text == '#start_conversation':
                return self.show_topic_menu(reply_token)
            elif text.startswith('#topic_'):
                topic = text[7:]
                return self.set_topic(user_id, topic, reply_token)
            elif text == '#end_conversation':
                return self.end_conversation(user_id, reply_token)
            
            # 根據狀態處理
            if session['state'] == 'init':
                return self.show_topic_menu(reply_token)
            elif session['state'] == 'in_conversation':
                return self.process_conversation(user_id, text, reply_token)
                
        except Exception as e:
            print(f"處理文字訊息錯誤: {e}")
            self.line_bot_api.reply_message(reply_token, 
                TextSendMessage(text="處理訊息時發生錯誤"))

    def handle_audio_message(self, user_id, audio_file_path, event=None):
        # 處理語音訊息
        if not self.using_whisper:
            return TextSendMessage(text="語音功能未啟用，請使用文字輸入")
        
        try:
            # 語音轉文字
            result = self.whisper_model.transcribe(audio_file_path)
            user_text = result["text"]
            
            # 處理對話
            session = self.user_sessions.get(user_id, {})
            if session.get('state') != 'in_conversation':
                return TextSendMessage(text="請先選擇對話主題")
            
            # 獲取 AI 回應
            ai_response = self.get_ai_response(user_text, session['history'])
            
            # 更新歷史
            session['history'].extend([
                {'role': 'user', 'content': user_text},
                {'role': 'assistant', 'content': ai_response}
            ])
            
            # 生成語音回覆
            audio_message = self.text_to_speech(ai_response, user_id)
            return [
                TextSendMessage(text=f"我聽到: {user_text}"),
                TextSendMessage(text=ai_response),
                audio_message
            ]
            
        except Exception as e:
            print(f"處理語音錯誤: {e}")
            return TextSendMessage(text="語音處理失敗")

    def show_topic_menu(self, reply_token):
        # 顯示主題選擇選單
        items = []
        for topic_id, topic_info in self.TOPICS.items():
            items.append(QuickReplyButton(
                action=MessageAction(
                    label=f"{topic_info['icon']} {topic_info['name']}", 
                    text=f"#topic_{topic_id}"
                )
            ))
        
        self.line_bot_api.reply_message(reply_token,
            TextSendMessage(
                text="請選擇對話主題：",
                quick_reply=QuickReply(items=items)
            ))
        return "handled"

    def set_topic(self, user_id, topic, reply_token):
        # 設置對話主題
        if topic not in self.TOPICS:
            return self.show_topic_menu(reply_token)
        
        topic_info = self.TOPICS[topic]
        
        # 更新用戶狀態
        self.user_sessions[user_id] = {
            'state': 'in_conversation',
            'topic': topic,
            'history': [
                {'role': 'system', 'content': topic_info['prompt']},
                {'role': 'assistant', 'content': topic_info['greeting']}
            ]
        }
        
        # 發送歡迎訊息和語音
        try:
            audio_message = self.text_to_speech(topic_info['greeting'], user_id)
            messages = [
                TextSendMessage(text=f"開始 {topic_info['icon']} {topic_info['name']} 對話"),
                TextSendMessage(text=topic_info['greeting']),
                audio_message
            ]
        except:
            messages = [
                TextSendMessage(text=f"開始 {topic_info['icon']} {topic_info['name']} 對話"),
                TextSendMessage(text=topic_info['greeting'])
            ]
        
        self.line_bot_api.reply_message(reply_token, messages)
        return "handled"

    def process_conversation(self, user_id, text, reply_token):
        # 處理對話內容
        session = self.user_sessions[user_id]
        
        # 添加用戶訊息
        session['history'].append({'role': 'user', 'content': text})
        
        # 獲取 AI 回應
        ai_response = self.get_ai_response(text, session['history'])
        
        # 添加 AI 回應
        session['history'].append({'role': 'assistant', 'content': ai_response})
        
        # 發送回覆
        try:
            audio_message = self.text_to_speech(ai_response, user_id)
            messages = [TextSendMessage(text=ai_response), audio_message]
        except:
            messages = [TextSendMessage(text=ai_response)]
        
        self.line_bot_api.reply_message(reply_token, messages)
        return "handled"

    def end_conversation(self, user_id, reply_token):
        # 結束對話
        if user_id in self.user_sessions:
            del self.user_sessions[user_id]
        
        self.line_bot_api.reply_message(reply_token,
            TextSendMessage(text="對話練習已結束，謝謝參與！"))
        return "handled"

    def get_ai_response(self, user_text, history):
        # 獲取 AI 回應
        openai_api_key = os.getenv('OPENAI_API_KEY')
        if not openai_api_key:
            return "Sorry, I can't respond right now."
        
        try:
            headers = {
                "Authorization": f"Bearer {openai_api_key}",
                "Content-Type": "application/json"
            }
            
            # 準備訊息
            messages = []
            for msg in history:
                messages.append({
                    "role": msg['role'],
                    "content": msg['content']
                })
            
            payload = {
                "model": "gpt-3.5-turbo",
                "messages": messages,
                "temperature": 0.7,
                "max_tokens": 100  # 限制回應長度
            }
            
            response = requests.post(
                "https://api.openai.com/v1/chat/completions",
                headers=headers,
                json=payload
            )
            
            if response.status_code == 200:
                return response.json()['choices'][0]['message']['content'].strip()
            else:
                return "Sorry, I'm having trouble responding."
                
        except Exception as e:
            print(f"OpenAI API 錯誤: {e}")
            return "Sorry, I can't respond right now."

    def text_to_speech(self, text, user_id):
        # 文字轉語音
        try:
            timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
            audio_filename = f"conv_{user_id}_{timestamp}.mp3"
            audio_file_path = os.path.join(self.audio_folder, audio_filename)
            
            # 生成語音
            tts = gTTS(text=text, lang='en')
            tts.save(audio_file_path)
            
            # 計算時長
            try:
                audio = MP3(audio_file_path)
                duration = int(audio.info.length * 1000)
            except:
                duration = 5000
            
            # 創建 URL - 使用相對路徑
            audio_url = f"{self.base_url}/static/conversation_audio/{audio_filename}"
            
            # 定時清理 - 每次生成新音檔時清理舊檔
            self._cleanup_old_audio_files()
            
            return AudioSendMessage(original_content_url=audio_url, duration=duration)
            
        except Exception as e:
            print(f"生成語音錯誤: {e}")
            raise