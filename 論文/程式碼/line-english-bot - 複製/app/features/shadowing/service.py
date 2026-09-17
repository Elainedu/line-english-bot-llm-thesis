import os
import json
import random
import tempfile
import requests
import traceback
import time
from datetime import datetime, timedelta
from gtts import gTTS
from mutagen.mp3 import MP3
from pydub import AudioSegment
from linebot.models import (
    TextSendMessage, AudioSendMessage, QuickReply, 
    QuickReplyButton, MessageAction, PostbackAction
)

# 用戶會話管理類
class UserSession:
    # 儲存所有使用者會話的字典
    _sessions = {}
    
    def __init__(self, line_user_id, session_type, session_data=None):
        """初始化用戶會話"""
        self.line_user_id = line_user_id
        self.session_type = session_type  # 例如 "shadowing"
        self.session_data = session_data or {}
        self.created_at = datetime.now()
        self.updated_at = datetime.now()
    
    @classmethod
    def create(cls, line_user_id, session_type, session_data=None):
        """創建新的用戶會話"""
        session = cls(line_user_id, session_type, session_data)
        cls._sessions[line_user_id] = session
        return session
    
    @classmethod
    def get_by_line_user_id(cls, line_user_id):
        """根據 LINE 用戶 ID 獲取會話"""
        return cls._sessions.get(line_user_id)
    
    @classmethod
    def delete(cls, line_user_id):
        """刪除用戶會話"""
        if line_user_id in cls._sessions:
            del cls._sessions[line_user_id]
            return True
        return False
    
    def delete(self):
        """實例方法版本的刪除操作，自動使用當前實例的 line_user_id"""
        return self.__class__.delete(self.line_user_id)
    
    def update(self, session_data=None):
        """更新會話數據"""
        if session_data:
            self.session_data.update(session_data)
        self.updated_at = datetime.now()
        return self

    @classmethod
    def cleanup_old_sessions(cls, hours=24):
        """清理舊的會話"""
        now = datetime.now()
        expired_ids = []
        
        for user_id, session in cls._sessions.items():
            if now - session.updated_at > timedelta(hours=hours):
                expired_ids.append(user_id)
        
        for user_id in expired_ids:
            cls.delete(user_id)
        
        return len(expired_ids)


