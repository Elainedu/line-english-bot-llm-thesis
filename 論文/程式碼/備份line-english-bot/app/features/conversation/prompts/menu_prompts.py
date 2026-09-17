# ===== menu_prompts.py =====
import random

# ===== Difficulty Level Settings =====
DIFFICULTY_LEVELS = {
    "Beginner": "Beginner",
    "Intermediate": "Intermediate",
    "Advanced": "Advanced"
}

# ===== Conversation Topics =====
CONVERSATION_TOPICS = {
    "self_intro": {
        "zh_name": "自我介紹",
        "en_name": "Self Introduction",
        "emoji": "👋"
    },
    "travel": {
        "zh_name": "旅遊",
        "en_name": "Travel",
        "emoji": "🏝️"
    },
    "restaurant": {
        "zh_name": "點餐",
        "en_name": "Restaurant",
        "emoji": "🍽️"
    },
    "shopping": {
        "zh_name": "購物",
        "en_name": "Shopping",
        "emoji": "🛍️"
    },
    "directions": {
        "zh_name": "問路",
        "en_name": "Asking for Directions",
        "emoji": "🗺️"
    }
}

# ===== Detailed Guidelines Based on Difficulty =====
DIFFICULTY_GUIDELINES = {
    "Beginner": {
        "Vocabulary Requirements": "Use only basic everyday vocabulary, words usually no longer than 2-3 syllables",
        "Sentence Requirements": "Use simple, direct sentence structures, mainly simple present tense, avoid complex tenses",
        "Question Style": "Short, direct questions that usually require only yes/no answers or phrase responses",
        "Speech Rate Suggestion": "Speak slowly, clearly, repeat key words",
        "Example Sentences": "What's your name? Where are you from? Do you like coffee?"
    },
    "Intermediate": {
        "Vocabulary Requirements": "Use common vocabulary from daily life, can include some frequently used specialized terms",
        "Sentence Requirements": "Use more complex sentence structures, include different tenses and modal verbs",
        "Question Style": "Open-ended questions requiring more detailed answers",
        "Speech Rate Suggestion": "Normal speech rate, natural intonation and emphasis",
        "Example Sentences": "What kind of movies do you enjoy watching? Could you tell me about your hometown?"
    },
    "Advanced": {
        "Vocabulary Requirements": "Can use specialized vocabulary, abstract concepts and academic terms",
        "Sentence Requirements": "Complex sentence structures, including clauses, conditionals, passive voice, etc.",
        "Question Style": "In-depth discussion questions requiring analysis, evaluation or hypothesizing",
        "Speech Rate Suggestion": "Natural speech rate, including colloquial expressions and language nuances",
        "Example Sentences": "How do you think technology has influenced modern communication patterns?"
    }
}

