import os
import json
import time
import random
import traceback
import requests
from linebot.models import (
    TextSendMessage,
    QuickReplyButton, QuickReply, MessageAction, PostbackAction
)

# 導入提示模板 (如果沒有這個文件，我們會使用內部預設值)
try:
    from app.features.voc.prompts.voc_prompts import VOCAB_PROMPTS
except ImportError:
    # 預設提示詞
    VOCAB_PROMPTS = {
        "初級": {
            "system_prompt": "你是一位英語教師，幫助初級英語學習者學習基本詞彙。提供簡單易懂的單詞解釋和基礎例句。"
        },
        "中級": {
            "system_prompt": "你是一位英語教師，幫助中級英語學習者擴展詞彙量。提供更詳細的單詞解釋和適中難度的例句。"
        },
        "高級": {
            "system_prompt": "你是一位英語教師，幫助高級英語學習者掌握進階詞彙。提供專業的單詞解釋和複雜的例句。"
        }
    }

class VocabularyService:
    def __init__(self, line_bot_api):
        """初始化詞彙練習服務"""
        print("初始化詞彙練習服務...")
        self.line_bot_api = line_bot_api
        self.user_sessions = {}
        
        # 設置OpenAI API金鑰 (如果有的話)
        self.openai_api_key = os.getenv('OPENAI_API_KEY')
        
        # 從 prompt 文件中導入詞彙集
        try:
            from app.features.voc.prompts.voc_prompts import DEFAULT_WORD_SETS
            self.word_sets = DEFAULT_WORD_SETS
        except ImportError:
            # 如果無法導入，給出錯誤消息
            print("警告：無法從 prompt 文件導入詞彙集，請確保 voc_prompts.py 文件存在並包含 DEFAULT_WORD_SETS。")
            self.word_sets = {}
        
        print("詞彙練習服務初始化完成")

    def handle_text_message(self, event):
        """處理文字訊息"""
        try:
            user_id = event.source.user_id
            text = event.message.text.strip()
            reply_token = event.reply_token
            
            print(f"詞彙服務收到訊息: {text}")
            
            # 如果是開始詞彙練習的指令
            if text.startswith("#start_vocabulary") or text.startswith("#vocab"):
                print("收到詞彙練習指令")
                # 更新用戶狀態為等待難度選擇
                self.user_sessions[user_id] = {
                    'state': 'waiting_for_difficulty',
                    'last_command': text
                }
                
                # 發送難度選擇選項
                items = [
                    QuickReplyButton(action=MessageAction(label="初級", text="beginner")),
                    QuickReplyButton(action=MessageAction(label="中級", text="intermediate")),
                    QuickReplyButton(action=MessageAction(label="高級", text="advanced"))
                ]
                
                quick_reply = TextSendMessage(
                    text="請選擇詞彙練習的難易度：",
                    quick_reply=QuickReply(items=items)
                )
                
                self.line_bot_api.reply_message(reply_token, quick_reply)
                print("已發送難度選擇選項")
                return
                
            # 如果是等待難度選擇的狀態
            elif user_id in self.user_sessions and self.user_sessions[user_id].get('state') == 'waiting_for_difficulty':
                print(f"用戶正在等待詞彙練習難度選擇，收到: {text}")
                
                # 處理難度選擇 - 支持中文和英文難度選擇
                valid_difficulties = {
                    "初級": "beginner", 
                    "中級": "intermediate", 
                    "高級": "advanced",
                    "beginner": "beginner",
                    "intermediate": "intermediate",
                    "advanced": "advanced"
                }
                
                if text in valid_difficulties:
                    difficulty = valid_difficulties[text]
                    self.start_vocabulary_session(user_id, difficulty, reply_token)
                else:
                    # 如果輸入的不是有效的難度，提示重新選擇
                    self.line_bot_api.reply_message(
                        reply_token,
                        TextSendMessage(text="請選擇有效的難度：初級(beginner)、中級(intermediate)或高級(advanced)")
                    )
                return
                
            # 如果是更換單字指令
            elif text == "#change_word":
                if user_id in self.user_sessions and self.user_sessions[user_id].get('state') == 'in_vocabulary':
                    self.change_word(user_id, reply_token)
                else:
                    self.line_bot_api.reply_message(
                        reply_token,
                        TextSendMessage(text="您目前沒有進行中的詞彙練習。請輸入 #start_vocabulary 開始練習。")
                    )
                return
                
            # 如果是結束練習指令
            elif text == "#end_vocabulary" or text == "結束練習":
                if user_id in self.user_sessions:
                    self.end_vocabulary_session(user_id, reply_token)
                else:
                    self.line_bot_api.reply_message(
                        reply_token,
                        TextSendMessage(text="您目前沒有進行中的詞彙練習。")
                    )
                return
                
            # 如果是"下一個單字"指令
            elif text == "下一個單字":
                if user_id in self.user_sessions and self.user_sessions[user_id].get('state') == 'in_vocabulary':
                    self.change_word(user_id, reply_token)
                else:
                    self.line_bot_api.reply_message(
                        reply_token,
                        TextSendMessage(text="您目前沒有進行中的詞彙練習。請輸入 #start_vocabulary 開始練習。")
                    )
                return
                
            # 如果是"再來一次"指令
            elif text == "再來一次":
                print("用戶選擇再來一次")
                # 更新用戶狀態為等待難度選擇
                self.user_sessions[user_id] = {
                    'state': 'waiting_for_difficulty',
                    'last_command': "#start_vocabulary"
                }
                
                # 發送難度選擇選項
                items = [
                    QuickReplyButton(action=MessageAction(label="初級", text="beginner")),
                    QuickReplyButton(action=MessageAction(label="中級", text="intermediate")),
                    QuickReplyButton(action=MessageAction(label="高級", text="advanced"))
                ]
                
                quick_reply = TextSendMessage(
                    text="請選擇詞彙練習的難易度：",
                    quick_reply=QuickReply(items=items)
                )
                
                self.line_bot_api.reply_message(reply_token, quick_reply)
                return
                
            # 如果是單字造句指令
            elif text.startswith("#vocab "):
                word = text[7:].strip()
                if not word:
                    self.line_bot_api.reply_message(
                        reply_token,
                        TextSendMessage(text="請在 #vocab 後加上您想練習的單字，例如：#vocab apple")
                    )
                    return
                    
                # 進行單字造句練習
                self.practice_word(user_id, word, reply_token)
                return
                
            # 如果用戶已在詞彙練習中
            elif user_id in self.user_sessions and self.user_sessions[user_id].get('state') == 'in_vocabulary':
                # 處理用戶造句回覆
                current_word = self.user_sessions[user_id].get('current_word', '')
                self.evaluate_sentence(user_id, text, current_word, reply_token)
                return
                
            # 其他不明確的情況，顯示幫助訊息
            else:
                topics = ["apple", "book", "computer", "dog", "education"]
                self.line_bot_api.reply_message(
                    reply_token,
                    [
                        TextSendMessage(text="請選擇一個單字練習造句，或輸入 #start_vocabulary 開始詞彙練習："),
                        TextSendMessage(
                            text="單字選擇",
                            quick_reply=QuickReply(items=[
                                QuickReplyButton(action=MessageAction(label=word, text=f"#vocab {word}"))
                                for word in topics
                            ])
                        )
                    ]
                )
                return
                    
        except Exception as e:
            print(f"詞彙練習處理訊息時發生錯誤: {str(e)}")
            traceback.print_exc()
            self.line_bot_api.reply_message(
                reply_token,
                TextSendMessage(text="處理您的訊息時發生錯誤，請稍後再試。")
            )

    def start_vocabulary_session(self, user_id, difficulty, reply_token):
        """啟動詞彙練習會話"""
        try:
            print(f"啟動難度為 {difficulty} 的詞彙練習")
            
            # 獲取對應難度的單詞集
            words = self.word_sets.get(difficulty, [])
            
            # 隨機選擇一個單詞
            if not words:
                print(f"沒有找到難度 {difficulty} 的單詞集")
                self.line_bot_api.reply_message(
                    reply_token, 
                    TextSendMessage(text="抱歉，無法獲取單詞列表，請稍後再試。")
                )
                return
                    
            current_word = random.choice(words)
            
            # 更新用戶狀態
            self.user_sessions[user_id] = {
                'state': 'in_vocabulary',
                'difficulty': difficulty,
                'words': words,
                'current_word': current_word,
                'practiced_words': [],
                'waiting_for_sentence': True  # 標記用戶需要提供造句
            }
            
            # 從提示詞模板獲取系統提示詞
            try:
                from app.features.voc.prompts.voc_prompts import VOCAB_PROMPTS
                system_prompt = VOCAB_PROMPTS[difficulty]['system_prompt']
                
                # 使用 OpenAI API 生成單字介紹
                headers = {
                    "Authorization": f"Bearer {self.openai_api_key}",
                    "Content-Type": "application/json"
                }
                
                payload = {
                    "model": "gpt-3.5-turbo",
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": f"Please introduce the word '{current_word}' for practice."}
                    ],
                    "temperature": 0.7
                }
                
                response = requests.post(
                    "https://api.openai.com/v1/chat/completions",
                    headers=headers,
                    data=json.dumps(payload)
                )
                
                if response.status_code == 200:
                    response_data = response.json()
                    content = response_data['choices'][0]['message']['content'].strip()
                    
                    # 發送單詞練習訊息
                    self.line_bot_api.reply_message(reply_token, TextSendMessage(text=content))
                    print(f"詞彙練習會話已啟動，當前單字: {current_word}")
                    return
            except Exception as e:
                print(f"使用 OpenAI API 生成單字介紹時發生錯誤: {str(e)}")
                
            # 如果 API 調用失敗，使用備用方法
            # 生成單詞釋義和例句
            english_definition, chinese_definition, example = self.generate_word_content(current_word, difficulty)
            
            # 發送單詞練習訊息 (不包含例句)
            messages = [
                TextSendMessage(text=f"已選擇{difficulty}難度的詞彙練習。"),
                TextSendMessage(text=f"**今日單字:**\n- **{current_word.lower()}** (noun): {english_definition}"),
                TextSendMessage(text=f"你可以用「{current_word}」造一個句子嗎？"),
            ]
            
            self.line_bot_api.reply_message(reply_token, messages)
            print(f"詞彙練習會話已啟動，當前單字: {current_word}")
            
        except Exception as e:
            print(f"啟動詞彙練習會話時發生錯誤: {str(e)}")
            traceback.print_exc()
            self.line_bot_api.reply_message(
                reply_token,
                TextSendMessage(text="啟動詞彙練習時發生錯誤，請稍後再試。")
            )

    def generate_word_content(self, word, difficulty):
        """生成單詞釋義和例句"""
        try:
            from app.features.voc.prompts.voc_prompts import WORD_CONTENT_PROMPTS, SYSTEM_PROMPTS, PREDEFINED_WORD_CONTENT
            
            # 嘗試使用 OpenAI API 生成內容 (如果API金鑰存在)
            if self.openai_api_key:
                # 獲取對應難度的提示詞
                prompt = WORD_CONTENT_PROMPTS.get(difficulty, WORD_CONTENT_PROMPTS["beginner"]).format(word=word)
                system_prompt = SYSTEM_PROMPTS["word_content"]
                
                # 呼叫 OpenAI API
                try:
                    headers = {
                        "Authorization": f"Bearer {self.openai_api_key}",
                        "Content-Type": "application/json"
                    }
                    
                    payload = {
                        "model": "gpt-3.5-turbo",
                        "messages": [
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": prompt}
                        ],
                        "temperature": 0.7
                    }
                    
                    response = requests.post(
                        "https://api.openai.com/v1/chat/completions",
                        headers=headers,
                        data=json.dumps(payload)
                    )
                    
                    if response.status_code == 200:
                        response_data = response.json()
                        content = response_data['choices'][0]['message']['content'].strip()
                        
                        # 解析回應，獲取英文釋義、中文釋義和例句
                        english_def = ""
                        chinese_def = ""
                        example = ""
                        
                        lines = content.split('\n')
                        for line in lines:
                            if "English Definition" in line:
                                english_def = line.split(':', 1)[1].strip() if ':' in line else ""
                            elif "Chinese Definition" in line:
                                chinese_def = line.split(':', 1)[1].strip() if ':' in line else ""
                            elif "Example" in line:
                                example = line.split(':', 1)[1].strip() if ':' in line else ""
                        
                        # 確保有值
                        if english_def and chinese_def and example:
                            return english_def, chinese_def, example
                except Exception as api_e:
                    print(f"API調用失敗: {str(api_e)}")
            
            # 使用預定義的內容（當API調用失敗或無API密鑰時）
            if word.lower() in PREDEFINED_WORD_CONTENT:
                return (
                    PREDEFINED_WORD_CONTENT[word.lower()]["english_definition"],
                    PREDEFINED_WORD_CONTENT[word.lower()]["chinese_definition"],
                    PREDEFINED_WORD_CONTENT[word.lower()]["example"]
                )
            
            # 否則生成通用內容
            difficulty_level = {"beginner": "easy", "intermediate": "medium", "advanced": "advanced"}
            return (
                f"A common {difficulty_level.get(difficulty, 'medium')} level English word.",
                f"{word} - 這是一個{difficulty_level.get(difficulty, '中等')}難度的英文單字。",
                f"Here's a sentence using the word '{word}'."
            )
                
        except Exception as e:
            print(f"生成單詞內容時發生錯誤: {str(e)}")
            return (
                f"A common English word",
                f"{word} - 英文單字",
                f"Please make a sentence using the word '{word}'."
            )

    def evaluate_sentence(self, user_id, sentence, word, reply_token):
        """評估用戶的造句"""
        try:
            print(f"評估用戶造句: '{sentence}', 單字: '{word}'")
            
            # 檢查句子中是否包含單詞
            if word.lower() not in sentence.lower():
                self.line_bot_api.reply_message(
                    reply_token,
                    TextSendMessage(text=f"您的句子中沒有包含單字 '{word}'。請重新嘗試。")
                )
                return
            
            # 獲取用戶的難度級別
            difficulty = self.user_sessions[user_id].get('difficulty', 'beginner')
            
            # 從提示詞模板獲取系統提示詞
            try:
                from app.features.voc.prompts.voc_prompts import VOCAB_PROMPTS
                system_prompt = VOCAB_PROMPTS[difficulty]['system_prompt']
                
                # 使用 OpenAI API 評估造句並生成回饋
                headers = {
                    "Authorization": f"Bearer {self.openai_api_key}",
                    "Content-Type": "application/json"
                }
                
                # 生成一個簡單的單字介紹訊息
                intro_message = f"**Today's Word:**\n- **{word}** (noun): a common {difficulty} level English word"
                
                payload = {
                    "model": "gpt-3.5-turbo",
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "assistant", "content": intro_message},
                        {"role": "user", "content": sentence}
                    ],
                    "temperature": 0.7
                }
                
                response = requests.post(
                    "https://api.openai.com/v1/chat/completions",
                    headers=headers,
                    data=json.dumps(payload)
                )
                
                if response.status_code == 200:
                    response_data = response.json()
                    feedback_content = response_data['choices'][0]['message']['content'].strip()
                    
                    # 記錄已練習的單詞
                    if 'practiced_words' not in self.user_sessions[user_id]:
                        self.user_sessions[user_id]['practiced_words'] = []
                    
                    self.user_sessions[user_id]['practiced_words'].append(word)
                    
                    # 準備下一個單詞
                    next_word = self.get_next_word(user_id)
                    self.user_sessions[user_id]['current_word'] = next_word
                    
                    # 發送評估結果和回饋
                    self.line_bot_api.reply_message(
                        reply_token,
                        [
                            TextSendMessage(text=feedback_content),
                            TextSendMessage(
                                text="繼續練習還是結束？",
                                quick_reply=QuickReply(items=[
                                    QuickReplyButton(action=MessageAction(label="更換單字", text="#change_word")),
                                    QuickReplyButton(action=MessageAction(label="結束練習", text="#end_vocabulary"))
                                ])
                            )
                        ]
                    )
                    print(f"評估完成，下一個單字: {next_word}")
                    return
            except Exception as e:
                print(f"使用 OpenAI API 評估造句時發生錯誤: {str(e)}")
            
            # 如果 API 調用失敗，使用備用方法
            # 生成評分和反饋
            score, feedback = self.generate_sentence_feedback(sentence, word, difficulty)
            
            # 記錄已練習的單詞
            if 'practiced_words' not in self.user_sessions[user_id]:
                self.user_sessions[user_id]['practiced_words'] = []
            
            self.user_sessions[user_id]['practiced_words'].append(word)
            
            # 準備下一個單詞
            next_word = self.get_next_word(user_id)
            self.user_sessions[user_id]['current_word'] = next_word
            
            # 生成下一個單詞的釋義和例句
            english_definition, chinese_definition, example = self.generate_word_content(next_word, difficulty)
            
            # 發送評估結果
            messages = [
                TextSendMessage(text=f"**Example:** {example}"),
                TextSendMessage(text=f"**Your sentence:** {sentence}"),
                TextSendMessage(text=f"**Comments:** {feedback}"),
                TextSendMessage(text=f"\n**Today's Word:**\n- **{next_word.lower()}** (noun): {english_definition}"),
                TextSendMessage(text=f"你可以用「{next_word}」造一個句子嗎？"),
                TextSendMessage(
                    text="或者選擇：",
                    quick_reply=QuickReply(items=[
                        QuickReplyButton(action=MessageAction(label="更換單字", text="#change_word")),
                        QuickReplyButton(action=MessageAction(label="結束練習", text="#end_vocabulary"))
                    ])
                )
            ]
            
            self.line_bot_api.reply_message(reply_token, messages)
            print(f"評估完成，下一個單字: {next_word}")
            
        except Exception as e:
            print(f"評估用戶造句時發生錯誤: {str(e)}")
            traceback.print_exc()
            self.line_bot_api.reply_message(
                reply_token,
                TextSendMessage(text="評估您的造句時發生錯誤，請稍後再試。")
            )

    def generate_sentence_feedback(self, sentence, word, difficulty):
        """生成造句評價"""
        try:
            from app.features.voc.prompts.voc_prompts import SENTENCE_EVALUATION_PROMPTS, SYSTEM_PROMPTS
            
            # 嘗試使用 OpenAI API 評估造句 (如果API金鑰存在)
            if self.openai_api_key:
                # 獲取對應難度的提示詞
                prompt = SENTENCE_EVALUATION_PROMPTS.get(difficulty, SENTENCE_EVALUATION_PROMPTS["beginner"]).format(
                    word=word, sentence=sentence
                )
                system_prompt = SYSTEM_PROMPTS["sentence_evaluation"]
                
                # 呼叫 OpenAI API
                try:
                    headers = {
                        "Authorization": f"Bearer {self.openai_api_key}",
                        "Content-Type": "application/json"
                    }
                    
                    payload = {
                        "model": "gpt-3.5-turbo",
                        "messages": [
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": prompt}
                        ],
                        "temperature": 0.7
                    }
                    
                    response = requests.post(
                        "https://api.openai.com/v1/chat/completions",
                        headers=headers,
                        data=json.dumps(payload)
                    )
                    
                    if response.status_code == 200:
                        response_data = response.json()
                        content = response_data['choices'][0]['message']['content'].strip()
                        
                        # 解析內容，提取評分和反饋
                        import re
                        score_match = re.search(r'Score:\s*(\d+)', content)
                        score = 75  # 默認評分
                        
                        if score_match:
                            score = int(score_match.group(1))
                        
                        # 提取反饋部分
                        feedback_match = re.search(r'Feedback:(.*?)($|Score:)', content, re.DOTALL)
                        if feedback_match:
                            feedback = feedback_match.group(1).strip()
                        else:
                            # 如果無法提取，使用整個回應作為反饋
                            feedback = content.replace(f"Score: {score}", "").strip()
                        
                        return score, feedback
                except Exception as api_e:
                    print(f"API調用失敗: {str(api_e)}")
            
            # 使用基本評估（當API調用失敗或無API密鑰時）
            words = sentence.split()
            score = min(90, 50 + 10 * min(len(words), 5))
            
            # 根據難度和句子長度給出不同的反饋
            if len(words) > 10:
                feedback = "很好！您的句子結構完整，單詞使用正確。繼續保持！"
            elif len(words) > 6:
                feedback = "不錯！您的句子清晰表達了意思。可以嘗試加入更多細節。"
            else:
                feedback = "基本正確。下次可以嘗試創造更長、更豐富的句子。"
            
            return score, feedback
                
        except Exception as e:
            print(f"生成句子反饋時發生錯誤: {str(e)}")
            return 70, "句子結構良好，單詞使用正確。"

    def get_next_word(self, user_id):
        """獲取下一個要練習的單詞"""
        try:
            # 獲取用戶會話
            session = self.user_sessions.get(user_id, {})
            words = session.get('words', [])
            practiced_words = session.get('practiced_words', [])
            
            # 如果沒有單詞列表，返回默認單詞
            if not words:
                return "example"
                
            # 如果所有單詞都已練習過，重置練習記錄
            if len(practiced_words) >= len(words):
                import random
                return random.choice(words)
            
            # 選擇一個未練習過的單詞
            available_words = [w for w in words if w not in practiced_words]
            import random
            return random.choice(available_words)
            
        except Exception as e:
            print(f"獲取下一個單詞時發生錯誤: {str(e)}")
            # 返回一個默認值
            return "book"

    def change_word(self, user_id, reply_token):
        """更換練習單詞"""
        try:
            # 獲取新單詞
            next_word = self.get_next_word(user_id)
            difficulty = self.user_sessions[user_id].get('difficulty', '初級')
            
            # 更新當前單詞
            self.user_sessions[user_id]['current_word'] = next_word
            
            # 生成單詞釋義和例句
            definition, example = self.generate_word_content(next_word, difficulty)
            
            # 發送新單詞
            messages = [
                TextSendMessage(text=f"已更換單字: {next_word.upper()}"),
                TextSendMessage(text=f"釋義: {definition}"),
                TextSendMessage(text=f"例句: {example}"),
                TextSendMessage(
                    text="請使用這個單字造一個句子。",
                    quick_reply=QuickReply(items=[
                        QuickReplyButton(action=MessageAction(label="更換單字", text="#change_word")),
                        QuickReplyButton(action=MessageAction(label="結束練習", text="#end_vocabulary"))
                    ])
                )
            ]
            
            self.line_bot_api.reply_message(reply_token, messages)
            print(f"單字已更換為: {next_word}")
            
        except Exception as e:
            print(f"更換單詞時發生錯誤: {str(e)}")
            traceback.print_exc()
            self.line_bot_api.reply_message(
                reply_token,
                TextSendMessage(text="更換單字時發生錯誤，請稍後再試。")
            )

    def end_vocabulary_session(self, user_id, reply_token):
        """結束詞彙練習會話"""
        try:
            session = self.user_sessions.get(user_id, {})
            practiced_words = session.get('practiced_words', [])
            difficulty = session.get('difficulty', '未知')
            
            # 刪除會話
            if user_id in self.user_sessions:
                del self.user_sessions[user_id]
            
            # 準備練習總結
            message = f"詞彙練習已結束。\n\n難度: {difficulty}\n練習單字數: {len(practiced_words)}"
            
            if practiced_words:
                message += f"\n\n練習過的單字: {', '.join(practiced_words)}"
            
            # 添加返回選單選項
            self.line_bot_api.reply_message(
                reply_token,
                [
                    TextSendMessage(text=message),
                    TextSendMessage(
                        text="請選擇下一步操作：",
                        quick_reply=QuickReply(items=[
                            QuickReplyButton(action=MessageAction(label="返回主選單", text="#menu")),
                            QuickReplyButton(action=MessageAction(label="再次練習", text="#start_vocabulary"))
                        ])
                    )
                ]
            )
            print(f"用戶 {user_id} 的詞彙練習會話已結束")
            
        except Exception as e:
            print(f"結束詞彙練習會話時發生錯誤: {str(e)}")
            traceback.print_exc()
            self.line_bot_api.reply_message(
                reply_token,
                TextSendMessage(text="結束練習時發生錯誤，請稍後再試。")
            )

    def practice_word(self, user_id, word, reply_token):
        """針對特定單字進行造句練習"""
        try:
            # 更新用戶狀態
            self.user_sessions[user_id] = {
                'state': 'in_vocabulary',
                'difficulty': '中級',  # 默認中級難度
                'words': [word],
                'current_word': word,
                'practiced_words': []
            }
            
            # 生成單詞釋義和例句
            definition, example = self.generate_word_content(word, '中級')
            
            # 發送單詞練習訊息
            messages = [
                TextSendMessage(text=f"單字: {word.upper()}"),
                TextSendMessage(text=f"釋義: {definition}"),
                TextSendMessage(text=f"例句: {example}"),
                TextSendMessage(
                    text="請使用這個單字造一個句子。完成後，您將獲得評分和反饋。",
                    quick_reply=QuickReply(items=[
                        QuickReplyButton(action=MessageAction(label="更換單字", text="#change_word")),
                        QuickReplyButton(action=MessageAction(label="結束練習", text="#end_vocabulary"))
                    ])
                )
            ]
            
            self.line_bot_api.reply_message(reply_token, messages)
            print(f"單字練習已開始，單字: {word}")
            
        except Exception as e:
            print(f"開始單字練習時發生錯誤: {str(e)}")
            traceback.print_exc()
            self.line_bot_api.reply_message(
                reply_token,
                TextSendMessage(text="開始單字練習時發生錯誤，請稍後再試。")
            )