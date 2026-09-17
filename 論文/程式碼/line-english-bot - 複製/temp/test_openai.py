import os
from dotenv import load_dotenv
from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import (
    MessageEvent, TextMessage, TextSendMessage,
    QuickReplyButton, QuickReply, MessageAction
)
import openai
from prompts.menu_prompts import MAIN_TOPICS, TOPIC_PROMPTS

# 載入環境變數
load_dotenv()

app = Flask(__name__)

# 設定 LINE Bot 認證
line_bot_api = LineBotApi(os.getenv('LINE_CHANNEL_ACCESS_TOKEN'))
handler = WebhookHandler(os.getenv('LINE_CHANNEL_SECRET'))

# 設定 OpenAI API
openai.api_key = os.getenv('OPENAI_API_KEY')

# 儲存使用者狀態
user_sessions = {}

def create_topic_menu():
    """創建主題選單"""
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
    """創建難度選單"""
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
                    label="↩️ 返回主選單",
                    text="menu"
                )
            )
        )
        return QuickReply(items=items)
    except Exception as e:
        print(f"Error creating level menu: {str(e)}")
        return None

@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    """處理用戶訊息"""
    try:
        user_id = event.source.user_id
        text = event.message.text.strip()
        
        print(f"Received message: {text}")  # 除錯用

        # 處理主選單請求
        if text.lower() in ['menu', '選單', 'start']:
            quick_reply = create_topic_menu()
            if quick_reply:
                line_bot_api.reply_message(
                    event.reply_token,
                    TextSendMessage(
                        text="請選擇要練習的主題：",
                        quick_reply=quick_reply
                    )
                )
            return

        # 處理主題選擇
        if text.startswith('#topic'):
            _, topic = text.split(' ', 1)
            print(f"Selected topic: {topic}")  # 除錯用
            quick_reply = create_level_menu(topic)
            if quick_reply:
                line_bot_api.reply_message(
                    event.reply_token,
                    TextSendMessage(
                        text=f"請選擇 {MAIN_TOPICS[topic]['description']} 的難度等級：",
                        quick_reply=quick_reply
                    )
                )
            return

        # 處理難度選擇
        if text.startswith('#level'):
            try:
                parts = text.split(' ')
                topic = ' '.join(parts[1:-1])  # 取得主題名稱
                level = parts[-1]  # 取得難度等級
                
                print(f"Selected topic: {topic}, level: {level}")  # 除錯用
                print(f"Available topics: {TOPIC_PROMPTS.keys()}")  # 除錯用
                print(f"Available levels for {topic}: {TOPIC_PROMPTS[topic].keys() if topic in TOPIC_PROMPTS else 'Topic not found'}")  # 除錯用
                
                if topic in TOPIC_PROMPTS and level in TOPIC_PROMPTS[topic]:
                    user_sessions[user_id] = {
                        'topic': topic,
                        'level': level,
                        'prompt': TOPIC_PROMPTS[topic][level]['prompt']
                    }
                    
                    line_bot_api.reply_message(
                        event.reply_token,
                        [
                            TextSendMessage(text=f"已選擇「{TOPIC_PROMPTS[topic][level]['name']}」"),
                            TextSendMessage(
                                text="您可以：\n1. 直接用英文對話\n2. 用中文請我教您相關英文\n3. 隨時輸入「menu」返回選單",
                                quick_reply=QuickReply(items=[
                                    QuickReplyButton(
                                        action=MessageAction(
                                            label="返回選單",
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
                        text="抱歉，選擇有誤，請重新選擇：",
                        quick_reply=quick_reply
                    )
                )
                return

        # 處理一般對話
        if user_id not in user_sessions:
            quick_reply = create_topic_menu()
            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(
                    text="請先選擇一個主題：",
                    quick_reply=quick_reply
                )
            )
            return

        # 使用 OpenAI 回應
        print("Calling OpenAI API...")  # 除錯用
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": user_sessions[user_id]['prompt']},
                {"role": "user", "content": text}
            ]
        )
        response_text = response.choices[0].message['content']
        print(f"OpenAI response: {response_text}")  # 除錯用
        
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(
                text=response_text,
                quick_reply=QuickReply(items=[
                    QuickReplyButton(
                        action=MessageAction(
                            label="返回選單",
                            text="menu"
                        )
                    )
                ])
            )
        )

    except Exception as e:
        print(f"Error in handle_message: {str(e)}")
        import traceback
        print(traceback.format_exc())  # 印出完整錯誤訊息
        try:
            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(
                    text="抱歉，發生錯誤。請再試一次。",
                    quick_reply=QuickReply(items=[
                        QuickReplyButton(
                            action=MessageAction(
                                label="返回選單",
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
    """處理 LINE Webhook"""
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

if __name__ == "__main__":
    print("=== Starting LINE Bot ===")
    print("Checking configurations...")
    print(f"LINE Channel Access Token length: {len(os.getenv('LINE_CHANNEL_ACCESS_TOKEN'))}")
    print(f"LINE Channel Secret length: {len(os.getenv('LINE_CHANNEL_SECRET'))}")
    print(f"OpenAI API Key length: {len(os.getenv('OPENAI_API_KEY'))}")
    app.run(debug=True)