import os
import sys
import logging
import asyncio
from datetime import datetime, timedelta
from typing import Optional, Dict, Any

from dotenv import load_dotenv
from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError, LineBotApiError
from linebot.models import (
    MessageEvent, TextMessage, TextSendMessage,
    QuickReplyButton, QuickReply, MessageAction
)
import openai
from prompts.menu_prompts import MAIN_TOPICS, TOPIC_PROMPTS

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('line_bot.log')
    ]
)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Flask application setup
app = Flask(__name__)

# LINE Bot setup
try:
    line_bot_api = LineBotApi(os.getenv('LINE_CHANNEL_ACCESS_TOKEN'))
    handler = WebhookHandler(os.getenv('LINE_CHANNEL_SECRET'))
except Exception as e:
    logger.critical(f"Failed to initialize LINE Bot: {str(e)}")
    sys.exit(1)

# OpenAI setup
openai.api_key = os.getenv('OPENAI_API_KEY')

# User sessions storage with type hints
user_sessions: Dict[str, Dict[str, Any]] = {}

class SessionManager:
    """Manage user sessions with timeout and cleanup"""
    
    @staticmethod
    def get_session(user_id: str) -> Optional[Dict[str, Any]]:
        """Get user session if valid"""
        session = user_sessions.get(user_id)
        if not session:
            return None
            
        if SessionManager.is_session_expired(session):
            del user_sessions[user_id]
            return None
            
        session['last_activity'] = datetime.now()
        return session
    
    @staticmethod
    def set_session(user_id: str, data: Dict[str, Any]) -> None:
        """Set user session with current timestamp"""
        data['last_activity'] = datetime.now()
        user_sessions[user_id] = data
    
    @staticmethod
    def is_session_expired(session: Dict[str, Any]) -> bool:
        """Check if session has expired"""
        last_activity = session.get('last_activity')
        if not last_activity:
            return True
        return datetime.now() - last_activity > timedelta(hours=1)
    
    @staticmethod
    def cleanup_expired_sessions() -> None:
        """Remove expired sessions"""
        expired_users = [
            user_id for user_id, session in user_sessions.items()
            if SessionManager.is_session_expired(session)
        ]
        for user_id in expired_users:
            del user_sessions[user_id]
            logger.info(f"Cleaned up expired session for user: {user_id}")

class MenuBuilder:
    """Handle creation of LINE Bot menus"""
    
    @staticmethod
    def create_topic_menu() -> Optional[QuickReply]:
        """Create topic selection menu"""
        if not MAIN_TOPICS:
            logger.error("MAIN_TOPICS is empty or not properly configured")
            return None
            
        try:
            items = []
            for topic, data in MAIN_TOPICS.items():
                if not isinstance(data, dict) or 'icon' not in data:
                    logger.warning(f"Invalid topic data format for {topic}")
                    continue
                    
                items.append(
                    QuickReplyButton(
                        action=MessageAction(
                            label=f"{data['icon']} {topic}",
                            text=f"#topic {topic}"
                        )
                    )
                )
            return QuickReply(items=items) if items else None
        except Exception as e:
            logger.error(f"Error creating topic menu: {str(e)}")
            return None
    
    @staticmethod
    def create_level_menu(topic: str) -> Optional[QuickReply]:
        """Create difficulty level menu"""
        try:
            if topic not in MAIN_TOPICS:
                logger.error(f"Invalid topic: {topic}")
                return None
                
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
            logger.error(f"Error creating level menu: {str(e)}")
            return None

class OpenAIHandler:
    """Handle OpenAI API interactions"""
    
    @staticmethod
    async def get_response(prompt: str, user_message: str) -> str:
        """Get response from OpenAI with timeout and retry"""
        max_retries = 3
        timeout = 30
        
        for attempt in range(max_retries):
            try:
                response = await asyncio.wait_for(
                    openai.ChatCompletion.create(
                        model="gpt-3.5-turbo",
                        messages=[
                            {"role": "system", "content": prompt},
                            {"role": "user", "content": user_message}
                        ]
                    ),
                    timeout=timeout
                )
                return response.choices[0].message['content']
            except asyncio.TimeoutError:
                logger.warning(f"OpenAI API timeout (attempt {attempt + 1}/{max_retries})")
                if attempt == max_retries - 1:
                    raise
            except Exception as e:
                logger.error(f"OpenAI API error: {str(e)}")
                raise