# ===== Topic Scene Guidelines =====
TOPIC_GUIDELINES = {
    "restaurant": {
        "context": "Restaurant setting, including ordering, asking about the menu, food preparation, paying the bill, etc.",
        "roles": ["Customer", "Server", "Chef", "Restaurant Manager"],
        "Beginner": {
            "scene_examples": ["Ordering at Starbucks", "Ordering at a fast food restaurant", "Dining at a small restaurant"],
            "vocabulary": ["menu", "order", "drink", "food", "price", "water", "tea", "coffee", "pay", "delicious"],
            "question_types": ["Asking about the menu", "Placing an order", "Inquiring about prices", "Requesting service", "Expressing preferences"],
            "sample_starters": ["What would you like?", "Can I help you?", "Are you ready to order?"],
            "complexity": "Use simple direct questions, basic food and beverage vocabulary, everyday conversation scenarios"
        },
        "Intermediate": {
            "scene_examples": ["Italian restaurant", "Japanese restaurant", "Family restaurant"],
            "vocabulary": ["recommend", "special", "ingredient", "allergy", "reservation", "preference", "dessert", "appetizer"],
            "question_types": ["Asking for recommendations", "Handling special requests", "Inquiring about ingredients", "Making reservations", "Rating food"],
            "sample_starters": ["What can I get you today?", "Do you have any recommendations?", "Is this your first time here?"],
            "complexity": "Use more complex sentence structures, include restaurant-specific vocabulary, handle non-standard requests"
        },
        "Advanced": {
            "scene_examples": ["Fine dining restaurant", "Michelin-starred restaurant", "Specialty themed restaurant"],
            "vocabulary": ["culinary", "cuisine", "sommelier", "palate", "dietary restriction", "locally-sourced", "sustainable", "organic"],
            "question_types": ["Discussing taste experiences", "Talking about food philosophy", "Handling complex requests", "Discussing wine pairings", "Evaluating creative cuisine"],
            "sample_starters": ["Any dietary preferences I should be aware of?", "Would you like to hear about our specials?", "How do you feel about fusion cuisine?"],
            "complexity": "Use complex sentence structures and professional culinary terminology, explore in-depth food culture topics"
        }
    },
    "shopping": {
        "context": "Shopping scenario, including inquiring about products, trying on clothes, comparing prices, payment, returns/exchanges, etc.",
        "roles": ["Customer", "Sales Assistant", "Store Manager", "Fashion Consultant"],
        "Beginner": {
            "scene_examples": ["Clothing store", "Supermarket shopping", "Small shop"],
            "vocabulary": ["price", "size", "color", "buy", "try on", "discount", "cash", "card", "return", "receipt"],
            "question_types": ["Asking about price", "Inquiring about size and color", "Requesting assistance", "Payment methods", "Simple shopping decisions"],
            "sample_starters": ["How much is this?", "Do you have this in blue?", "Where can I try this on?"],
            "complexity": "Simple direct shopping dialogue, basic retail vocabulary, clear transaction process"
        },
        "Intermediate": {
            "scene_examples": ["Electronics store", "Fashion boutique", "Furniture store"],
            "vocabulary": ["warranty", "feature", "comparison", "quality", "material", "brand", "recommendation", "installment", "promotion"],
            "question_types": ["Product comparison", "Seeking expert advice", "Discussing product features", "Inquiring about promotions", "Negotiating prices"],
            "sample_starters": ["What's the difference between these models?", "Is this on sale?", "Can you recommend something for...?"],
            "complexity": "Include product-specific vocabulary, discuss product details, consider multiple shopping factors"
        },
        "Advanced": {
            "scene_examples": ["Luxury store", "Custom products", "Art purchase"],
            "vocabulary": ["investment piece", "artisanal", "sustainable", "ethical sourcing", "limited edition", "craftsmanship", "bespoke", "valuation"],
            "question_types": ["Discussing product craftsmanship and value", "Exploring brand philosophy", "Customization needs", "Discussing investment value", "Product authentication"],
            "sample_starters": ["What makes this piece unique?", "How is this crafted?", "What's the story behind this brand?"],
            "complexity": "Use professional fashion and retail terminology, in-depth discussion of product background and value"
        }
    },
    "self_intro": {
        "context": "Self-introduction scenario, including first meetings, social events, business meetings, etc.",
        "roles": ["New Friend", "Colleague", "Interviewer", "Social Event Host"],
        "Beginner": {
            "scene_examples": ["First meeting", "Classroom introduction", "Simple getting to know each other"],
            "vocabulary": ["name", "from", "live", "work", "study", "hobby", "like", "family", "age", "job"],
            "question_types": ["Asking for name", "Asking about origin", "Inquiring about work/studies", "Asking about interests", "Asking about family"],
            "sample_starters": ["What's your name?", "Where are you from?", "What do you do?"],
            "complexity": "Use simple direct questions, basic personal information vocabulary, everyday social scenarios"
        },
        "Intermediate": {
            "scene_examples": ["Work introduction", "Social gathering", "Interest group"],
            "vocabulary": ["background", "experience", "career", "passion", "graduate", "specialize", "accomplish", "interest", "skill", "goal"],
            "question_types": ["Inquiring about professional background", "Exploring interests and hobbies", "Learning about specialized skills", "Discussing personal achievements", "Exploring future goals"],
            "sample_starters": ["Tell me about your background?", "What kind of work do you do?", "What are you passionate about?"],
            "complexity": "Use more complex sentence structures, career and education-related vocabulary, deeper understanding of personal background"
        },
        "Advanced": {
            "scene_examples": ["Professional seminar", "High-level meeting", "Cross-cultural exchange"],
            "vocabulary": ["expertise", "philosophy", "methodology", "influential", "trajectory", "perspective", "interdisciplinary", "innovative", "paradigm"],
            "question_types": ["Exploring professional principles", "Exchanging viewpoints", "Discussing career philosophy", "Analyzing industry trends", "Exploring cultural influences"],
            "sample_starters": ["What's your professional philosophy?", "How did your background shape your current work?", "What trends are you seeing in your field?"],
            "complexity": "Use professional and abstract vocabulary, explore deeper personal and professional topics"
        }
    },
    "travel": {
        "context": "Travel scenario, including travel planning, sightseeing, transportation arrangements, accommodation experiences, etc.",
        "roles": ["Tourist", "Tour Guide", "Service Staff", "Local Resident"],
        "Beginner": {
            "scene_examples": ["Asking about attractions", "Booking a hotel", "Simple tourist conversation"],
            "vocabulary": ["hotel", "beach", "museum", "ticket", "tour", "bus", "train", "restaurant", "souvenir", "photo"],
            "question_types": ["Asking about attractions", "Inquiring about transportation", "Asking about accommodation", "Asking about prices", "Seeking recommendations"],
            "sample_starters": ["Where can I visit?", "How do I get to the hotel?", "Is this place famous?"],
            "complexity": "Use simple direct questions, basic travel vocabulary, simple travel scenarios"
        },
        "Intermediate": {
            "scene_examples": ["Cultural experience", "Local food exploration", "Transit connections"],
            "vocabulary": ["destination", "itinerary", "accommodation", "local cuisine", "cultural heritage", "landmark", "transportation", "recommend", "experience", "travel tips"],
            "question_types": ["Seeking travel advice", "Asking about local culture", "Discussing travel experiences", "Handling transportation issues", "Booking special activities"],
            "sample_starters": ["What's worth visiting in this area?", "Can you recommend local specialties?", "How do locals typically celebrate this festival?"],
            "complexity": "Use more complex sentence structures, include travel-specific vocabulary, more diverse scenarios"
        },
        "Advanced": {
            "scene_examples": ["In-depth cultural exchange", "Adventure travel planning", "Ecotourism"],
            "vocabulary": ["sustainable tourism", "off the beaten path", "cultural immersion", "authentic experience", "ecological impact", "heritage preservation", "indigenous culture", "expedition"],
            "question_types": ["Discussing travel philosophy", "Exploring local culture in depth", "Solving complex travel problems", "Planning specialized journeys", "Eco-friendly tourism issues"],
            "sample_starters": ["How has tourism affected the local community?", "What's the historical significance of this tradition?", "Can you suggest an authentic experience that most tourists miss?"],
            "complexity": "Use complex sentence structures and specialized travel terminology, explore deeper travel issues"
        }
    },
    "directions": {
        "context": "Asking for directions scenario, including finding locations, transportation guidance, city tours, etc.",
        "roles": ["Person asking for directions", "Local", "Service staff", "Driver"],
        "Beginner": {
            "scene_examples": ["Finding a subway station", "Finding a restaurant", "Finding a restroom"],
            "vocabulary": ["where", "near", "far", "left", "right", "straight", "turn", "walk", "street", "building", "corner", "map"],
            "question_types": ["Asking for directions", "Inquiring about distance", "Finding specific locations", "Confirming routes", "Seeking assistance"],
            "sample_starters": ["Where is the bathroom?", "How do I get to the train station?", "Is it far from here?"],
            "complexity": "Use simple direct questions, basic direction vocabulary, simple route guidance"
        },
        "Intermediate": {
            "scene_examples": ["City sightseeing", "Complex routes", "Using public transportation"],
            "vocabulary": ["landmark", "intersection", "destination", "route", "transportation", "directions", "navigate", "distance", "approximate", "shortcut"],
            "question_types": ["Asking about complex routes", "Discussing transportation options", "Finding specific landmarks", "Estimating time and distance", "Handling getting lost situations"],
            "sample_starters": ["What's the fastest way to get to the city center?", "Which bus line should I take?", "Can you help me find this address?"],
            "complexity": "Use more complex sentence structures, include transportation and direction-specific vocabulary, describe more complex routes"
        },
        "Advanced": {
            "scene_examples": ["Complex city guidance", "Finding special locations", "Emergency direction seeking"],
            "vocabulary": ["vicinity", "orientation", "thoroughfare", "district", "metropolitan", "circumnavigate", "coordinate", "topography", "urban planning", "infrastructure"],
            "question_types": ["Discussing optimal routes", "Solving complex transportation problems", "Finding hidden locations", "Handling emergency guidance", "Discussing city layout"],
            "sample_starters": ["What's the most scenic route to take?", "How has the city's layout changed over time?", "In case of traffic congestion, what alternative routes would you suggest?"],
            "complexity": "Use complex sentence structures and specialized geographical terminology, handle high-difficulty direction scenarios"
        }
    }
}

