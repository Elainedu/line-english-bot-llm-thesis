import os
import json
import random
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
from app.features.shadowing.service import UserSession
# 導入提示模板
from app.features.listening.prompts.listening_prompts import (
    LISTENING_SYSTEM_PROMPT, 
    LISTENING_CONTENT_PROMPT_TEMPLATE,
    LISTENING_QUESTIONS_PROMPT_TEMPLATE,
    LISTENING_EVALUATION_PROMPT_TEMPLATE,
    get_question_count,
    MAIN_LISTENING_TOPICS,
    LISTENING_TOPIC_PROMPTS
)


def exception_handler(method):
    """異常處理裝飾器"""
    def wrapper(self, *args, **kwargs):
        try:
            return method(self, *args, **kwargs)
        except Exception as e:
            print(f"{method.__name__} 發生錯誤: {str(e)}")
            traceback.print_exc()
            if len(args) > 1 and hasattr(args[1], 'reply_token'):
                self.line_bot_api.reply_message(
                    args[1].reply_token,
                    TextSendMessage(text="處理請求時發生錯誤，請稍後再試。")
                )
            return None
    return wrapper


class ListeningService:
    def __init__(self, line_bot_api):
        """初始化聽力訓練服務"""
        self.line_bot_api = line_bot_api
        
        # 修正：調整基礎目錄計算方式，避免重複
        current_dir = os.path.dirname(__file__)
        app_dir = os.path.dirname(os.path.dirname(current_dir))
        basedir = os.path.abspath(app_dir)
        
        # 確保不會在路徑中添加重複的 app 目錄
        if os.path.basename(basedir) == 'app':
            self.audio_folder = os.path.join(basedir, 'features', 'listening', 'audio')
            self.static_audio_folder = os.path.join(basedir, 'static', 'audio')
        else:
            self.audio_folder = os.path.join(basedir, 'app', 'features', 'listening', 'audio')
            self.static_audio_folder = os.path.join(basedir, 'app', 'static', 'audio')
        
        # 確保目錄存在
        os.makedirs(self.audio_folder, exist_ok=True)
        os.makedirs(self.static_audio_folder, exist_ok=True)
        
        print(f"聽力訓練音頻目錄: {self.audio_folder}")
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
        
        # 如果還是沒有 URL，使用開發環境 URL
        if not self.base_url:
            self.base_url = "http://localhost:5000"
            print(f"使用默認 URL: {self.base_url}")
        
        # 清理 URL（移除結尾斜線和空格）
        self.base_url = self.base_url.rstrip('/').strip()
        print(f"最終使用的 NGROK_URL: {self.base_url}")
        
        # 初始化用戶會話字典
        self.user_sessions = {}
        
        # 嘗試初始化 Whisper 模型
        try:
            import whisper
            self.whisper_model = whisper.load_model("base")
            self.using_whisper = True
            print("Whisper 模型初始化成功")
        except Exception as e:
            print(f"Whisper 模型初始化失敗: {str(e)}")
            traceback.print_exc()
            self.using_whisper = False
            print("將使用替代評估方法")
        
        # 清理舊音頻文件
        self.cleanup_old_audio_files()
        
        # 清理舊會話
        cleaned = UserSession.cleanup_old_sessions()
        if cleaned > 0:
            print(f"清理了 {cleaned} 個過期會話")
        
        # 測試 TTS 功能
        tts_test_result = self.test_tts()
        print(f"TTS 功能測試結果: {'成功' if tts_test_result else '失敗'}")

    def cleanup_old_audio_files(self, max_age=3600):
        """清理舊的音訊檔案"""
        try:
            current_time = time.time()
            count = 0
            
            # 清理音訊目錄
            for folder in [self.audio_folder, self.static_audio_folder]:
                if os.path.exists(folder):
                    for filename in os.listdir(folder):
                        if filename.startswith('listening_'):  # 只清理聽力練習相關的音頻
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

    def test_tts(self):
        """測試 TTS 功能"""
        try:
            test_text = "This is a test message for text-to-speech conversion."
            timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
            audio_filename = f"test_tts_{timestamp}.mp3"
            audio_file_path = os.path.join(self.static_audio_folder, audio_filename)
            
            # 使用 gTTS 生成音頻
            tts = gTTS(text=test_text, lang='en')
            tts.save(audio_file_path)
        
            if os.path.exists(audio_file_path) and os.path.getsize(audio_file_path) > 0:
                print(f"TTS 測試成功，文件已保存: {audio_file_path}")
                
                # 計算音頻時長
                try:
                    audio = MP3(audio_file_path)
                    duration = int(audio.info.length * 1000)
                    print(f"音頻時長: {duration} 毫秒")
                except Exception as e:
                    print(f"計算音頻時長時發生錯誤: {str(e)}")
                
                # 清理測試文件
                os.remove(audio_file_path)
                return True
            else:
                print("TTS 測試失敗，無法生成音頻文件")
                return False
        except Exception as e:
            print(f"TTS 測試發生錯誤: {str(e)}")
            traceback.print_exc()
            return False    

    @exception_handler
    def start_listening_session(self, user_id, difficulty):
        """開始新的聽力訓練環節"""
        print(f"開始 {difficulty} 難度的聽力訓練")
        
        try:
            # 使用 get_random_passage 方法獲取一段文本
            content = self.get_random_passage(difficulty)
            if not content:
                print("無法獲取隨機段落")
                return TextSendMessage(text="準備聽力訓練內容時發生錯誤，請稍後再試。")
            
            print(f"獲取難度為 {difficulty} 的隨機段落: {content}")
            
            # 使用 generate_questions 方法生成問題
            questions = self._generate_questions(content, difficulty)
            if not questions:
                print("無法生成問題")
                # 使用備用問題
                questions = [{"question": "What is the main topic of this passage?", "answer": "Please provide a summary."}]
            
            print(f"生成問題: {questions}")
            
            # 生成 TTS 音頻
            try:
                audio_filename, duration = self.generate_tts(content, difficulty, user_id)
                if not audio_filename:
                    raise Exception("無法生成音頻文件")
                    
                print(f"生成 TTS 音頻文件: {audio_filename}, 時長: {duration}ms")
            except Exception as e:
                print(f"生成音頻時發生錯誤: {str(e)}")
                traceback.print_exc()
                return TextSendMessage(text="生成音頻時發生錯誤，請稍後再試。")
            
            # 創建音頻 URL - 使用 static/audio 路徑
            audio_url = f"{self.base_url}/static/audio/{audio_filename}"
            print(f"音頻 URL: {audio_url}")
            
            # 創建用戶會話
            session_data = {
                "difficulty": difficulty,
                "content": content,
                "questions": questions,
                "current_question_index": 0,
                "audio_filename": audio_filename,
                "audio_url": audio_url,
                "audio_duration": duration,
                "scores": [],
                "state": "listening"
            }
            
            # 保存會話數據到本地字典
            self.user_sessions[user_id] = session_data
            print(f"用戶會話已保存到本地字典: {user_id}")
            
            # 準備回覆訊息，加入問題文字
            first_question = questions[0]['question']
            messages = [
                TextSendMessage(text=f"聽力練習 {difficulty.capitalize()} 難度：請仔細聽下面的音訊"),
                AudioSendMessage(original_content_url=audio_url, duration=duration)
            ]

            # 直接添加問題到回傳訊息中
            messages.extend(self.ask_question(user_id, None))

            return messages
        except Exception as e:
            print(f"開始聽力訓練環節時發生錯誤: {str(e)}")
            traceback.print_exc()
            return TextSendMessage(text="聽力訓練準備中遇到問題，請稍後再試。")
        
    def _generate_questions(self, content, difficulty):
        """根據內容生成問題"""
        try:
            # 直接使用 prompt 檔案中的函數和常數
            question_count = get_question_count(difficulty)
            
            # 如果沒有 OpenAI API key，返回默認問題
            openai_api_key = os.getenv('OPENAI_API_KEY')
            if not openai_api_key:
                return [{"question": "What is the main topic?", "answer": "Describe the main idea"}]
            
            # 準備 OpenAI API 請求
            headers = {
                "Authorization": f"Bearer {openai_api_key}",
                "Content-Type": "application/json"
            }
            
            payload = {
                "model": "gpt-3.5-turbo",
                "messages": [
                    {"role": "system", "content": LISTENING_SYSTEM_PROMPT},
                    {"role": "user", "content": LISTENING_QUESTIONS_PROMPT_TEMPLATE.format(
                        content=content,
                        difficulty=difficulty,
                        question_count=question_count
                    )}
                ],
                "temperature": 0.3,
                "max_tokens": 200
            }
            
            response = requests.post(
                "https://api.openai.com/v1/chat/completions",
                headers=headers,
                data=json.dumps(payload)
            )
            
            if response.status_code == 200:
                questions_str = response.json()['choices'][0]['message']['content'].strip()
                
                # 清理並解析 JSON
                questions_str = questions_str.replace("```json", "").replace("```", "").strip()
                
                try:
                    questions = json.loads(questions_str)
                    
                    # 驗證問題格式
                    if not isinstance(questions, list) or \
                    not all(isinstance(q, dict) and "question" in q and "answer" in q for q in questions):
                        raise ValueError("問題格式不正確")
                    
                    return questions
                
                except (json.JSONDecodeError, ValueError) as e:
                    print(f"解析問題時發生錯誤: {str(e)}")
                    return [{"question": "What is the main topic?", "answer": "Describe the main idea"}]
            
            else:
                print(f"OpenAI API 請求失敗，狀態碼: {response.status_code}")
                return [{"question": "What is the main topic?", "answer": "Describe the main idea"}]
        
        except Exception as e:
            print(f"生成問題時發生錯誤: {str(e)}")
            return [{"question": "What is the main topic?", "answer": "Describe the main idea"}]

    def get_random_passage(self, difficulty):
        """根据难度获取随机段落"""
        try:
            # 使用 OpenAI API 生成文本
            openai_api_key = os.getenv('OPENAI_API_KEY')
            if not openai_api_key:
                return self._get_fallback_passage(difficulty)
                
            # 定义主题类型列表
            topics = [
                "nature", "animals", "weather", "space", 
                "sports", "music", "technology", "books", 
                "colors", "emotions", "time", "seasons"
            ]
            
            # 随机选择一个主题
            selected_topic = random.choice(topics)
            
            # 根据难度和主题设定提示词
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
                        {"role": "system", "content": "You are an assistant that generates short, simple English sentences for language learners."},
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
                    passage = response_data['choices'][0]['message']['content'].strip()
                    
                    # 额外验证，确保符合难度要求
                    word_count = len(passage.split())
                    if (difficulty == "beginner" and (word_count < 5 or word_count > 10)) or \
                    (difficulty == "intermediate" and (word_count < 10 or word_count > 15)) or \
                    (difficulty == "advanced" and (word_count < 15 or word_count > 20)):
                        return self._get_fallback_passage(difficulty)
                    
                    return passage
                else:
                    return self._get_fallback_passage(difficulty)
            except Exception as e:
                print(f"呼叫 OpenAI API 时发生错误: {str(e)}")
                return self._get_fallback_passage(difficulty)
        except Exception as e:
            print(f"生成随机段落时发生错误: {str(e)}")
            return self._get_fallback_passage(difficulty)

    def _get_fallback_passage(self, difficulty):
        """當 API 調用失敗時使用的備用段落集合"""
        # 按主題分類的段落
        beginner_passages = {
            "travel": [
                "I went to Paris last summer. The weather was nice and warm. I visited the Eiffel Tower.",
                "My family likes to travel by car. We take photos at every place we visit. Our favorite place is the beach."
            ],
            "food": [
                "I eat breakfast at 7 AM every day. I usually have eggs and toast. Sometimes I drink orange juice.",
                "My favorite food is pizza. I like pizza with cheese and tomatoes. I eat pizza once a week."
            ],
            "daily_life": [
                "I wake up at six every morning. Then I take a shower and eat breakfast. I go to work by bus.",
                "On weekends, I clean my house and do laundry. In the afternoon, I meet my friends. We talk and laugh a lot."
            ]
        }
        
        intermediate_passages = {
            "technology": [
                "Many people use smartphones every day. We can check emails, browse the internet, and take photos. Technology has changed the way we communicate with others.",
                "Computers have become important tools for work and study. People can now work from home using the internet. This has made life more convenient for many people."
            ],
            "environment": [
                "Taking care of our environment is very important. We should recycle paper, plastic, and glass. This helps reduce pollution and save natural resources.",
                "Climate change is affecting our planet. Temperatures are rising, and weather patterns are changing. We need to find ways to protect our environment for future generations."
            ],
            "education": [
                "Education is important for personal growth and success. Students learn many subjects like math, science, and languages. Good education helps people find better jobs.",
                "Many students around the world now take online courses. They can learn at their own pace and from anywhere. This type of education is becoming more popular."
            ]
        }
        
        advanced_passages = {
            "society": [
                "The way we communicate has been transformed by social media platforms. People can now connect with others across the globe instantly. However, this constant connectivity has raised concerns about privacy and mental health issues. Finding a balance between online and offline life has become a challenge for many individuals.",
                "Urbanization continues to shape modern society as more people move to cities in search of better opportunities. This migration has led to the growth of megacities with populations exceeding 10 million. While cities offer economic advantages, they also face challenges such as housing shortages, traffic congestion, and environmental pollution. Urban planners are working to create more sustainable and livable cities."
            ],
            "personal_growth": [
                "Personal development requires continuous learning and self-reflection. Setting realistic goals helps individuals track their progress and stay motivated. Many people find that stepping outside their comfort zone leads to the most significant growth. Embracing challenges and learning from failures are essential parts of the journey.",
                "Maintaining a healthy work-life balance has become increasingly important in today's fast-paced world. People are recognizing that success involves more than just career achievements. Taking time for family, hobbies, and self-care contributes to overall well-being and happiness. Finding this balance is a personal journey that varies for each individual."
            ],
            "global_issues": [
                "Access to clean water remains a significant challenge in many parts of the world. Nearly 800 million people lack basic drinking water services. Climate change is worsening this situation by causing more frequent droughts in already water-scarce regions. International organizations are working with local communities to implement sustainable water management solutions.",
                "The global response to public health emergencies has evolved significantly in recent years. Countries are now more aware of the importance of international cooperation and information sharing. Advances in medical research and technology have improved our ability to respond quickly to outbreaks. However, ensuring equitable access to healthcare remains a challenge that requires ongoing attention."
            ]
        }
        
        # 根據難度選擇段落集合
        if difficulty == "beginner":
            passages_dict = beginner_passages
        elif difficulty == "intermediate":
            passages_dict = intermediate_passages
        else:  # advanced
            passages_dict = advanced_passages
        
        # 隨機選擇一個主題
        topic = random.choice(list(passages_dict.keys()))
        
        # 從該主題中隨機選擇一個段落
        return random.choice(passages_dict[topic])

    def generate_questions(self, content, difficulty):
        """根據內容生成問題"""
        try:
            # 嘗試使用 OpenAI API 生成問題
            openai_api_key = os.getenv('OPENAI_API_KEY')
            if not openai_api_key:
                print("找不到 OpenAI API 金鑰")
                return [{"question": "What is the main topic of this passage?", "answer": "Describe the main idea"}]
                
            question_count = get_question_count(difficulty)
            prompt = LISTENING_QUESTIONS_PROMPT_TEMPLATE.format(
                content=content,
                difficulty=difficulty,
                question_count=question_count
            )
            
            headers = {
                "Authorization": f"Bearer {openai_api_key}",
                "Content-Type": "application/json"
            }
            
            payload = {
                "model": "gpt-3.5-turbo",
                "messages": [
                    {"role": "system", "content": "You are an expert at creating precise listening comprehension questions that directly relate to the given text."},
                    {"role": "user", "content": prompt}
                ],
                "temperature": 0.3,  # 降低隨機性
                "max_tokens": 400
            }
            
            response = requests.post(
                "https://api.openai.com/v1/chat/completions",
                headers=headers,
                data=json.dumps(payload)
            )
            
            if response.status_code == 200:
                questions_str = response.json()['choices'][0]['message']['content'].strip()
                
                # 清理 JSON 字串
                questions_str = questions_str.replace("```json", "").replace("```", "").strip()
                
                try:
                    questions = json.loads(questions_str)
                    
                    # 嚴格驗證問題格式
                    if not isinstance(questions, list):
                        raise ValueError("生成的不是問題列表")
                    
                    for q in questions:
                        if not isinstance(q, dict) or "question" not in q or "answer" not in q:
                            raise ValueError("問題格式不正確")
                    
                    print(f"使用 OpenAI 生成的問題: {questions}")
                    return questions
                
                except (json.JSONDecodeError, ValueError) as e:
                    print(f"解析 OpenAI 生成的問題時發生錯誤: {str(e)}")
                    print(f"原始返回內容: {questions_str}")
                    # 返回一個通用的默認問題
                    return [{"question": "What is the main topic of this passage?", "answer": "Describe the main idea"}]
            else:
                print(f"OpenAI API 請求失敗，狀態碼: {response.status_code}")
                return [{"question": "What is the main topic of this passage?", "answer": "Describe the main idea"}]
        except Exception as e:
            print(f"使用 OpenAI 生成問題時發生錯誤: {str(e)}")
            traceback.print_exc()
            return [{"question": "What is the main topic of this passage?", "answer": "Describe the main idea"}]

    def _generate_simple_questions(self, content, difficulty):
        """生成簡單的備用問題"""
        # 根據難度生成不同數量和複雜度的問題
        questions = []
        sentences = content.split('.')
        sentences = [s.strip() for s in sentences if s.strip()]
        
        # 至少生成一個問題
        questions.append({"question": "What is the main topic of this passage?", "answer": "The main topic is about " + sentences[0] if sentences else "the content"})
        
        # 根據難度添加更多問題
        if difficulty.lower() == "intermediate" and len(sentences) > 1:
            questions.append({"question": "What details were mentioned in the passage?", "answer": "Some details include " + sentences[1] if len(sentences) > 1 else "various aspects of the topic"})
        
        if difficulty.lower() == "advanced" and len(sentences) > 2:
            questions.append({"question": "What is your opinion about this topic?", "answer": "Any reasonable opinion about the topic."})
            questions.append({"question": "Can you summarize the key points of this passage?", "answer": "The key points include " + " and ".join(sentences[:2]) if len(sentences) > 1 else "the main aspects discussed"})
        
        return questions

    def generate_tts(self, text, difficulty, user_id):
        """生成 TTS 音頻文件"""
        try:
            # 使用穩定的命名方式
            timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
            audio_filename = f"listening_{user_id}_{timestamp}.mp3"
            audio_file_path = os.path.join(self.static_audio_folder, audio_filename)
            
            print(f"生成音頻文件: {audio_file_path}")
            
            # 使用 gTTS 生成音頻
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

    @exception_handler
    def handle_text_message(self, event):
        """處理用戶文字回答"""
        user_id = event.source.user_id
        user_input = event.message.text.strip()
        reply_token = event.reply_token
        
        # 檢查用戶是否在聽力訓練中
        if user_id not in self.user_sessions:
            session = UserSession.get_by_line_user_id(user_id)
            if session and session.session_type == "listening":
                self.user_sessions[user_id] = session.session_data
            else:
                return None
        
        session_data = self.user_sessions[user_id]
        state = session_data.get("state", "listening")
        
        # 處理特殊命令
        if user_input.startswith("#"):
            if user_input == "#repeat":
                return self.repeat_audio(user_id, reply_token)
            elif user_input == "#menu":
                return None  # 由主處理程序處理
            elif user_input == "#skip":
                return self.skip_question(user_id, reply_token)
            else:
                return TextSendMessage(text="未知命令，請繼續聽力練習或輸入 #menu 返回主選單。")
        
        # 根據當前狀態處理
        if state == "listening":
            if user_input.lower() in ["準備好了", "ready", "i'm ready", "yes", "go", "開始"]:
                return self.ask_question(user_id, reply_token)
            else:
                return TextSendMessage(
                    text="請在聆聽完畢後，輸入「準備好了」或點擊下方按鈕開始回答問題。",
                    quick_reply=QuickReply(items=[
                        QuickReplyButton(action=MessageAction(label="準備好了", text="準備好了")),
                        QuickReplyButton(action=MessageAction(label="再聽一次", text="#repeat")),
                        QuickReplyButton(action=MessageAction(label="返回主選單", text="#menu"))
                    ])
                )
        elif state == "answering":
            return self.evaluate_answer(user_id, user_input, reply_token)
        else:
            return TextSendMessage(text="聽力練習狀態錯誤，請重新開始。")

    @exception_handler
    def repeat_audio(self, user_id, reply_token):
        """重複播放音頻"""
        session_data = self.user_sessions.get(user_id)
        if not session_data:
            return TextSendMessage(text="找不到進行中的聽力練習，請重新開始。")
        
        audio_url = session_data.get("audio_url")
        duration = session_data.get("audio_duration")
        
        if not audio_url or not duration:
            return TextSendMessage(text="無法重複播放音頻，請重新開始練習。")
        
        messages = [
            TextSendMessage(text="再次播放音頻："),
            AudioSendMessage(original_content_url=audio_url, duration=duration),
            TextSendMessage(
                text="聆聽完畢後，請輸入「準備好了」或點擊下方按鈕開始回答問題。",
                quick_reply=QuickReply(items=[
                    QuickReplyButton(action=MessageAction(label="準備好了", text="準備好了")),
                    QuickReplyButton(action=MessageAction(label="再聽一次", text="#repeat")),
                    QuickReplyButton(action=MessageAction(label="返回主選單", text="#menu"))
                ])
            )
        ]
        
        self.line_bot_api.reply_message(reply_token, messages)
        return "handled"
    
    @exception_handler
    def ask_question(self, user_id, reply_token):
        """向用戶提出問題"""
        session_data = self.user_sessions.get(user_id)
        if not session_data:
            return TextSendMessage(text="找不到進行中的聽力練習，請重新開始。")
        
        # 獲取當前問題
        current_index = session_data.get("current_question_index", 0)
        questions = session_data.get("questions", [])
        
        if not questions or current_index >= len(questions):
            return self.complete_session(user_id, reply_token)
        
        # 獲取當前問題
        current_question = questions[current_index]
        question_text = current_question.get("question", "")
        
        # 更新狀態
        session_data["state"] = "answering"
        session = UserSession.get_by_line_user_id(user_id)
        if session:
            session.update({"state": "answering"})
        
        # 更新本地字典
        self.user_sessions[user_id] = session_data
        
        # 發送問題
        messages = [
            TextSendMessage(
                text=f"問題 {current_index + 1}/{len(questions)}:\n\n{question_text}\n\n請直接輸入您的答案。",
                
            )
        ]
        
        return messages

    @exception_handler
    def evaluate_answer(self, user_id, user_answer, reply_token):
        """評估用戶的回答"""
        session_data = self.user_sessions.get(user_id)
        if not session_data:
            return TextSendMessage(text="找不到進行中的聽力練習，請重新開始。")
        
        # 特殊命令 - 跳過問題
        if user_answer == "#skip":
            return self.skip_question(user_id, reply_token)
        
        # 獲取當前問題
        current_index = session_data.get("current_question_index", 0)
        questions = session_data.get("questions", [])
        
        if not questions or current_index >= len(questions):
            self.line_bot_api.reply_message(
                reply_token,
                TextSendMessage(text="所有問題已回答完畢，正在計算總分...")
            )
            return self.complete_session(user_id, reply_token)
        
        current_question = questions[current_index]
        question_text = current_question.get("question", "")
        correct_answer = current_question.get("answer", "")
        
        # 評估回答
        evaluation = self.evaluate_user_answer(question_text, user_answer, correct_answer)
        
        # 保存分數並更新狀態
        scores = session_data.get("scores", [])
        scores.append(evaluation.get("score", 0))
        session_data["scores"] = scores
        session_data["current_question_index"] = current_index + 1
        session_data["state"] = "listening"
        
        # 更新本地字典
        self.user_sessions[user_id] = session_data
        
        # 更新 UserSession
        session = UserSession.get_by_line_user_id(user_id)
        if session:
            session.update({
                "current_question_index": current_index + 1,
                "scores": scores,
                "state": "listening"
            })
        
       
        
        # 檢查是否還有更多問題
        if current_index + 1 < len(questions):
            # 還有更多問題
            messages = [
                TextSendMessage(text=feedback_message),
                TextSendMessage(
                    text="準備好回答下一個問題了嗎？",
                )
            ]
        else:
            # 所有問題已回答完畢
            messages = [
                TextSendMessage(text=feedback_message),
                TextSendMessage(text="所有問題已回答完畢，正在計算總分...")
            ]
            # 自動完成會話
            self.line_bot_api.reply_message(reply_token, messages)
            return self.complete_session(user_id, None)
        
        self.line_bot_api.reply_message(reply_token, messages)
        return "handled"

    @exception_handler
    def skip_question(self, user_id, reply_token):
        """跳過當前問題"""
        session_data = self.user_sessions.get(user_id)
        if not session_data:
            return TextSendMessage(text="找不到進行中的聽力練習，請重新開始。")
        
        # 獲取當前問題
        current_index = session_data.get("current_question_index", 0)
        questions = session_data.get("questions", [])
        
        if not questions or current_index >= len(questions):
            return self.complete_session(user_id, reply_token)
        
        correct_answer = questions[current_index].get("answer", "")
        
        # 添加零分並更新狀態
        scores = session_data.get("scores", [])
        scores.append(0)
        session_data["scores"] = scores
        session_data["current_question_index"] = current_index + 1
        session_data["state"] = "listening"
        
        # 更新本地字典
        self.user_sessions[user_id] = session_data
        
        # 更新 UserSession
        session = UserSession.get_by_line_user_id(user_id)
        if session:
            session.update({
                "current_question_index": current_index + 1,
                "scores": scores,
                "state": "listening"
            })
        
        # 發送跳過信息
        skip_message = f"您已跳過此問題。\n參考答案: {correct_answer}\n"
        
        # 檢查是否還有更多問題
        if current_index + 1 < len(questions):
            messages = [
                TextSendMessage(text=skip_message),
            ]
        else:
            messages = [
                TextSendMessage(text=skip_message),
                TextSendMessage(text="所有問題已回答完畢，正在計算總分...")
            ]
            self.line_bot_api.reply_message(reply_token, messages)
            return self.complete_session(user_id, None)
        
        self.line_bot_api.reply_message(reply_token, messages)
        return "handled"

    @exception_handler
    def complete_session(self, user_id, reply_token=None):
        """完成聽力練習環節並計算總結果"""
        session_data = self.user_sessions.get(user_id)
        if not session_data:
            if reply_token:
                return TextSendMessage(text="找不到進行中的聽力練習，請重新開始。")
            return "handled"
        
        # 計算總分
        scores = session_data.get("scores", [])
        avg_score = sum(scores) / len(scores) if scores else 0
        
        # 獲取難度和內容
        difficulty = session_data.get("difficulty", "beginner")
        content = session_data.get("content", "")
        questions = session_data.get("questions", [])
        
        # 準備結果訊息
        result_message = (
            "📊 聽力練習總結 📊\n\n"
            f"難度: {difficulty.capitalize()}\n"
            f"總分: {avg_score:.1f}/5\n\n"
        )
        
        # 添加表現評價
        if avg_score >= 90:
            result_message += "太棒了！您的聽力理解能力非常出色！ 🌟\n\n"
        elif avg_score >= 75:
            result_message += "很好！您有很好的聽力理解能力。 👍\n\n"
        elif avg_score >= 60:
            result_message += "不錯！您有良好的聽力基礎，繼續練習。 💪\n\n"
        elif avg_score >= 40:
            result_message += "您已經掌握了一些聽力技巧，繼續努力！ 🌱\n\n"
        else:
            result_message += "聽力需要大量練習，不要氣餒，繼續加油！ 🚀\n\n"
        
        # 添加原文和問題
        result_message += "🎧 聽力原文:\n" + content + "\n\n"
        result_message += "📝 問題和參考答案:\n"
        for i, q in enumerate(questions):
            result_message += (
                f"{i+1}. {q.get('question', '')}\n"
                f"   答案: {q.get('answer', '')}\n\n"
            )
        
        
        
        # 清理會話數據
        if user_id in self.user_sessions:
            del self.user_sessions[user_id]
        
        # 嘗試從 UserSession 中刪除
        try:
            session = UserSession.get_by_line_user_id(user_id)
            if session:
                session.delete()
        except Exception as e:
            print(f"刪除 UserSession 時發生錯誤: {str(e)}")
        
        # 發送結果
        quick_reply = QuickReply(items=[
            QuickReplyButton(action=PostbackAction(label="初級聽力", data="listening_level=beginner")),
            QuickReplyButton(action=PostbackAction(label="中級聽力", data="listening_level=intermediate")),
            QuickReplyButton(action=PostbackAction(label="高級聽力", data="listening_level=advanced")),
            QuickReplyButton(action=MessageAction(label="返回主選單", text="#menu"))
        ])
        
        messages = [
            TextSendMessage(text=result_message),
            TextSendMessage(text="您想繼續練習嗎？", quick_reply=quick_reply)
        ]
        
        if reply_token:
            try:
                self.line_bot_api.reply_message(reply_token, messages)
            except Exception as e:
                print(f"發送結果訊息失敗: {str(e)}")
                # 嘗試使用 push message 作為備用
                try:
                    self.line_bot_api.push_message(user_id, messages)
                except:
                    pass
        else:
            try:
                self.line_bot_api.push_message(user_id, messages)
            except Exception as e:
                print(f"推送結果訊息失敗: {str(e)}")
        
        return "handled"

    def evaluate_user_answer(self, question, user_answer, correct_answer):
        """評估用戶回答的準確性，返回 5 分制評分"""
        try:
            # 簡化文本進行比較
            def normalize_text(text):
                return text.lower().strip().replace(".", "").replace(",", "").replace("?", "").replace("!", "")
            
            user_norm = normalize_text(user_answer)
            correct_norm = normalize_text(correct_answer)
            
            # 檢查基本內容是否存在
            if not user_norm or not correct_norm:
                return {
                    "score": 3,  # 默認給 3/5 分
                    "score_text": "3/5",
                    "feedback": "請嘗試回答問題。",
                    "explanation": "嘗試根據聽到的內容給出回答。"
                }
            
            # 檢查關鍵詞
            def extract_keywords(text):
                # 移除常見的冠詞、介係詞等
                stop_words = {'the', 'a', 'an', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by'}
                return {word for word in text.split() if word.lower() not in stop_words}
            
            user_keywords = extract_keywords(user_norm)
            correct_keywords = extract_keywords(correct_norm)
            
            # 計算關鍵詞匹配度
            if not correct_keywords:
                return {
                    "score": 4,  # 默認給 4/5 分
                    "score_text": "4/5",
                    "feedback": "您的回答基本正確。",
                    "explanation": "嘗試包含更多具體細節。"
                }
            
            # 計算關鍵詞重疊率
            common_keywords = user_keywords.intersection(correct_keywords)
            keyword_match_ratio = len(common_keywords) / len(correct_keywords)
            
            # 根據關鍵詞匹配度給分
            if keyword_match_ratio >= 0.8:
                score = 5
                feedback = "太棒了！您的回答非常準確！"
                explanation = "您完全抓住了問題的關鍵。"
            elif keyword_match_ratio >= 0.6:
                score = 4
                feedback = "很好！回答接近正確答案。"
                explanation = "您抓住了大部分關鍵信息。"
            elif keyword_match_ratio >= 0.4:
                score = 3
                feedback = "不錯！有一些關鍵信息。"
                explanation = "繼續保持，多聽多練。"
            elif keyword_match_ratio >= 0.2:
                score = 2
                feedback = "有些困難，但已有嘗試。"
                explanation = "繼續加油，仔細聆聽。"
            else:
                score = 1
                feedback = "需要更多練習。"
                explanation = "建議仔細聆聽並多加練習。"
            
            return {
                "score": score,
                "score_text": f"{score}/5",
                "feedback": feedback,
                "explanation": explanation
            }
            
        except Exception as e:
            print(f"本地評估時發生錯誤: {str(e)}")
            return {
                "score": 3,  # 出錯時給 3/5 分
                "score_text": "3/5",
                "feedback": "系統評估遇到困難。",
                "explanation": "請繼續練習，保持信心。"
            }

    def evaluate_answer(self, user_id, user_answer, reply_token):
        """評估用戶的回答"""
        session_data = self.user_sessions.get(user_id)
        if not session_data:
            return TextSendMessage(text="找不到進行中的聽力練習，請重新開始。")
        
        # 獲取當前問題
        current_index = session_data.get("current_question_index", 0)
        questions = session_data.get("questions", [])
        
        if not questions or current_index >= len(questions):
            self.line_bot_api.reply_message(
                reply_token,
                TextSendMessage(text="所有問題已回答完畢，正在計算總分...")
            )
            return self.complete_session(user_id, reply_token)
        
        current_question = questions[current_index]
        question_text = current_question.get("question", "")
        correct_answer = current_question.get("answer", "")
        
        # 評估回答
        evaluation = self.evaluate_user_answer(question_text, user_answer, correct_answer)
        
        # 保存分數並更新狀態
        scores = session_data.get("scores", [])
        scores.append(evaluation.get("score", 3))  # 默認 3 分
        session_data["scores"] = scores
        session_data["current_question_index"] = current_index + 1
        session_data["state"] = "listening"
        
        # 更新本地字典
        self.user_sessions[user_id] = session_data
        
        # 更新 UserSession
        session = UserSession.get_by_line_user_id(user_id)
        if session:
            session.update({
                "current_question_index": current_index + 1,
                "scores": scores,
                "state": "listening"
            })
        
        # 準備反饋訊息
        feedback_message = (
            f"您的回答: {user_answer}\n\n"
            f"參考答案: {correct_answer}\n\n"
            f"評分: {evaluation.get('score_text', '3/5')}\n"
            f"反饋: {evaluation.get('feedback', '')}\n\n"
            f"{evaluation.get('explanation', '')}"
        )
        
        # 檢查是否還有更多問題
        if current_index + 1 < len(questions):
            # 還有更多問題
            messages = [
                TextSendMessage(text=feedback_message),
                TextSendMessage(
                    text="準備好下一個問題了嗎？",
                    quick_reply=QuickReply(items=[
                        QuickReplyButton(action=MessageAction(label="下一題", text="下一題")),
                        QuickReplyButton(action=MessageAction(label="再聽一次", text="#repeat")),
                        QuickReplyButton(action=MessageAction(label="返回主選單", text="#menu"))
                    ])
                )
            ]
        else:
            # 所有問題已回答完畢
            messages = [
                TextSendMessage(text=feedback_message),
                TextSendMessage(text="所有問題已回答完畢，正在計算總分...")
            ]
            # 自動完成會話
            self.line_bot_api.reply_message(reply_token, messages)
            return self.complete_session(user_id, None)
        
        self.line_bot_api.reply_message(reply_token, messages)
        return "handled"

    def _local_evaluation(self, user_answer, correct_answer):
        """本地評估方法"""
        try:
            # 簡化文本進行比較
            def normalize_text(text):
                return text.lower().strip().replace(".", "").replace(",", "").replace("?", "").replace("!", "")
            
            user_norm = normalize_text(user_answer)
            correct_norm = normalize_text(correct_answer)
            
            # 計算共同單詞數量
            user_words = set(user_norm.split())
            correct_words = set(correct_norm.split())
            
            if not correct_words:
                return {
                    "score": 50,
                    "feedback": "無法準確評估您的回答。",
                    "explanation": "請繼續練習，專注於理解關鍵信息。"
                }
            
            common_words = user_words.intersection(correct_words)
            score = (len(common_words) / len(correct_words)) * 100
            
            # 根據分數給出反饋
            if score >= 80:
                feedback = "您的回答非常準確！"
                explanation = "您正確理解了大部分內容，展現了很好的聽力理解能力。"
            elif score >= 60:
                feedback = "您的回答包含了一些關鍵信息。"
                explanation = "您理解了部分內容，但還有一些細節未能捕捉到。"
            elif score >= 40:
                feedback = "您理解了一些基本內容。"
                explanation = "嘗試更專注於聽取關鍵詞和主要信息。"
            else:
                feedback = "您的回答與預期有較大差距。"
                explanation = "建議重複聆聽，並專注於識別主題和關鍵詞。"
            
            return {
                "score": int(score),
                "feedback": feedback,
                "explanation": explanation
            }
            
        except Exception as e:
            print(f"本地評估時發生錯誤: {str(e)}")
            return {
                "score": 50,
                "feedback": "系統無法準確評估您的回答。",
                "explanation": "請繼續練習，專注於理解聽力內容的主要信息。"
            }
            
    @exception_handler
    def evaluate_listening(self, user_id, audio_file_path):
        """評估用戶的語音回答（從音頻文件轉換為文本後評估）"""
        # 檢查用戶是否在聽力訓練中
        if user_id not in self.user_sessions:
            session = UserSession.get_by_line_user_id(user_id)
            if session and session.session_type == "listening":
                self.user_sessions[user_id] = session.session_data
            else:
                return TextSendMessage(text="找不到進行中的聽力訓練環節，請重新開始。")
        
        session_data = self.user_sessions[user_id]
        state = session_data.get("state", "listening")
        
        # 檢查是否在回答問題狀態
        if state != "answering":
            if state == "listening":
                # 提示用戶開始回答
                return [
                    TextSendMessage(text="您已完成聆聽。現在要開始回答問題嗎？"),
                    TextSendMessage(
                        text="請輸入「準備好了」或點擊下方按鈕開始回答問題。",
                        quick_reply=QuickReply(items=[
                            QuickReplyButton(action=MessageAction(label="準備好了", text="準備好了")),
                            QuickReplyButton(action=MessageAction(label="再聽一次", text="#repeat")),
                            QuickReplyButton(action=MessageAction(label="返回主選單", text="#menu"))
                        ])
                    )
                ]
            else:
                return TextSendMessage(text="目前不在問題回答階段，請按照指示進行。")
        
        # 使用 Whisper 將語音轉換為文本
        if hasattr(self, 'using_whisper') and self.using_whisper:
            try:
                # 轉錄音頻
                result = self.whisper_model.transcribe(audio_file_path)
                user_answer = result["text"]
                
                print(f"語音識別結果: {user_answer}")
                
                # 獲取當前問題
                current_index = session_data.get("current_question_index", 0)
                questions = session_data.get("questions", [])
                
                if not questions or current_index >= len(questions):
                    return TextSendMessage(text="所有問題已回答完畢，請重新開始練習。")
                
                current_question = questions[current_index]
                question_text = current_question.get("question", "")
                correct_answer = current_question.get("answer", "")
                
                # 評估回答
                evaluation = self.evaluate_user_answer(question_text, user_answer, correct_answer)
                
                # 保存分數
                scores = session_data.get("scores", [])
                scores.append(evaluation.get("score", 0))
                session_data["scores"] = scores
                
                # 準備下一個問題
                session_data["current_question_index"] = current_index + 1
                session_data["state"] = "listening"
                
                # 更新本地字典
                self.user_sessions[user_id] = session_data
                
                # 更新 UserSession
                session = UserSession.get_by_line_user_id(user_id)
                if session:
                    session.update({
                        "current_question_index": current_index + 1,
                        "scores": scores,
                        "state": "listening"
                    })
                
                # 發送評估結果
                feedback_message = (
                    f"您的語音回答: {user_answer}\n\n"
                    f"參考答案: {correct_answer}\n\n"
                    f"評分: {evaluation.get('score', 0)}/5\n"
                    f"反饋: {evaluation.get('feedback', '')}\n\n"
                    f"{evaluation.get('explanation', '')}"
                )
                
                # 檢查是否還有更多問題
                if current_index + 1 < len(questions):
                    # 還有更多問題
                    return [
                        TextSendMessage(text=feedback_message),
                        TextSendMessage(
                            text="準備好回答下一個問題了嗎？",
                            quick_reply=QuickReply(items=[
                                QuickReplyButton(action=MessageAction(label="準備好了", text="準備好了")),
                                QuickReplyButton(action=MessageAction(label="再聽一次", text="#repeat")),
                                QuickReplyButton(action=MessageAction(label="返回主選單", text="#menu"))
                            ])
                        )
                    ]
                else:
                    # 所有問題已回答完畢
                    self.complete_session(user_id, None)
                    return [
                        TextSendMessage(text=feedback_message),
                        TextSendMessage(text="所有問題已回答完畢，正在計算總分...")
                    ]
            except Exception as e:
                print(f"使用 Whisper 處理語音時發生錯誤: {str(e)}")
                traceback.print_exc()
        
        # 如果無法使用 Whisper 或處理失敗
        return TextSendMessage(
            text="很抱歉，無法處理您的語音回答。請嘗試以文字形式回答問題。",
            quick_reply=QuickReply(items=[
                QuickReplyButton(action=MessageAction(label="再聽一次", text="#repeat")),
                QuickReplyButton(action=MessageAction(label="返回主選單", text="#menu"))
            ])
        )