@handler.add(MessageEvent, message=TextMessage)
async def handle_message(event: MessageEvent) -> None:
    """Handle user messages"""
    try:
        user_id = event.source.user_id
        text = event.message.text.strip()
        
        logger.info(f"Received message from {user_id}: {text}")
        
        # Handle menu request
        if text.lower() in ['menu', 'start']:
            quick_reply = MenuBuilder.create_topic_menu()
            if quick_reply:
                await line_bot_api.reply_message(
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
            logger.info(f"User {user_id} selected topic: {topic}")
            
            quick_reply = MenuBuilder.create_level_menu(topic)
            if quick_reply:
                await line_bot_api.reply_message(
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
                    session_data = {
                        'topic': topic,
                        'level': level,
                        'prompt': TOPIC_PROMPTS[topic][level]['prompt']
                    }
                    SessionManager.set_session(user_id, session_data)
                    
                    await line_bot_api.reply_message(
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
                logger.error(f"Error processing level selection: {str(e)}")
                quick_reply = MenuBuilder.create_topic_menu()
                await line_bot_api.reply_message(
                    event.reply_token,
                    TextSendMessage(
                        text="Sorry, invalid selection. Please try again:",
                        quick_reply=quick_reply
                    )
                )
                return
        
        # Handle general conversation
        session = SessionManager.get_session(user_id)
        if not session:
            quick_reply = MenuBuilder.create_topic_menu()
            await line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(
                    text="Please select a topic first:",
                    quick_reply=quick_reply
                )
            )
            return
        
        # Get OpenAI response
        logger.info(f"Requesting OpenAI response for user {user_id}")
        response_text = await OpenAIHandler.get_response(session['prompt'], text)
        
        await line_bot_api.reply_message(
            event.reply_token,
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
        )
        
    except Exception as e:
        logger.error(f"Error in handle_message: {str(e)}", exc_info=True)
        try:
            await line_bot_api.reply_message(
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
            logger.error(f"Error sending error message: {str(e2)}", exc_info=True)

def validate_env_vars() -> None:
    """Validate required environment variables"""
    required_vars = [
        'LINE_CHANNEL_ACCESS_TOKEN',
        'LINE_CHANNEL_SECRET',
        'OPENAI_API_KEY'
    ]
    
    missing_vars = [var for var in required_vars if not os.getenv(var)]
    
    if missing_vars:
        raise EnvironmentError(
            f"Missing required environment variables: {', '.join(missing_vars)}"
        )

@app.route("/callback", methods=['GET', 'POST'])
async def callback():
    """Handle LINE Webhook"""
    if request.method == 'GET':
        return 'OK'
    
    signature = request.headers.get('X-Line-Signature')
    if not signature:
        logger.error("Missing LINE signature")
        abort(400)
        
    body = request.get_data(as_text=True)
    logger.info(f"Received webhook: {body[:100]}...")  # Log first 100 chars
    
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        logger.error(f"Invalid signature for body: {body[:100]}...")
        abort(400)
    except Exception as e:
        logger.error(f"Error handling webhook: {str(e)}", exc_info=True)
        abort(400)
    return 'OK'

@app.route("/")
def home():
    """Home endpoint"""
    return 'LINE Bot is running!'

@app.before_request
def before_request():
    """Run before each request"""
    SessionManager.cleanup_expired_sessions()

if __name__ == "__main__":
    try:
        validate_env_vars()
        logger.info("=== Starting LINE Bot ===")
        logger.info("All configurations validated successfully")
        app.run(host='0.0.0.0', port=int(os.getenv('PORT', 5000)))
    except Exception as e:
        logger.critical(f"Failed to start application: {str(e)}")
        sys.exit(1)