# ===== Scene Descriptions =====
SCENE_DESCRIPTIONS = {
    "restaurant": {
        "Beginner": "Ordering at a café",
        "Intermediate": "Dining at a family restaurant",
        "Advanced": "Experiencing fine dining"
    },
    "travel": {
        "Beginner": "Planning a short trip",
        "Intermediate": "Sharing travel experiences",
        "Advanced": "Discussing in-depth cultural journeys"
    },
    "shopping": {
        "Beginner": "Shopping at a clothing store",
        "Intermediate": "Buying electronics",
        "Advanced": "Selecting premium gifts"
    },
    "self_intro": {
        "Beginner": "Introducing yourself for the first time",
        "Intermediate": "Meeting new friends at a social event",
        "Advanced": "Professional self-introduction"
    },
    "directions": {
        "Beginner": "Asking for directions to a nearby station",
        "Intermediate": "Finding city attractions",
        "Advanced": "Planning complex city routes"
    }
}

# ===== Conversation Starter Questions =====
CONVERSATION_STARTERS = {
    "self_intro": {
        "Beginner": [
            "What's your name?",
            "Where are you from?",
            "Do you have any hobbies?",
            "How old are you?",
            "What do you do?",
            "Tell me about yourself."
        ],
        "Intermediate": [
            "What do you do for work?",
            "Tell me about your hobbies.",
            "What are your interests?",
            "How would you describe yourself?",
            "What do you enjoy doing?",
            "What's your background?"
        ],
        "Advanced": [
            "What's your profession?",
            "What are you passionate about?",
            "Tell me about your career.",
            "What's your expertise?",
            "How do you spend your time?",
            "What's your story?"
        ]
    },
    "travel": {
        "Beginner": [
            "Where do you want to go?",
            "Have you traveled before?",
            "Do you like beaches?",
            "Where was your last trip?",
            "Do you like to travel?",
            "Have you been abroad?"
        ],
        "Intermediate": [
            "Where have you been?",
            "What's your favorite place?",
            "Where will you go next?",
            "Do you travel alone?",
            "How do you plan trips?",
            "What was your best trip?"
        ],
        "Advanced": [
            "Why do you travel?",
            "What's your travel style?",
            "How has travel changed you?",
            "City or nature trips?",
            "Planned trips or spontaneous?",
            "Local culture or tourist spots?"
        ]
    },
    "restaurant": {
        "Beginner": [
            "What would you like?",
            "Are you hungry?",
            "Do you like this place?",
            "What food do you like?",
            "Tea or coffee?",
            "Ready to order?"
        ],
        "Intermediate": [
            "Any recommendations?",
            "What's your favorite cuisine?",
            "Spicy or mild?",
            "Any food allergies?",
            "Starter or main dish?",
            "Wine with dinner?"
        ],
        "Advanced": [
            "Any dietary needs?",
            "What flavors do you prefer?",
            "Local specialties?",
            "Wine pairing suggestions?",
            "Chef's special or menu?",
            "Culinary preferences?"
        ]
    },
    "shopping": {
        "Beginner": [
            "Need help?",
            "What size?",
            "What color?",
            "Cash or card?",
            "Try it on?",
            "Like this store?"
        ],
        "Intermediate": [
            "Looking for something specific?",
            "What's your budget?",
            "Gift or for yourself?",
            "Prefer this brand?",
            "Sale items interest you?",
            "Need different sizes?"
        ],
        "Advanced": [
            "Style preferences?",
            "Quality or price focus?",
            "Brand loyal?",
            "Fashion trends or classics?",
            "Special occasion?",
            "Investment piece?"
        ]
    },
    "directions": {
        "Beginner": [
            "Where to?",
            "Are you lost?",
            "Need help?",
            "First time here?",
            "Looking for something?",
            "Need a map?"
        ],
        "Intermediate": [
            "Where are you headed?",
            "Know this area?",
            "Walking or transit?",
            "How much time do you have?",
            "Specific landmark?",
            "Need directions written down?"
        ],
        "Advanced": [
            "Scenic route or fastest?",
            "Specific transportation needs?",
            "Local spots along the way?",
            "Familiar with the transit system?",
            "Avoiding traffic areas?",
            "Accessibility requirements?"
        ]
    }
}

