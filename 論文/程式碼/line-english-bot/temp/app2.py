import os
import sys
import uuid
import time
import threading
import requests
from dotenv import load_dotenv
from flask import Flask, request, abort, send_file
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import (
    MessageEvent, TextMessage, TextSendMessage, AudioMessage,
    QuickReplyButton, QuickReply, MessageAction
)
from openai import OpenAI
from gtts import gTTS
import tempfile
import logging
from datetime import datetime, timedelta
from prompts.menu_prompts import MAIN_TOPICS, TOPIC_PROMPTS

# 設定日誌
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# 載入環境變數
load_dotenv()

app = Flask(__name__)

# 初始化 API 客戶端
line_bot_api = LineBotApi(os.getenv('LINE_CHANNEL_ACCESS_TOKEN'))
handler = WebhookHandler(os.getenv('LINE_CHANNEL_SECRET'))
client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
NGROK_URL = os.getenv('NGROK_URL')

class SessionManager:
    def __init__(self, timeout_minutes=30):
        self.sessions = {}
        self.timeout = timedelta(minutes=timeout_minutes)
    
    def get_session(self, user_id):
        if user_id in self.sessions:
            session_data, timestamp = self.sessions[user_id]
            if datetime.now() - timestamp < self.timeout:
                self.sessions[user_id] = (session_data, datetime.now())
                return session_data
            else:
                del self.sessions[user_id]
        return None
    
    def set_session(self, user_id, session_data):
        self.sessions[user_id] = (session_data, datetime.now())
    
    def clear_session(self, user_id):
        if user_id in self.sessions:
            del self.sessions[user_id]

session_manager = SessionManager()

# 預設設定
DEFAULT_TOPIC = "Business"
DEFAULT_LEVEL = "Beginner"

def get_default_session():
    return {
        'topic': DEFAULT_TOPIC,
        'level': DEFAULT_LEVEL,
        'prompt': TOPIC_PROMPTS[DEFAULT_TOPIC][DEFAULT_LEVEL]['prompt'],
        'conversation_history': []
    }

# 測試路由
@app.route("/test-audio")
def test_audio():
    try:
        test_text = "This is a test audio message."
        test_file = os.path.join("temp_audio", "test.mp3")
        
        tts = gTTS(text=test_text, lang='en')
        tts.save(test_file)
        
        return send_file(test_file, mimetype="audio/mp3")
    except Exception as e:
        return str(e), 500

@app.route("/audio/<filename>")
def serve_audio(filename):
    try:
        # 安全檢查檔名
        if '..' in filename or filename.startswith('/'):
            abort(404)
            
        # 構建完整路徑
        filepath = os.path.join("temp_audio", filename)
        
        if not os.path.exists(filepath):
            logger.error(f"Audio file not found: {filepath}")
            abort(404)
            
        # 設定正確的 MIME 類型和標頭
        response = send_file(
            filepath,
            mimetype='audio/mpeg',
            as_attachment=False
        )
        
        # 添加必要的標頭
        response.headers['Content-Type'] = 'audio/mpeg'
        response.headers['Accept-Ranges'] = 'bytes'
        
        return response
        
    except Exception as e:
        logger.error(f"Error serving audio file: {str(e)}")
        abort(500)

