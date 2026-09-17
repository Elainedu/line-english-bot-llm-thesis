# Define LINE Bot listening practice topics and prompts
# Each topic includes an icon, description, and different difficulty levels.
import random

MAIN_LISTENING_TOPICS = {
    'greetings': {
        'icon': '👋',
        'levels': ['Beginner', 'Intermediate', 'Advanced'],
        'description': 'Listening practice: Common greetings and introductions.'
    },
    'weather': {
        'icon': '🌤️',
        'levels': ['Beginner', 'Intermediate', 'Advanced'],
        'description': 'Listening practice: Conversations about the weather.'
    },
    'food': {
        'icon': '🍔',
        'levels': ['Beginner', 'Intermediate', 'Advanced'],
        'description': 'Listening practice: Ordering food and discussing meals.'
    },
    'transportation': {
        'icon': '🚗',
        'levels': ['Beginner', 'Intermediate', 'Advanced'],
        'description': 'Listening practice: Talking about transportation and travel.'
    },
    'shopping': {
        'icon': '🛍️',
        'levels': ['Beginner', 'Intermediate', 'Advanced'],
        'description': 'Listening practice: Shopping and making purchases.'
    },
    'hobbies': {
        'icon': '🎨',
        'levels': ['Beginner', 'Intermediate', 'Advanced'],
        'description': 'Listening practice: Discussing hobbies and interests.'
    },
    'family': {
        'icon': '👨‍👩‍👧‍👦',
        'levels': ['Beginner', 'Intermediate', 'Advanced'],
        'description': 'Listening practice: Talking about family members and relationships.'
    },
    'health': {
        'icon': '💪',
        'levels': ['Beginner', 'Intermediate', 'Advanced'],
        'description': 'Listening practice: Conversations about health and fitness.'
    }
}

LISTENING_CONTENT_PROMPT_TEMPLATE = """Create a very concise English listening passage at {difficulty} level.
- For beginner: Use 5-8 words total
- For intermediate: Use 8-15 words total
- For advanced: Use 15-20 words total

Focus on clarity and brevity. Do NOT start with phrases like "Here is..." or "Sure..." Just begin directly with the content."""