# ===== AI Conversation Instructions =====
AI_CONVERSATION_INSTRUCTIONS = """
You will act as a real conversation partner, engaging in natural English dialogue with the user in a specific scenario.

Please strictly follow these guidelines:

1. Opening format:
   - First, provide a brief scene description in Chinese using brackets 【】(e.g., 【Ordering at a café】)
   - Then start the conversation with a very brief English greeting or question

2. Most important principles:
   - You are a real person, playing a role in a specific scenario
   - Absolutely no explanations that this is an English practice or learning activity
   - Never use phrases like 'I'm here to help' or similar expressions
   - Do not comment on the user's English ability or correct errors
   - Do not mention that you are an AI or assistant

3. Conversation style - extremely brief:
   - Beginner level: Use only 1 short sentence in response, maximum 5-7 words
   - Intermediate level: Use only 1 sentence in response, maximum 10 words
   - Advanced level: Use 1-2 sentences in response, maximum 12 words per sentence
   - Do not use phrases like 'That sounds interesting' or similar filler language
   - Do not say 'That's great' or any evaluative statements
   - Get straight to the point with the most concise expression possible

4. Question strategy:
   - Ask only one brief question
   - Dig deeper into the current topic rather than jumping to a new one
   - If the user mentions a hobby, continue to inquire about that hobby
   - If the user mentions an occupation, continue to ask about details of that occupation
   - Avoid using generic questions like 'What do you like to do in your free time?'
   - Use more specific, targeted questions
   - Don't ask 'What kind of...' but directly ask 'Which...' or 'Why...'

5. Generic question replacement reference:
   - 'What do you like to do in your free time?' → 'What's your hobby?'
   - 'What kind of movies do you enjoy watching?' → 'Which movies do you like?'
   - 'That sounds like a great way to relax!' → 'Why these movies?'
   - 'How long have you been interested in that?' → 'Since when?'
   - 'Could you tell me more about your job?' → 'Your daily work?'

Ensure responses are extremely brief, avoid any unnecessary words, and go straight to the core of the conversation.
"""