def send_voice_response(text, user_id):
    try:
        # 確保目錄存在
        audio_dir = "temp_audio"
        os.makedirs(audio_dir, exist_ok=True)
        
        # 生成唯一檔名
        audio_filename = f"audio_{uuid.uuid4()}.mp3"
        filepath = os.path.join(audio_dir, audio_filename)
        
        try:
            # 生成語音檔案
            tts = gTTS(text=text, lang='en', slow=False)
            tts.save(filepath)
            
            if not os.path.exists(filepath):
                raise FileNotFoundError(f"Audio file not created: {filepath}")
            
            file_size = os.path.getsize(filepath)
            logger.info(f"Audio file size: {file_size} bytes")
            
            if file_size == 0:
                raise ValueError("Audio file is empty")
            
            # 構建 URL
            clean_ngrok_url = NGROK_URL.rstrip('/')
            audio_url = f"{clean_ngrok_url}/audio/{audio_filename}"
            logger.info(f"Audio URL: {audio_url}")
            
            # 使用字典方式構建訊息
            message = {
                "to": user_id,
                "messages": [{
                    "type": "audio",
                    "originalContentUrl": audio_url,
                    "duration": 5000
                }]
            }
            
            # 直接使用 POST 請求
            line_bot_api._post(
                '/v2/bot/message/push',
                data=message
            )
            
            logger.info("Audio message sent successfully")
            
        finally:
            # 設定定時刪除檔案
            def delete_file():
                time.sleep(300)  # 5分鐘後刪除
                try:
                    if os.path.exists(filepath):
                        os.remove(filepath)
                        logger.info(f"Deleted audio file: {filepath}")
                except Exception as e:
                    logger.error(f"Error deleting audio file: {str(e)}")
            
            threading.Thread(target=delete_file, daemon=True).start()
            
    except Exception as e:
        logger.error(f"Error in voice response: {str(e)}", exc_info=True)
        try:
            line_bot_api.push_message(
                user_id,
                TextSendMessage(text="Sorry, voice response failed. Please try again.")
            )
        except:
            pass

def create_topic_menu():
    try:
        items = [
            QuickReplyButton(action=MessageAction(
                label=f"{data['icon']} {topic}"[:20],
                text=f"#topic {topic}"
            ))
            for topic, data in MAIN_TOPICS.items()
        ]
        return QuickReply(items=items[:13])
    except Exception as e:
        logger.error(f"Error creating topic menu: {str(e)}")
        return None

def create_level_menu(topic):
    try:
        items = [
            QuickReplyButton(action=MessageAction(
                label=level,
                text=f"#level {topic} {level}"
            ))
            for level in MAIN_TOPICS[topic]['levels']
        ]
        items.append(QuickReplyButton(
            action=MessageAction(label="↩️ Menu", text="menu")
        ))
        return QuickReply(items=items[:13])
    except Exception as e:
        logger.error(f"Error creating level menu: {str(e)}")
        return None

def get_openai_response(prompt, user_message, conversation_history=None):
    try:
        messages = [{"role": "system", "content": prompt}]
        if conversation_history:
            messages.extend(conversation_history[-6:])
        messages.append({"role": "user", "content": user_message})
        
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=messages,
            max_tokens=300,
            temperature=0.7
        )
        return response.choices[0].message.content
    except Exception as e:
        logger.error(f"OpenAI API error: {str(e)}")
        raise

@handler.add(MessageEvent, message=AudioMessage)
def handle_audio_message(event):
    try:
        message_content = line_bot_api.get_message_content(event.message.id)
        with tempfile.NamedTemporaryFile(delete=False, suffix='.wav') as f:
            for chunk in message_content.iter_content():
                f.write(chunk)
            temp_path = f.name

        try:
            # 使用 Whisper 將語音轉換為文字
            with open(temp_path, "rb") as audio_file:
                transcript = client.audio.transcriptions.create(
                    model="whisper-1",
                    file=audio_file,
                    language="en"
                )
            
            user_id = event.source.user_id
            session_data = session_manager.get_session(user_id)

            if not session_data:
                session_data = get_default_session()
                session_manager.set_session(user_id, session_data)

            # 獲取 AI 回應
            text_response = get_openai_response(
                session_data['prompt'],
                transcript.text,
                session_data.get('conversation_history')
            )

            # 發送文字回應
            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(
                    text=f"I heard: {transcript.text}\n\n{text_response}",
                    quick_reply=QuickReply(items=[
                        QuickReplyButton(
                            action=MessageAction(label="Change Topic", text="menu")
                        )
                    ])
                )
            )

            # 生成並發送語音回應
            send_voice_response(text_response, user_id)

            # 更新對話歷史
            session_data['conversation_history'].extend([
                {"role": "user", "content": transcript.text},
                {"role": "assistant", "content": text_response}
            ])
            session_manager.set_session(user_id, session_data)

        finally:
            try:
                os.remove(temp_path)
            except:
                pass

    except Exception as e:
        logger.error(f"Error handling audio message: {str(e)}")
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text="Sorry, I couldn't process your voice message.")
        )