# Define listening prompts for each topic and level
LISTENING_TOPIC_PROMPTS = {
    'greetings': {
        'Beginner': {
            'prompt': """You will hear a simple English conversation about greetings.

Goal: Understand common greetings and introductions.

Guidelines:
1. Listen to how people greet each other.
2. Includes common phrases like "Hello," "How are you?", and "Nice to meet you."
3. Recognize how people respond to greetings.

Examples:
- "Hi, how are you?"
- "Nice to meet you!"
- "Good morning!"

Difficulty: CEFR A1-A2 level."""
        },
        'Intermediate': {
            'prompt': """You will hear an intermediate-level conversation about greetings.

Goal: Understand more varied greetings and responses.

Guidelines:
1. Listen to greetings in different situations.
2. Includes more complex responses to questions like "How have you been?" or "How's your day?"
3. Recognize casual, friendly exchanges.

Examples:
- "Long time no see!"
- "How's it going?"
- "It's great to see you again!"

Difficulty: CEFR B1-B2 level."""
        },
        'Advanced': {
            'prompt': """You will hear an advanced conversation about greetings.

Goal: Understand sophisticated greetings and cultural differences in greetings.

Guidelines:
1. Listen to more formal and complex greetings.
2. Includes greetings in different cultural contexts and situations.
3. Understand professional and casual settings.

Examples:
- "It's a pleasure to meet you."
- "I hope you're doing well."
- "How's everything on your end?"

Difficulty: CEFR C1-C2 level."""
        }
    },
    'weather': {
        'Beginner': {
            'prompt': """You will hear a simple conversation about the weather.

Goal: Understand basic weather-related vocabulary and questions.

Guidelines:
1. Listen to how people talk about the weather.
2. Recognize simple phrases like "It's sunny," "It's cold," and "What's the weather like?"
3. Learn about different weather conditions.

Examples:
- "It's raining today."
- "How's the weather?"
- "It's really hot outside!"

Difficulty: CEFR A1-A2 level."""
        },
        'Intermediate': {
            'prompt': """You will hear an intermediate conversation about the weather.

Goal: Understand more detailed weather descriptions and forecasts.

Guidelines:
1. Listen to how people describe weather patterns and forecasts.
2. Includes phrases like "It might rain tomorrow," "The forecast says..." and "The temperature will be...".
3. Recognize discussions about different climates and weather conditions.

Examples:
- "The weather is going to be cold tomorrow."
- "It looks like it will be sunny this weekend."
- "The temperature will reach 30°C."

Difficulty: CEFR B1-B2 level."""
        },
        'Advanced': {
            'prompt': """You will hear an advanced conversation about the weather.

Goal: Understand detailed weather reports and professional language used in weather forecasting.

Guidelines:
1. Listen to meteorological terms and detailed weather discussions.
2. Recognize predictions and expert opinions on weather conditions.
3. Understand how weather affects different areas or events.

Examples:
- "The storm is expected to make landfall by tomorrow."
- "We're anticipating a cold front to move through the region."
- "The current high-pressure system will bring clear skies."

Difficulty: CEFR C1-C2 level."""
        }
    },
    'food': {
        'Beginner': {
            'prompt': """You will hear a simple conversation about food and ordering.

Goal: Understand basic food-related vocabulary and phrases for ordering food.

Guidelines:
1. Listen to how people order food at restaurants.
2. Recognize common food-related phrases like "What's for lunch?" or "I'd like a coffee."
3. Understand basic discussions about meals.

Examples:
- "Can I get a burger?"
- "I'll have a pizza, please."
- "What do you want for breakfast?"

Difficulty: CEFR A1-A2 level."""
        },
        'Intermediate': {
            'prompt': """You will hear an intermediate conversation about food.

Goal: Understand more detailed discussions about food preferences and dining.

Guidelines:
1. Listen to more detailed orders and descriptions of food.
2. Includes phrases like "What's your favorite dish?" or "Can I recommend the special?"
3. Recognize people talking about different types of food.

Examples:
- "I'd like the grilled chicken, please."
- "Do you prefer spicy or mild food?"
- "What's the best dish on the menu?"

Difficulty: CEFR B1-B2 level."""
        },
        'Advanced': {
            'prompt': """You will hear an advanced conversation about food.

Goal: Understand professional food terminology and detailed discussions about cuisine.

Guidelines:
1. Listen to discussions on food preparation, cooking methods, and ingredients.
2. Includes conversations between chefs or food critics.
3. Understand discussions about food culture and fine dining.

Examples:
- "This dish is prepared using a sous-vide method."
- "The flavor profile of this wine pairs well with the dish."
- "This is a traditional French recipe."

Difficulty: CEFR C1-C2 level."""
        }
    },
    'transportation': {
        'Beginner': {
            'prompt': """You will hear a simple conversation about transportation.

Goal: Understand basic vocabulary related to transportation and travel.

Guidelines:
1. Listen to how people talk about getting around (bus, train, taxi).
2. Recognize simple phrases like "Where's the bus stop?" or "How do I get to the station?"
3. Understand basic directions and transportation-related questions.

Examples:
- "How do I get to the airport?"
- "I need to take a taxi."
- "Which bus goes to the mall?"

Difficulty: CEFR A1-A2 level."""
        },
        'Intermediate': {
            'prompt': """You will hear an intermediate conversation about transportation.

Goal: Understand more detailed discussions about different modes of transport.

Guidelines:
1. Listen to descriptions of transportation schedules, routes, and fares.
2. Includes phrases like "Is this the right train to...?" or "How much is a ticket to...?"
3. Recognize conversations about booking travel tickets or planning trips.

Examples:
- "When does the next train leave?"
- "What's the fastest way to get there?"
- "Are there any discounts for students?"

Difficulty: CEFR B1-B2 level."""
        },
        'Advanced': {
            'prompt': """You will hear an advanced conversation about transportation.

Goal: Understand in-depth discussions about transportation systems and travel logistics.

Guidelines:
1. Listen to discussions on transportation policies, infrastructure, and future improvements.
2. Recognize advanced vocabulary related to transportation.
3. Understand technical details on flight, train, or road systems.

Examples:
- "The airport expansion will significantly increase capacity."
- "We're working on upgrading the railway lines to accommodate high-speed trains."
- "The government is implementing stricter regulations for road safety."

Difficulty: CEFR C1-C2 level."""
        }
    }
}

# 系統提示
LISTENING_SYSTEM_PROMPT = """You are an English language assistant creating short listening practice content."""

# 內容生成模板
LISTENING_CONTENT_PROMPT_TEMPLATE = """Create a very short English listening passage at {difficulty} level.
- For beginner: Use only basic words and very simple sentences (10-30 words)
- For intermediate: Use simple sentences with common expressions (30-50 words)
- For advanced: Use natural language with more complex structure (50-80 words)

Do NOT start with phrases like "Here is..." or "Sure..." Just begin directly with the content."""

# 問題生成模板
LISTENING_QUESTIONS_PROMPT_TEMPLATE = """Based on this listening passage: 
"{content}"

Create {question_count} simple comprehension questions at {difficulty} level.
Return ONLY a JSON array of objects, each with "question" and "answer" fields.
Make questions very simple and directly answerable from the passage."""

# 評估模板
LISTENING_EVALUATION_PROMPT_TEMPLATE = """Question: {question}
User's answer: {user_answer}
Correct answer: {correct_answer}

Evaluate how accurately the user's answer matches the correct answer.
Return ONLY a JSON object with:
- score (0-100)
- feedback (1-2 short sentences)
- explanation (1 short sentence)"""

# 根據難度獲取問題數量
def get_question_count(difficulty):
    if difficulty.lower() == "beginner":
        return 1
    elif difficulty.lower() == "intermediate":
        return 1
    else:  # advanced
        return 3