class ShadowingService:
    def __init__(self, line_bot_api):
        """初始化跟讀練習服務"""
        self.line_bot_api = line_bot_api
        
        # 修正：調整基礎目錄計算方式，避免重複
        current_dir = os.path.dirname(__file__)
        app_dir = os.path.dirname(os.path.dirname(current_dir))
        basedir = os.path.abspath(app_dir)
        
        # 確保不會在路徑中添加重複的 app 目錄
        if os.path.basename(basedir) == 'app':
            self.audio_folder = os.path.join(basedir, 'features', 'shadowing', 'audio')
            self.static_audio_folder = os.path.join(basedir, 'static', 'audio')
        else:
            self.audio_folder = os.path.join(basedir, 'app', 'features', 'shadowing', 'audio')
            self.static_audio_folder = os.path.join(basedir, 'app', 'static', 'audio')
        
        # 確保目錄存在
        os.makedirs(self.audio_folder, exist_ok=True)
        os.makedirs(self.static_audio_folder, exist_ok=True)
        
        print(f"跟讀練習音頻目錄: {self.audio_folder}")
        print(f"靜態音頻目錄: {self.static_audio_folder}")
        
        # 獲取 ngrok URL
        self.base_url = os.getenv('NGROK_URL')
        print(f"初始 NGROK_URL: {self.base_url}")
        
        # 如果環境變數中沒有 NGROK_URL，嘗試從 .env 文件讀取
        if not self.base_url:
            try:
                env_path = os.path.join(basedir, '.env')
                print(f"嘗試從 {env_path} 讀取 NGROK_URL")
                
                if os.path.exists(env_path):
                    with open(env_path, 'r') as env_file:
                        for line in env_file:
                            if line.strip().startswith('NGROK_URL='):
                                self.base_url = line.strip().split('=', 1)[1].strip()
                                # 移除可能的引號和空格
                                self.base_url = self.base_url.strip('"\'').strip()
                                print(f"從 .env 文件讀取的 NGROK_URL: {self.base_url}")
                                break
            except Exception as env_err:
                print(f"讀取 .env 文件錯誤: {str(env_err)}")
                traceback.print_exc()
        
        # 如果還是沒有 URL，嘗試從命令行獲取
        if not self.base_url:
            try:
                import subprocess
                result = subprocess.run(['ngrok', 'status'], stdout=subprocess.PIPE)
                output = result.stdout.decode('utf-8')
                import re
                match = re.search(r'URL:(https://.*?)\s', output)
                if match:
                    self.base_url = match.group(1)
                    print(f"從 ngrok 狀態中獲取 URL: {self.base_url}")
            except Exception as e:
                print(f"嘗試從 ngrok 狀態獲取 URL 時發生錯誤: {str(e)}")
        
        # 如果還是沒有 URL，使用開發環境 URL
        if not self.base_url:
            self.base_url = "http://localhost:5000"
            print(f"使用默認 URL: {self.base_url}")
        
        # 清理 URL（移除結尾斜線和空格）
        self.base_url = self.base_url.rstrip('/').strip()
        print(f"最終使用的 NGROK_URL: {self.base_url}")
        
        # 嘗試初始化 Google Cloud Speech 客戶端
        try:
            from google.cloud import speech
            self.speech_client = speech.SpeechClient()
            self.using_google_speech = True
            print("Google Cloud Speech 客戶端初始化成功")
        except Exception as e:
            print(f"Google Cloud客戶端初始化失敗: {str(e)}")
            traceback.print_exc()
            self.using_google_speech = False
            print("將使用替代評估方法")
        
        # 清理舊音頻文件
        self.cleanup_old_audio_files()
        
        # 清理舊會話
        cleaned = UserSession.cleanup_old_sessions()
        if cleaned > 0:
            print(f"清理了 {cleaned} 個過期會話")

    def cleanup_old_audio_files(self, max_age=3600):
        """清理舊的音訊檔案"""
        try:
            current_time = time.time()
            count = 0
            
            # 清理音訊目錄
            for folder in [self.audio_folder, self.static_audio_folder]:
                if os.path.exists(folder):
                    for filename in os.listdir(folder):
                        if filename.startswith('shadowing_'):  # 只清理跟讀練習相關的音頻
                            file_path = os.path.join(folder, filename)
                            if os.path.isfile(file_path) and os.path.getmtime(file_path) < current_time - max_age:
                                try:
                                    os.remove(file_path)
                                    count += 1
                                except Exception as e:
                                    print(f"刪除文件 {file_path} 時發生錯誤: {str(e)}")
            
            print(f"清理了 {count} 個舊音訊檔案")
        except Exception as e:
            print(f"清理舊音訊檔案時發生錯誤: {str(e)}")
            traceback.print_exc()

    def start_shadowing_session(self, user_id, difficulty):
        """開始新的跟讀練習環節"""
        try:
            # 獲取一個隨機段落
            passage = self.get_random_passage(difficulty)
            if not passage:
                print("無法獲取隨機段落")
                return None
            
            print(f"獲取難度為 {difficulty} 的隨機段落: {passage}")
            
            # 生成 TTS 音頻
            audio_filename, duration = self.generate_tts(passage, difficulty, user_id)
            if not audio_filename:
                print("生成 TTS 音頻失敗")
                return None
            
            print(f"生成 TTS 音頻文件: {audio_filename}")
            
            # 創建音頻 URL - 使用 static/audio 路徑
            audio_url = f"{self.base_url}/static/audio/{audio_filename}"
            print(f"音頻 URL: {audio_url}")
            
            # 創建或更新用戶會話
            session_data = {
                "difficulty": difficulty,
                "text": passage,
                "audio_filename": audio_filename,
                "audio_url": audio_url,
                "audio_duration": duration,
                "attempts": 0,
                "last_score": None
            }
            
            UserSession.create(user_id, "shadowing", session_data)
            
            # 回覆帶有音頻和跟讀練習指示的消息
            messages = [
                TextSendMessage(text="請仔細聆聽以下句子，然後嘗試用相同的語調和速度重複它。"),
                AudioSendMessage(
                    original_content_url=audio_url,
                    duration=duration
                ),
                TextSendMessage(text=f"句子：{passage}\n\n聆聽後，請錄製您的跟讀音頻。")
            ]
            
            return messages
            
        except Exception as e:
            print(f"開始跟讀練習環節時發生錯誤: {str(e)}")
            traceback.print_exc()
            return None

    def get_random_passage(self, difficulty):
        """根據難度獲取隨機段落"""
        try:
            # 嘗試使用 OpenAI API 生成文本
            openai_api_key = os.getenv('OPENAI_API_KEY')
            if not openai_api_key:
                return self._get_fallback_passage(difficulty)
                
            # 定義主題類型列表
            topics = [
                "travel", "food", "hobbies", "technology", "environment", 
                "education", "health", "movies", "music", "sports", 
                "family", "work", "animals", "friendship", "culture"
            ]
            
            # 隨機選擇一個主題
            selected_topic = random.choice(topics)
            
            # 根據難度和主題設定提示詞
            if difficulty == "beginner":
                prompt = f"Generate a single simple sentence (5-10 words) about {selected_topic} using only elementary English vocabulary. Make it suitable for absolute beginners."
            elif difficulty == "intermediate":
                prompt = f"Generate a single sentence (10-15 words) about {selected_topic} using basic English vocabulary. Make it suitable for beginners."
            else:  # advanced
                prompt = f"Generate a single sentence (15-20 words) about {selected_topic} using intermediate English vocabulary. No complex structures."
            
            # 呼叫 OpenAI API
            try:
                headers = {
                    "Authorization": f"Bearer {openai_api_key}",
                    "Content-Type": "application/json"
                }
                
                payload = {
                    "model": "gpt-3.5-turbo",
                    "messages": [
                        {"role": "system", "content": "You are an assistant that generates short, simple English sentences for language beginners."},
                        {"role": "user", "content": prompt}
                    ],
                    "temperature": 0.7,
                    "max_tokens": 50
                }
                
                response = requests.post(
                    "https://api.openai.com/v1/chat/completions",
                    headers=headers,
                    data=json.dumps(payload)
                )
                
                if response.status_code == 200:
                    response_data = response.json()
                    return response_data['choices'][0]['message']['content'].strip()
                else:
                    print(f"OpenAI API 請求失敗: {response.status_code}, {response.text}")
                    return self._get_fallback_passage(difficulty)
            except Exception as e:
                print(f"呼叫 OpenAI API 時發生錯誤: {str(e)}")
                return self._get_fallback_passage(difficulty)
        except Exception as e:
            print(f"生成隨機段落時發生錯誤: {str(e)}")
            return self._get_fallback_passage(difficulty)

    def _get_fallback_passage(self, difficulty):
        """當 API 調用失敗時使用的備用段落集合"""
        # 按主題分類的句子
        beginner_passages = {
            "travel": [
                "I want to visit Paris someday.",
                "She likes to travel by train.",
                "We took photos at the beach.",
                "The hotel room is very clean."
            ],
            "food": [
                "I like to eat pizza on weekends.",
                "This soup tastes very good.",
                "She makes delicious cookies.",
                "We had dinner at a restaurant."
            ],
            "daily_life": [
                "I wake up at six every day.",
                "She reads books before sleeping.",
                "He walks to school every morning.",
                "They play games after dinner."
            ],
            "hobbies": [
                "I enjoy swimming in summer.",
                "She collects beautiful stamps.",
                "He plays guitar very well.",
                "We go hiking on Sundays."
            ],
            "shopping": [
                "These shoes are too expensive.",
                "I need to buy some fruit.",
                "The mall closes at 9 PM.",
                "This shirt is on sale."
            ]
        }
        
        intermediate_passages = {
            "technology": [
                "I use my smartphone to check emails every morning.",
                "Social media helps us connect with old friends.",
                "Many people work from home using computers now.",
                "Digital cameras take better photos than phones."
            ],
            "environment": [
                "We should recycle paper, glass, and plastic.",
                "Solar energy is better for the environment.",
                "Many animals are in danger because of pollution.",
                "Plants and trees help clean the air we breathe."
            ],
            "education": [
                "Learning a new language takes time and practice.",
                "Students should ask questions when they don't understand.",
                "Reading books improves your vocabulary and knowledge.",
                "Online courses are becoming more popular these days."
            ],
            "health": [
                "Regular exercise keeps your body strong and healthy.",
                "Eating vegetables is important for good health.",
                "Getting enough sleep helps your brain work better.",
                "Walking for thirty minutes each day is good exercise."
            ],
            "culture": [
                "Different countries have interesting traditions and customs.",
                "Music and art are important parts of every culture.",
                "People celebrate holidays in many different ways.",
                "Traditional food tells us about a country's history."
            ]
        }
        
        advanced_passages = {
            "society": [
                "Technology has changed the way we communicate with each other.",
                "Public transportation can reduce traffic congestion in big cities.",
                "Many countries are facing challenges with aging populations.",
                "Freedom of speech is considered essential in democratic societies."
            ],
            "personal_growth": [
                "Setting realistic goals helps you achieve what you want in life.",
                "Overcoming challenges builds confidence and resilience.",
                "Continuous learning keeps your mind active and engaged.",
                "Taking small steps every day leads to big changes over time."
            ],
            "relationships": [
                "Good friends support each other through difficult times.",
                "Effective communication is the foundation of healthy relationships.",
                "Understanding different perspectives helps resolve conflicts peacefully.",
                "Trust takes time to build but can be broken in an instant."
            ],
            "career": [
                "Finding work you enjoy makes every day more satisfying.",
                "Developing professional skills increases your career opportunities.",
                "Networking is important for finding new job opportunities.",
                "Remote work offers flexibility but requires self-discipline."
            ],
            "global_issues": [
                "Climate change affects weather patterns around the world.",
                "Access to clean water remains a challenge in many regions.",
                "Cultural exchange promotes understanding between different nations.",
                "Technological innovation can help solve global problems."
            ]
        }
        
        # 根據難度選擇句子集合
        if difficulty == "beginner":
            passages_dict = beginner_passages
        elif difficulty == "intermediate":
            passages_dict = intermediate_passages
        else:  # advanced
            passages_dict = advanced_passages
        
        # 隨機選擇一個主題
        topic = random.choice(list(passages_dict.keys()))
        
        # 從該主題中隨機選擇一個句子
        return random.choice(passages_dict[topic])

    def generate_tts(self, text, difficulty, user_id):
        """生成 TTS 音頻文件"""
        try:
            # 使用穩定的命名方式
            timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
            audio_filename = f"listening_{user_id}_{timestamp}.mp3"
            audio_file_path = os.path.join(self.static_audio_folder, audio_filename)
            
            print(f"生成音頻文件: {audio_file_path}")
            
            # 使用 gTTS 生成音頻 - 與 ShadowingService 保持一致
            tts = gTTS(text=text, lang='en', slow=(difficulty.lower() == 'beginner'))
            tts.save(audio_file_path)
            
            # 檢查文件是否生成成功
            if os.path.exists(audio_file_path) and os.path.getsize(audio_file_path) > 0:
                print(f"音頻文件生成成功，大小: {os.path.getsize(audio_file_path)} 字節")
                
                # 計算音頻時長
                try:
                    audio = MP3(audio_file_path)
                    duration = int(audio.info.length * 1000)  # 轉換為毫秒
                    print(f"音頻時長: {duration} ms")
                except Exception as e:
                    print(f"計算音頻時長時發生錯誤: {str(e)}")
                    duration = 5000  # 默認 5 秒
                
                # 複製到其他目錄（確保可訪問性）
                try:
                    import shutil
                    if self.audio_folder != self.static_audio_folder:
                        shutil.copy2(audio_file_path, os.path.join(self.audio_folder, audio_filename))
                        print(f"已複製音頻文件到: {self.audio_folder}")
                except Exception as copy_e:
                    print(f"複製音頻文件時發生錯誤: {str(copy_e)}")
                
                return audio_filename, duration
            else:
                print(f"音頻文件生成失敗或為空")
                raise Exception("音頻文件生成失敗")
                
        except Exception as e:
            print(f"生成 TTS 音頻時發生錯誤: {str(e)}")
            traceback.print_exc()
            
            # 嘗試返回一個默認音頻（避免完全失敗）
            try:
                default_text = "This is a listening test."
                default_filename = f"listening_default_{user_id}_{timestamp}.mp3"
                default_path = os.path.join(self.static_audio_folder, default_filename)
                
                simple_tts = gTTS(text=default_text, lang='en')
                simple_tts.save(default_path)
                
                # 計算時長
                try:
                    audio = MP3(default_path)
                    duration = int(audio.info.length * 1000)
                except:
                    duration = 3000  # 默認 3 秒
                
                print(f"使用默認音頻: {default_path}")
                return default_filename, duration
            except:
                print("生成默認音頻也失敗")
                return None, None
        
    def evaluate_shadowing(self, user_id, audio_file_path):
        """評估用戶的跟讀表現"""
        try:
            # 獲取用戶會話
            user_session = UserSession.get_by_line_user_id(user_id)
            if not user_session or user_session.session_type != "shadowing":
                return TextSendMessage(text="找不到進行中的跟讀練習環節，請重新開始。")
            
            # 從會話中獲取原始文本和難度
            original_text = user_session.session_data.get('text', '')
            difficulty = user_session.session_data.get('difficulty', 'beginner')
            
            # 更新嘗試次數
            attempts = user_session.session_data.get('attempts', 0) + 1
            user_session.update({"attempts": attempts})
            
            # 如果沒有 Google Speech 認證或使用 Google Speech 評估失敗，提供模擬評估
            if not hasattr(self, 'using_google_speech') or not self.using_google_speech:
                return self._generate_mock_evaluation(user_id, original_text, difficulty, attempts)
            
            # 使用 Google Speech 轉換音頻為文本
            try:
                # 讀取音頻文件
                with open(audio_file_path, "rb") as audio_file:
                    content = audio_file.read()
                
                # 配置語音識別
                from google.cloud import speech
                audio = speech.RecognitionAudio(content=content)
                config = speech.RecognitionConfig(
                    encoding=speech.RecognitionConfig.AudioEncoding.MP3,
                    sample_rate_hertz=16000,  # 可能需要根據實際音頻調整
                    language_code="en-US",
                    enable_automatic_punctuation=True
                )
                
                # 執行語音識別
                response = self.speech_client.recognize(config=config, audio=audio)
                
                # 獲取識別結果
                if response.results:
                    recognized_text = response.results[0].alternatives[0].transcript
                    confidence = response.results[0].alternatives[0].confidence
                else:
                    recognized_text = ""
                    confidence = 0.0
                
                print(f"原始文本: {original_text}")
                print(f"識別文本: {recognized_text}")
                print(f"置信度: {confidence}")
                
                # 計算相似度分數
                similarity_score = self._calculate_similarity(original_text, recognized_text)
                print(f"相似度分數: {similarity_score}")
                
                # 保存評估結果
                user_session.update({"last_score": similarity_score, "recognized_text": recognized_text})
                
                # 根據分數生成反饋訊息
                return self._generate_feedback(user_id, original_text, recognized_text, similarity_score, difficulty, attempts)
                
            except Exception as e:
                print(f"使用 Google Speech 評估時發生錯誤: {str(e)}")
                traceback.print_exc()
                return self._generate_mock_evaluation(user_id, original_text, difficulty, attempts)
                
        except Exception as e:
            print(f"評估跟讀練習時發生錯誤: {str(e)}")
            traceback.print_exc()
            return TextSendMessage(text="評估您的跟讀表現時發生錯誤，請稍後再試。")

    def _calculate_similarity(self, original_text, recognized_text):
        """計算原始文本和識別文本的相似度"""
        try:
            # 簡化文本進行比較
            def simplify_text(text):
                return text.lower().strip().replace(".", "").replace(",", "").replace("?", "").replace("!", "")
            
            orig_simple = simplify_text(original_text)
            recog_simple = simplify_text(recognized_text)
            
            # 使用 Levenshtein 距離計算相似度
            try:
                import Levenshtein
                distance = Levenshtein.distance(orig_simple, recog_simple)
                max_len = max(len(orig_simple), len(recog_simple))
                similarity = 1 - (distance / max_len) if max_len > 0 else 0
                return similarity * 100  # 轉換為百分比
            except ImportError:
                # 如果沒有 Levenshtein 庫，使用簡單的單詞匹配
                orig_words = set(orig_simple.split())
                recog_words = set(recog_simple.split())
                
                if not orig_words:
                    return 0
                
                matches = len(orig_words.intersection(recog_words))
                similarity = matches / len(orig_words)
                return similarity * 100  # 轉換為百分比
                
        except Exception as e:
            print(f"計算相似度時發生錯誤: {str(e)}")
            # 返回默認分數
            return 50.0

    def _generate_feedback(self, user_id, original_text, recognized_text, similarity_score, difficulty, attempts):
        """根據評估結果生成反饋訊息"""
        try:
            # 根據分數判斷表現
            if similarity_score >= 85:
                performance = "優秀"
                feedback = "你的發音非常清晰，語調和節奏與原音接近。繼續保持！"
            elif similarity_score >= 70:
                performance = "良好"
                feedback = "你的發音整體不錯，繼續練習以提高語調和節奏的準確性。"
            elif similarity_score >= 50:
                performance = "中等"
                feedback = "你已經掌握了部分內容，但還需要多練習以提高清晰度和流暢度。"
            else:
                performance = "需要改進"
                feedback = "繼續練習，專注於清晰的發音和正確的語調。多聽幾次原音再嘗試。"
            
            # 準備反饋消息
            messages = []
            
            # 主要評估結果
            result_message = f"評估結果：{performance}\n"
            result_message += f"相似度得分：{similarity_score:.1f}%\n\n"
            result_message += f"原始句子：\n{original_text}\n\n"
            result_message += f"識別內容：\n{recognized_text}\n\n"
            result_message += f"反饋：{feedback}"
            
            messages.append(TextSendMessage(text=result_message))
            
            # 提供選項
            items = [
                QuickReplyButton(action=PostbackAction(label="再試一次", data=f"shadowing_level={difficulty}")),
                QuickReplyButton(action=PostbackAction(label="換一句", data=f"shadowing_level={difficulty}")),
                QuickReplyButton(action=MessageAction(label="返回主選單", text="#menu"))
            ]
            
            messages.append(TextSendMessage(
                text="您想要繼續練習嗎？",
                quick_reply=QuickReply(items=items)
            ))
            
            return messages
            
        except Exception as e:
            print(f"生成反饋訊息時發生錯誤: {str(e)}")
            return TextSendMessage(text="評估完成，但生成反饋時發生錯誤。請重新開始。")

    def _generate_mock_evaluation(self, user_id, original_text, difficulty, attempts):
        """生成模擬評估結果（當無法使用 Google Speech 時）"""
        try:
            # 生成一個隨機分數，隨著嘗試次數增加而提高
            base_score = random.uniform(40, 60)
            attempt_bonus = min(attempts * 5, 20)  # 每次嘗試增加 5 分，最多增加 20 分
            difficulty_modifier = 10 if difficulty == "beginner" else 5 if difficulty == "intermediate" else 0
            
            similarity_score = min(base_score + attempt_bonus + difficulty_modifier, 95)
            
            # 保存評估結果
            user_session = UserSession.get_by_line_user_id(user_id)
            if user_session:
                user_session.update({"last_score": similarity_score, "recognized_text": "無法使用語音識別"})
            
            # 準備反饋消息
            messages = []
            
            result_message = "評估結果（模擬）：\n\n"
            result_message += f"相似度得分：{similarity_score:.1f}%\n\n"
            result_message += f"原始句子：\n{original_text}\n\n"
            result_message += "由於無法使用語音識別功能，此評估結果僅供參考。繼續練習以提高您的發音和流暢度。"
            
            messages.append(TextSendMessage(text=result_message))
            
            # 提供選項
            items = [
                QuickReplyButton(action=PostbackAction(label="再試一次", data=f"shadowing_level={difficulty}")),
                QuickReplyButton(action=PostbackAction(label="換一句", data=f"shadowing_level={difficulty}")),
                QuickReplyButton(action=MessageAction(label="返回主選單", text="#menu"))
            ]
            
            messages.append(TextSendMessage(
                text="您想要繼續練習嗎？",
                quick_reply=QuickReply(items=items)
            ))
            
            return messages
            
        except Exception as e:
            print(f"生成模擬評估時發生錯誤: {str(e)}")
            return TextSendMessage(text="由於技術限制，無法提供詳細評估。請繼續練習或稍後再試。")