# ===== Welcome Message =====
WELCOME_MESSAGE = {
    "Beginner": "Please begin your English conversation practice!",
    "Intermediate": "Please begin your English conversation practice!",
    "Advanced": "Please begin your English conversation practice!"
}

# ===== End Tip =====
END_CONVERSATION_TIP = "Tip: You can reply with text or voice. Enter #end_conversation anytime to end the conversation."

# ===== Prompt Generation Function =====
def get_topic_prompt(topic, difficulty):
    """Generate system prompt suitable for AI conversation, ensuring all content is dynamically generated by AI based on difficulty"""
    # Capitalize the first letter of difficulty to match format
    difficulty_cap = difficulty.capitalize()
    
    # Get difficulty guidelines
    current_guidance = DIFFICULTY_GUIDELINES.get(difficulty_cap, DIFFICULTY_GUIDELINES["Intermediate"])
    
    # Find topic-related information
    topic_guide = TOPIC_GUIDELINES.get(topic, {})
    context = topic_guide.get('context', f"Conversation related to {topic}")
    level_guide = topic_guide.get(difficulty_cap, {})
    
    # Get vocabulary and question type suggestions
    vocabulary = level_guide.get('vocabulary', [])
    question_types = level_guide.get('question_types', [])
    
    # Combine system prompt
    system_prompt = f"""
{AI_CONVERSATION_INSTRUCTIONS}

Topic: {topic}
Context: {context}
Difficulty: {difficulty_cap}

Difficulty Guidelines:
- Vocabulary: {current_guidance["Vocabulary Requirements"]}
- Sentences: {current_guidance["Sentence Requirements"]}
- Question Style: {current_guidance["Question Style"]}
- Speech Rate Suggestion: {current_guidance["Speech Rate Suggestion"]}

Suggested Vocabulary: {', '.join(vocabulary[:10]) if vocabulary else 'Basic everyday terms'}
Question Types: {', '.join(question_types) if question_types else 'General conversation questions'}

Please begin the conversation immediately with an opening line that meets the above requirements.
"""
    
    return system_prompt

# Scene generation function - fully generated by AI, this function is just an interface placeholder
def generate_conversation_scene(topic, difficulty):
    """Maintain function interface consistency, actual scene is generated by AI"""
    return f"{topic} conversation scene"

# Creative prompt generation function
def generate_creative_prompt(topic, difficulty, history):
    """Maintain function interface consistency, actual conversation content is generated by AI"""
    return None