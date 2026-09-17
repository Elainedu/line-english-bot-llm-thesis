import os
import time
from dotenv import load_dotenv
from flask import Flask, request, abort, send_from_directory
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import (
    MessageEvent, TextMessage, TextSendMessage, AudioMessage,
    QuickReplyButton, QuickReply, MessageAction
)
import openai
from gtts import gTTS
from prompts.menu_prompts import MAIN_TOPICS, TOPIC_PROMPTS

# Load environment variables
load_dotenv()

app = Flask(__name__)

# LINE Bot setup
line_bot_api = LineBotApi(os.getenv('LINE_CHANNEL_ACCESS_TOKEN'))
handler = WebhookHandler(os.getenv('LINE_CHANNEL_SECRET'))

# OpenAI setup
openai.api_key = os.getenv('OPENAI_API_KEY')

# Audio files directory setup
AUDIO_FOLDER = 'audio_files'
if not os.path.exists(AUDIO_FOLDER):
    os.makedirs(AUDIO_FOLDER)

# Get NGROK URL from environment variable
NGROK_URL = os.getenv('NGROK_URL')
if not NGROK_URL:
    raise ValueError("NGROK_URL not found in environment variables")

# User sessions storage
user_sessions = {}

def create_topic_menu():
    """Create topic selection menu"""
    try:
        items = []
        for topic, data in MAIN_TOPICS.items():
            items.append(
                QuickReplyButton(
                    action=MessageAction(
                        label=f"{data['icon']} {topic}",
                        text=f"#topic {topic}"
                    )
                )
            )
        return QuickReply(items=items)
    except Exception as e:
        print(f"Error creating topic menu: {str(e)}")
        return None

def create_level_menu(topic):
    """Create difficulty level menu"""
    try:
        items = []
        for level in MAIN_TOPICS[topic]['levels']:
            items.append(
                QuickReplyButton(
                    action=MessageAction(
                        label=f"{level}",
                        text=f"#level {topic} {level}"
                    )
                )
            )
        items.append(
            QuickReplyButton(
                action=MessageAction(
                    label="↩️ Back to Menu",
                    text="menu"
                )
            )
        )
        return QuickReply(items=items)
    except Exception as e:
        print(f"Error creating level menu: {str(e)}")
        return None

@app.route('/audio/<filename>')
def serve_audio(filename):
    """Serve audio files"""
    return send_from_directory(AUDIO_FOLDER, filename)

@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    """Handle user messages"""
    try:
        user_id = event.source.user_id
        text = event.message.text.strip()
        
        print(f"Received message: {text}")

        # Handle menu request
        if text.lower() in ['menu', 'start']:
            quick_reply = create_topic_menu()
            if quick_reply:
                line_bot_api.reply_message(
                    event.reply_token,
                    TextSendMessage(
                        text="Please select a topic to practice:",
                        quick_reply=quick_reply
                    )
                )
            return

        # Handle topic selection
        if text.startswith('#topic'):
            _, topic = text.split(' ', 1)
            print(f"Selected topic: {topic}")
            quick_reply = create_level_menu(topic)
            if quick_reply:
                line_bot_api.reply_message(
                    event.reply_token,
                    TextSendMessage(
                        text=f"Select difficulty level for {topic}:",
                        quick_reply=quick_reply
                    )
                )
            return

        # Handle level selection
        if text.startswith('#level'):
            try:
                parts = text.split(' ')
                topic = ' '.join(parts[1:-1])
                level = parts[-1]
                
                if topic in TOPIC_PROMPTS and level in TOPIC_PROMPTS[topic]:
                    user_sessions[user_id] = {
                        'topic': topic,
                        'level': level,
                        'prompt': TOPIC_PROMPTS[topic][level]['prompt']
                    }
                    
                    line_bot_api.reply_message(
                        event.reply_token,
                        [
                            TextSendMessage(text=f"Selected: {topic} ({level})"),
                            TextSendMessage(
                                text="You can start the conversation now! Type anything to begin.",
                                quick_reply=QuickReply(items=[
                                    QuickReplyButton(
                                        action=MessageAction(
                                            label="Back to Menu",
                                            text="menu"
                                        )
                                    )
                                ])
                            )
                        ]
                    )
                else:
                    raise ValueError(f"Invalid topic ({topic}) or level ({level})")
            except Exception as e:
                print(f"Error processing level selection: {str(e)}")
                quick_reply = create_topic_menu()
                line_bot_api.reply_message(
                    event.reply_token,
                    TextSendMessage(
                        text="Sorry, invalid selection. Please try again:",
                        quick_reply=quick_reply
                    )
                )
                return

        # Handle general conversation
        if user_id not in user_sessions:
            quick_reply = create_topic_menu()
            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(
                    text="Please select a topic first:",
                    quick_reply=quick_reply
                )
            )
            return

        # OpenAI response
        print("Calling OpenAI API...")
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": user_sessions[user_id]['prompt']},
                {"role": "user", "content": text}
            ]
        )
        response_text = response.choices[0].message['content']
        
        # Convert text to speech
        tts = gTTS(text=response_text, lang='en')
        
        # Generate unique filename
        audio_filename = f"audio_{user_id}_{int(time.time())}.mp3"
        audio_path = os.path.join(AUDIO_FOLDER, audio_filename)
        
        # Save audio file
        tts.save(audio_path)
        
        # Generate audio URL
        audio_url = f"{NGROK_URL}/audio/{audio_filename}"
        
        # Send response
        line_bot_api.reply_message(
            event.reply_token,
            [
                AudioMessage(
                    original_content_url=audio_url,
                    duration=300000  # 300 seconds
                ),
                TextSendMessage(
                    text=response_text,
                    quick_reply=QuickReply(items=[
                        QuickReplyButton(
                            action=MessageAction(
                                label="Change Topic",
                                text="menu"
                            )
                        )
                    ])
                )
            ]
        )

    except Exception as e:
        print(f"Error in handle_message: {str(e)}")
        import traceback
        print(traceback.format_exc())
        try:
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
        except Exception as e2:
            print(f"Error sending error message: {str(e2)}")

@app.route("/callback", methods=['GET', 'POST'])
def callback():
    """Handle LINE Webhook"""
    if request.method == 'GET':
        return 'OK'
    
    signature = request.headers['X-Line-Signature']
    body = request.get_data(as_text=True)
    
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        print("Invalid signature!")
        abort(400)
    except Exception as e:
        print(f"Error handling webhook: {str(e)}")
        abort(400)
    return 'OK'

@app.route("/")
def home():
    return 'LINE Bot is running!'

@app.before_request
def before_request():
    """Clean up old audio files before each request"""
    try:
        current_time = time.time()
        for filename in os.listdir(AUDIO_FOLDER):
            file_path = os.path.join(AUDIO_FOLDER, filename)
            # Clean up files older than 1 hour
            if os.path.getmtime(file_path) < current_time - 3600:
                os.remove(file_path)
    except Exception as e:
        print(f"Error cleaning up audio files: {str(e)}")

if __name__ == "__main__":
    print("=== Starting LINE Bot ===")
    print("Checking configurations...")
    print(f"LINE Channel Access Token length: {len(os.getenv('LINE_CHANNEL_ACCESS_TOKEN'))}")
    print(f"LINE Channel Secret length: {len(os.getenv('LINE_CHANNEL_SECRET'))}")
    print(f"OpenAI API Key length: {len(os.getenv('OPENAI_API_KEY'))}")
    print(f"NGROK URL: {NGROK_URL}")
    app.run(debug=True, port=5000)