@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    user_id = event.source.user_id
    text = event.message.text.strip()
    
    try:
        if text.lower() in ['menu', 'start']:
            session_manager.clear_session(user_id)
            quick_reply = create_topic_menu()
            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(
                    text="Choose a topic to practice:",
                    quick_reply=quick_reply
                )
            )
            return

        if text.startswith('#topic'):
            _, topic = text.split(' ', 1)
            quick_reply = create_level_menu(topic)
            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(
                    text=f"Select difficulty for {topic}:",
                    quick_reply=quick_reply
                )
            )
            return

        if text.startswith('#level'):
            parts = text.split(' ')
            topic = ' '.join(parts[1:-1])
            level = parts[-1]
            
            session_data = {
                'topic': topic,
                'level': level,
                'prompt': TOPIC_PROMPTS[topic][level]['prompt'],
                'conversation_history': []
            }
            session_manager.set_session(user_id, session_data)
            
            response_text = f"Ready to practice {topic} ({level} level)! Type anything to begin."
            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(text=response_text)
            )
            return

        session_data = session_manager.get_session(user_id)
        if not session_data:
            session_data = get_default_session()
            session_manager.set_session(user_id, session_data)

        text_response = get_openai_response(
            session_data['prompt'],
            text,
            session_data.get('conversation_history')
        )
        
        # 發送文字回應
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(
                text=text_response,
                quick_reply=QuickReply(items=[
                    QuickReplyButton(
                        action=MessageAction(
                            label="Change Topic",
                            text="menu"
                        )
                    )
                ])
            )
        )
        
        # 生成並發送語音回應
        send_voice_response(text_response, user_id)
        
        # 更新對話歷史
        session_data['conversation_history'].extend([
            {"role": "user", "content": text},
            {"role": "assistant", "content": text_response}
        ])
        session_manager.set_session(user_id, session_data)

    except Exception as e:
        logger.error(f"Error in handle_message: {str(e)}", exc_info=True)
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(
                text="Sorry, something went wrong. Please try again.",
                quick_reply=QuickReply(items=[
                    QuickReplyButton(
                        action=MessageAction(
                            label="Back to Menu",
                            text="menu"
                        )
                    )
                ])
            )
        )

@app.route("/callback", methods=['POST'])
def callback():
    signature = request.headers['X-Line-Signature']
    body = request.get_data(as_text=True)
    
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)
    return 'OK'

@app.route("/")
def home():
    return 'LINE Bot is running!'

def cleanup_old_files():
    while True:
        try:
            current_time = datetime.now()
            audio_dir = "temp_audio"
            
            if os.path.exists(audio_dir):
                for filename in os.listdir(audio_dir):
                    filepath = os.path.join(audio_dir, filename)
                    file_time = datetime.fromtimestamp(os.path.getctime(filepath))
                    
                    # 如果檔案超過10分鐘就刪除
                    if (current_time - file_time) > timedelta(minutes=10):
                        try:
                            os.remove(filepath)
                            logger.info(f"Cleaned up old audio file: {filepath}")
                        except Exception as e:
                            logger.error(f"Error cleaning up file: {str(e)}")
            
            time.sleep(300)  # 每5分鐘檢查一次
            
        except Exception as e:
            logger.error(f"Error in cleanup task: {str(e)}")
            time.sleep(300)

if __name__ == "__main__":
    logger.info("=== Starting LINE Bot ===")
    
    # 驗證 NGROK_URL
    if not NGROK_URL or not NGROK_URL.startswith('https://'):
        logger.error("Invalid NGROK_URL. Must start with https://")
        sys.exit(1)
    
    # 移除結尾的斜線
    NGROK_URL = NGROK_URL.rstrip('/')
    
    # 建立 temp_audio 目錄
    os.makedirs("temp_audio", exist_ok=True)
    
    # 設定 Flask
    app.run(host='0.0.0.0', port=5000, debug=True)