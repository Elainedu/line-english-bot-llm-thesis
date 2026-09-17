import random

# 對話主題 - 只保留點餐和興趣
CONVERSATION_TOPICS = {
    "restaurant": {
        "zh_name": "點餐",
        "en_name": "Restaurant",
        "emoji": "🍽️"
    },
    "hobbies": {
        "zh_name": "興趣愛好",
        "en_name": "Hobbies",
        "emoji": "🎯"
    }
}

# 難度設定
DIFFICULTY_GUIDELINES = {
    "Beginner": {
        "Vocabulary Requirements": "Use basic everyday vocabulary",
        "Sentence Requirements": "Use simple sentences, present tense",
        "Question Style": "Short, direct questions"
    },
    "Intermediate": {
        "Vocabulary Requirements": "Use common daily vocabulary",
        "Sentence Requirements": "Use complex sentences, different tenses",
        "Question Style": "Open-ended questions"
    },
    "Advanced": {
        "Vocabulary Requirements": "Use specialized vocabulary",
        "Sentence Requirements": "Complex structures, various tenses",
        "Question Style": "In-depth discussion questions"
    }
}

# 主題指南
TOPIC_GUIDELINES = {
    "restaurant": {
        "context": "Restaurant setting - ordering, menu, payment",
        "Beginner": {
            "vocabulary": ["menu", "order", "drink", "food", "price", "water", "tea", "coffee", "pay"],
            "question_types": ["Asking about menu", "Placing order", "Inquiring prices"]
        },
        "Intermediate": {
            "vocabulary": ["recommend", "special", "ingredient", "allergy", "reservation", "appetizer"],
            "question_types": ["Asking recommendations", "Special requests", "Making reservations"]
        },
        "Advanced": {
            "vocabulary": ["culinary", "cuisine", "sommelier", "dietary restriction", "locally-sourced"],
            "question_types": ["Discussing food philosophy", "Wine pairings", "Creative cuisine"]
        }
    },
    "hobbies": {
        "context": "Discussing interests and hobbies",
        "Beginner": {
            "vocabulary": ["hobby", "like", "enjoy", "play", "watch", "read", "music", "sports"],
            "question_types": ["What hobbies", "Favorite activities", "Free time"]
        },
        "Intermediate": {
            "vocabulary": ["passionate", "interest", "skill", "talent", "practice", "improve", "achieve"],
            "question_types": ["Why this hobby", "How started", "Skills developed"]
        },
        "Advanced": {
            "vocabulary": ["expertise", "dedication", "philosophy", "methodology", "influential", "perspective"],
            "question_types": ["Hobby philosophy", "Skill mastery", "Personal growth"]
        }
    }
}

# 場景描述
SCENE_DESCRIPTIONS = {
    "restaurant": {
        "Beginner": "Ordering at a café",
        "Intermediate": "Dining at a family restaurant",
        "Advanced": "Experiencing fine dining"
    },
    "hobbies": {
        "Beginner": "Talking about what you like to do",
        "Intermediate": "Discussing favorite activities",
        "Advanced": "Exploring personal passions"
    }
}

# 開場對話
CONVERSATION_STARTERS = {
    "restaurant": {
        "Beginner": [
            "What would you like?",
            "Are you ready to order?",
            "Tea or coffee?"
        ],
        "Intermediate": [
            "Any recommendations?",
            "What's your favorite cuisine?",
            "Any food allergies?"
        ],
        "Advanced": [
            "Any dietary preferences?",
            "Local specialties interest you?",
            "Wine pairing suggestions?"
        ]
    },
    "hobbies": {
        "Beginner": [
            "What's your hobby?",
            "What do you like?",
            "Do you play sports?"
        ],
        "Intermediate": [
            "What are you passionate about?",
            "How did you start this hobby?",
            "What skills have you developed?"
        ],
        "Advanced": [
            "What drives your passion?",
            "How has this hobby shaped you?",
            "What's your approach to mastery?"
        ]
    }
}

# AI 對話指令
AI_CONVERSATION_INSTRUCTIONS = """
You are a real conversation partner in a specific scenario.

Guidelines:
1. Start with brief scene description in Chinese using 【】
2. You are a real person, not a language teacher
3. Keep responses very brief:
   - Beginner: 1 short sentence (5-7 words max)
   - Intermediate: 1 sentence (10 words max)  
   - Advanced: 1-2 sentences (12 words per sentence max)
4. Ask specific, targeted questions
5. Continue the current topic, don't jump around
6. No corrections or evaluations
"""

def get_topic_prompt(topic, difficulty):
    """生成系統提示"""
    difficulty_cap = difficulty.capitalize()
    
    topic_guide = TOPIC_GUIDELINES.get(topic, {})
    context = topic_guide.get('context', f"Conversation about {topic}")
    level_guide = topic_guide.get(difficulty_cap, {})
    
    vocabulary = level_guide.get('vocabulary', [])
    question_types = level_guide.get('question_types', [])
    
    system_prompt = f"""
{AI_CONVERSATION_INSTRUCTIONS}

Topic: {topic}
Context: {context}
Difficulty: {difficulty_cap}

Suggested Vocabulary: {', '.join(vocabulary[:8])}
Question Types: {', '.join(question_types)}

Begin the conversation immediately with an appropriate opening.
"""
    
    return system_prompt

def generate_conversation_scene(topic, difficulty):
    """生成對話場景"""
    return f"{topic} conversation scene"

def generate_creative_prompt(topic, difficulty, history):
    """生成創意提示"""
    return None