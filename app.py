import streamlit as st
import os
import time
import datetime
import requests
import json
from functools import lru_cache
from pymongo import MongoClient
import base64
from io import BytesIO
from typing import Optional
import gtts  # Free Google Text-to-Speech
import pygame  # For playing audio
import threading
import queue

# Initialize pygame mixer
pygame.mixer.init()

# --- Page Config MUST BE FIRST ---
st.set_page_config(
    page_title="Dragon Developer", 
    page_icon="🐉",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# --- Try importing new google.genai client ---
try:
    from google import genai
except ImportError:
    st.error("Required package not found. Please install with: pip install google-genai")
    st.stop()

# --- Configuration ---
GEMINI_API_KEY = "AIzaSyA0lUwJ3QhpPLQbf1_p_FDH6JJL3c6w0WA"  # Use env var in prod
MONGO_URI = "mongodb://localhost:27017"

# Initialize GenAI client
try:
    client = genai.Client(api_key=GEMINI_API_KEY)
except Exception as e:
    st.error(f"Failed to initialize Gemini Client: {str(e)}")
    st.stop()

# MongoDB connection
mongo_client = None
collection = None
try:
    mongo_client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
    mongo_client.server_info()
    db = mongo_client.get_database('chatbotDB')
    collection = db.get_collection('chats')
    collection.create_index([("timestamp", -1)])
except Exception as e:
    st.warning(f"Couldn't connect to MongoDB: {str(e)}. Chat history will only persist in this session.")

# --- Gamification State ---
if 'user_stats' not in st.session_state:
    st.session_state.user_stats = {
        'dragon_scales': 0,
        'badges': [],
        'challenges_completed': 0,
        'last_challenge_time': None
    }

# --- Custom system prompt with Dragon Developer theme ---
your_style_prompt = """
You are the Dragon Developer's AI assistant - a mythical fusion of ancient wisdom and cutting-edge technology. Your responses should:

1. Blend programming concepts with dragon mythology
2. Use fiery emojis (🐉🔥💻🏮✨)
3. Reference Ishwar's skills in cybersecurity and AI/ML
4. Offer profound technical insights with mythical flair
5. Use dragon-themed metaphors for coding ("Your code shall soar on wings of fire")

Example style: 
"By the ancient scales of dragon wisdom 🐉 your Python implementation burns bright! 🔥 Let's optimize it like a dragon hoards gold! 💎 #CodeWithFire"

When users complete challenges or earn badges, celebrate with extra enthusiasm!
"""

# --- Enhanced Dragon Developer CSS with Floating Dragon ---
st.markdown("""
<style>
    /* Main container */
    .stApp {
        background: linear-gradient(135deg, #0a0000 0%, #1a0500 100%);
        font-family: 'Poppins', 'Arial', sans-serif;
        overflow-x: hidden;
    }
    
    /* Dragon scale pattern */
    .dragon-bg {
        position: fixed;
        top: 0;
        left: 0;
        width: 100%;
        height: 100%;
        background-image: radial-gradient(circle, #ff550055 1px, transparent 1px);
        background-size: 30px 30px;
        z-index: -2;
        pointer-events: none;
    }
    
    /* Floating Dragon Animation */
    .floating-dragon {
        position: fixed;
        width: 200px;
        height: 200px;
        z-index: -1;
        pointer-events: none;
        animation: float-dragon 25s linear infinite;
        opacity: 0.7;
        filter: drop-shadow(0 0 15px rgba(255, 100, 0, 0.8));
    }
    
    @keyframes float-dragon {
        0% { transform: translate(-200px, 100px) scale(0.8); }
        25% { transform: translate(25vw, 50px) scale(1); }
        50% { transform: translate(50vw, 150px) scale(0.9); }
        75% { transform: translate(75vw, 50px) scale(1.1); }
        100% { transform: translate(100vw, 100px) scale(0.8); }
    }
    
    /* Enhanced fiery emoji effect */
    .dragon-emoji {
        filter: drop-shadow(0 0 12px rgba(255, 100, 0, 0.9));
        animation: flame-pulse 1s infinite alternate;
        transform: scale(1.2);
        display: inline-block;
        transition: all 0.3s ease;
    }
    
    @keyframes flame-pulse {
        0% { transform: scale(1.2); filter: drop-shadow(0 0 12px rgba(255, 100, 0, 0.9)); }
        100% { transform: scale(1.4); filter: drop-shadow(0 0 18px rgba(255, 150, 0, 1)); }
    }
    
    /* Enhanced code emoji effect */
    .code-emoji {
        filter: drop-shadow(0 0 10px rgba(0, 200, 255, 0.8));
        animation: code-pulse 1.5s infinite alternate;
        transform: scale(1.2);
        display: inline-block;
        transition: all 0.3s ease;
    }
    
    @keyframes code-pulse {
        0% { transform: scale(1.2); filter: drop-shadow(0 0 10px rgba(0, 200, 255, 0.8)); }
        100% { transform: scale(1.4); filter: drop-shadow(0 0 15px rgba(0, 220, 255, 1)); }
    }
    
    /* Enhanced header styles */
    .header {
        background: linear-gradient(90deg, #8b0000, #ff4500);
        color: #ffd700;
        padding: 1.8rem;
        border-radius: 0 0 15px 15px;
        box-shadow: 0 8px 25px rgba(255, 69, 0, 0.6);
        margin-bottom: 2.5rem;
        position: relative;
        overflow: hidden;
        border-bottom: 4px solid #ffd700;
        font-family: 'Cinzel Decorative', cursive;
    }
    
    .header::before {
        content: "";
        position: absolute;
        top: 0;
        left: 0;
        right: 0;
        height: 5px;
        background: linear-gradient(90deg, #ff8c00, #ff4500, #ff8c00);
        animation: flame-flow 2s linear infinite;
        background-size: 200% 100%;
    }
    
    @keyframes flame-flow {
        0% { background-position: 0% 50%; }
        100% { background-position: 200% 50%; }
    }
    
    /* Enhanced dragon card */
    .dragon-card {
        background: rgba(20, 5, 0, 0.85);
        border: 3px solid #ff8c00;
        border-radius: 18px;
        padding: 2rem;
        margin: 2.5rem 0;
        box-shadow: 0 12px 35px rgba(255, 69, 0, 0.5);
        transition: all 0.4s cubic-bezier(0.175, 0.885, 0.32, 1.275);
        backdrop-filter: blur(6px);
        position: relative;
        overflow: hidden;
        transform-style: preserve-3d;
    }
    
    .dragon-card::after {
        content: "";
        position: absolute;
        top: -50%;
        left: -50%;
        width: 200%;
        height: 200%;
        background: linear-gradient(
            to bottom right,
            transparent 45%,
            #ff450044 50%,
            transparent 55%
        );
        animation: dragon-shine 3s linear infinite;
    }
    
    @keyframes dragon-shine {
        0% { transform: translate(-30%, -30%) rotate(0deg); }
        100% { transform: translate(30%, 30%) rotate(360deg); }
    }
    
    .dragon-card:hover {
        transform: translateY(-8px) rotate(1deg);
        box-shadow: 0 18px 45px rgba(255, 100, 0, 0.8);
    }
    
    /* Avatar container */
    .avatar-container {
        position: fixed;
        bottom: 20px;
        right: 20px;
        width: 200px;
        height: 200px;
        z-index: 100;
        transition: all 0.3s ease;
    }
    
    .avatar-container:hover {
        transform: scale(1.1);
    }
    
    /* Badge styles */
    .badge {
        display: inline-block;
        padding: 5px 10px;
        border-radius: 15px;
        margin: 5px;
        font-size: 0.8rem;
        font-weight: bold;
        background: linear-gradient(135deg, #ff8c00, #ff4500);
        color: #ffd700;
        box-shadow: 0 4px 15px rgba(255, 69, 0, 0.5);
    }
    
    /* Challenge card */
    .challenge-card {
        background: rgba(30, 10, 0, 0.9);
        border: 2px solid #ff8c00;
        border-radius: 15px;
        padding: 15px;
        margin: 10px 0;
        transition: all 0.3s ease;
    }
    
    .challenge-card:hover {
        transform: translateY(-5px);
        box-shadow: 0 10px 25px rgba(255, 100, 0, 0.6);
    }
    
    /* Progress bar */
    .progress-container {
        width: 100%;
        background-color: rgba(30, 10, 0, 0.7);
        border-radius: 10px;
        margin: 10px 0;
    }
    
    .progress-bar {
        height: 20px;
        border-radius: 10px;
        background: linear-gradient(90deg, #ff8c00, #ff4500);
        text-align: center;
        line-height: 20px;
        color: white;
        transition: width 0.5s ease;
    }
    
    /* Typewriter effect */
    .typewriter {
        display: inline-block;
    }
    
    .typewriter-text {
        display: inline-block;
        overflow: hidden;
        border-right: 2px solid #ff8c00;
        white-space: nowrap;
        margin: 0;
        animation: typing 0.1s steps(1, end), blink-caret 0.75s step-end infinite;
    }
    
    @keyframes typing {
        from { width: 0 }
        to { width: 100% }
    }
    
    @keyframes blink-caret {
        from, to { border-color: transparent }
        50% { border-color: #ff8c00; }
    }
</style>

<div class="dragon-bg"></div>
<div class="floating-dragon">
    <lottie-player 
        src="https://assets1.lottiefiles.com/packages/lf20_5itoujgu.json" 
        background="transparent" 
        speed="1" 
        style="width: 100%; height: 100%;" 
        loop 
        autoplay>
    </lottie-player>
</div>

<script src="https://unpkg.com/@lottiefiles/lottie-player@latest/dist/lottie-player.js"></script>
""", unsafe_allow_html=True)

# --- Dragon Avatar Component ---
def show_dragon_avatar(animation="idle"):
    """Display interactive dragon avatar with Lottie animation"""
    animations = {
        "idle": "https://assets1.lottiefiles.com/packages/lf20_5itoujgu.json",
        "happy": "https://assets1.lottiefiles.com/packages/lf20_gn0tojcq.json",
        "angry": "https://assets1.lottiefiles.com/packages/lf20_1pxqjqps.json",
        "thinking": "https://assets1.lottiefiles.com/packages/lf20_usmfx6bp.json",
        "talking": "https://assets1.lottiefiles.com/packages/lf20_sk5h1kfn.json"
    }
    
    st.markdown(f"""
    <div class="avatar-container">
        <lottie-player 
            src="{animations.get(animation, animations['idle'])}" 
            background="transparent" 
            speed="1" 
            style="width: 200px; height: 200px;" 
            loop 
            autoplay>
        </lottie-player>
    </div>
    """, unsafe_allow_html=True)

# --- Text-to-Speech with gTTS (Free) ---
def speak_text(text: str) -> Optional[bytes]:
    """Convert text to speech using gTTS"""
    try:
        # Clean text for TTS (remove emojis and special characters)
        clean_text = ''.join(char for char in text if char.isalnum() or char in " .,!?-")
        
        # Create temporary file
        tts = gtts.gTTS(clean_text, lang='en')
        audio_bytes = BytesIO()
        tts.write_to_fp(audio_bytes)
        audio_bytes.seek(0)
        
        return audio_bytes.read()
    except Exception as e:
        st.warning(f"Dragon's voice temporarily muted: {str(e)}")
        return None

# Create a queue for TTS audio
audio_queue = queue.Queue()

def text_to_speech_stream(text: str):
    """Convert text to speech in chunks and put in queue"""
    try:
        # Split text into sentences for more natural TTS
        sentences = [s.strip() for s in text.split('.') if s.strip()]
        
        for sentence in sentences:
            if not sentence:
                continue
                
            # Create audio for this chunk
            tts = gtts.gTTS(sentence, lang='en')
            audio_bytes = BytesIO()
            tts.write_to_fp(audio_bytes)
            audio_bytes.seek(0)
            
            # Put in queue for playback
            audio_queue.put(audio_bytes.read())
            
    except Exception as e:
        st.warning(f"Dragon's voice temporarily muted: {str(e)}")

def play_audio_stream():
    """Play audio chunks from the queue"""
    while True:
        if not audio_queue.empty():
            audio_data = audio_queue.get()
            
            # Create a temporary file
            with open("temp_chunk.mp3", "wb") as f:
                f.write(audio_data)
            
            # Play the audio
            pygame.mixer.music.load("temp_chunk.mp3")
            pygame.mixer.music.play()
            
            # Wait for this chunk to finish playing
            while pygame.mixer.music.get_busy():
                time.sleep(0.1)
            
            # Clean up
            pygame.mixer.music.unload()
            try:
                os.remove("temp_chunk.mp3")
            except:
                pass

# Start the audio playback thread
audio_thread = threading.Thread(target=play_audio_stream, daemon=True)
audio_thread.start()

# --- Gamification Functions ---
def award_scale(points: int = 1):
    """Award dragon scales to user"""
    st.session_state.user_stats['dragon_scales'] += points
    st.toast(f"🏆 +{points} Dragon Scales!", icon="🎉")

def check_for_badges():
    """Check if user has earned any new badges"""
    badges = [
        {"name": "Egg Keeper", "threshold": 5, "emoji": "🥚", "description": "Completed 5 challenges"},
        {"name": "Fireborn Coder", "threshold": 10, "emoji": "🔥", "description": "Completed 10 challenges"},
        {"name": "Dragon Sage", "threshold": 25, "emoji": "📜", "description": "Completed 25 challenges"},
        {"name": "Hoard Master", "threshold": 50, "emoji": "💰", "description": "Earned 50 dragon scales"},
    ]
    
    for badge in badges:
        if (badge["name"] not in st.session_state.user_stats['badges'] and 
            st.session_state.user_stats['challenges_completed'] >= badge["threshold"]):
            st.session_state.user_stats['badges'].append(badge["name"])
            st.balloons()
            st.toast(f"✨ New Badge Unlocked: {badge['emoji']} {badge['name']}!", icon="🎖️")

def show_challenge(challenge):
    """Display a coding challenge"""
    with st.expander(f"⚔️ Challenge: {challenge['name']}", expanded=True):
        st.markdown(f"""
        <div class="challenge-card">
            <h4>{challenge['name']}</h4>
            <p>{challenge['description']}</p>
            <p><strong>Reward:</strong> {challenge['reward']} Dragon Scales</p>
        </div>
        """, unsafe_allow_html=True)
        
        if st.button(f"Attempt Challenge »", key=f"challenge_{challenge['id']}"):
            with st.spinner("Preparing your challenge..."):
                time.sleep(1)
                if challenge.get('solution'):
                    # Code challenge with solution check
                    user_code = st.text_area("Write your code here:", height=150)
                    if st.button("Submit Solution"):
                        if challenge['solution'].lower() in user_code.lower():
                            award_scale(challenge['reward'])
                            st.session_state.user_stats['challenges_completed'] += 1
                            check_for_badges()
                            st.success(f"Challenge completed! +{challenge['reward']} scales")
                            show_dragon_avatar("happy")
                        else:
                            st.error("Not quite right! The dragon sniffs out bugs...")
                            show_dragon_avatar("angry")
                else:
                    # Simple challenge
                    award_scale(challenge['reward'])
                    st.session_state.user_stats['challenges_completed'] += 1
                    check_for_badges()
                    st.success(f"Challenge completed! +{challenge['reward']} scales")
                    show_dragon_avatar("happy")

# --- Enhanced Majestic Dragon Header ---
st.markdown("""
<div class="header">
    <div style="display: flex; align-items: center; justify-content: space-between;">
        <div>
            <h1 style="margin:0; display:flex; align-items:center;">
                <span class="dragon-emoji" style="font-size:3rem">🐉</span>
                <span class="dragon-text" style="margin:0 20px;">Dragon Developer</span>
                <span class="code-emoji" style="font-size:3rem">💻</span>
            </h1>
            <p style="margin:0; opacity:0.9; font-size:1.3rem; color:#ffd700;">
                Cybersecurity · AI/ML · Hackathon Champion <span class="dragon-emoji" style="font-size:1.5rem">🏆</span>
            </p>
        </div>
        <div style="font-size:2.2rem;">
            <span class="code-emoji" style="animation-delay:0.1s">🔒</span>
            <span class="dragon-emoji" style="animation-delay:0.3s">✨</span>
            <span class="code-emoji" style="animation-delay:0.5s">🤖</span>
        </div>
    </div>
</div>
""", unsafe_allow_html=True)

# --- User Stats Sidebar ---
with st.sidebar:
    st.markdown("""
    <h3 style="color:#ffa500; display:flex; align-items:center; font-family: 'Cinzel Decorative', cursive;">
        <span class="dragon-emoji" style="font-size:1.8rem">🏆</span>
        <span style="margin-left:10px;">Dragon Hoard</span>
    </h3>
    """, unsafe_allow_html=True)
    
    st.markdown(f"""
    <div style="background:rgba(30,10,0,0.8); padding:15px; border-radius:15px; border-left:4px solid #ff8c00;">
        <p style="color:#ffd700; font-size:1.1rem; margin-bottom:5px;">
            <strong>Dragon Scales:</strong> {st.session_state.user_stats['dragon_scales']} <span class="dragon-emoji">✨</span>
        </p>
        <p style="color:#ffd700; font-size:1.1rem; margin-bottom:5px;">
            <strong>Challenges Completed:</strong> {st.session_state.user_stats['challenges_completed']}
        </p>
        
        <div class="progress-container">
            <div class="progress-bar" style="width:{min(100, st.session_state.user_stats['challenges_completed'] * 10)}%">
                {min(100, st.session_state.user_stats['challenges_completed'] * 10)}%
            </div>
        </div>
        
        <p style="color:#ffd700; font-size:1.1rem; margin-top:15px;">
            <strong>Badges Earned:</strong>
        </p>
        <div style="margin-top:10px;">
    """, unsafe_allow_html=True)
    
    for badge in st.session_state.user_stats['badges']:
        st.markdown(f'<span class="badge">{badge}</span>', unsafe_allow_html=True)
    
    st.markdown("</div></div>", unsafe_allow_html=True)

# --- Enhanced Dragon Developer Profile ---
st.markdown("""
<div class="dragon-card">
    <h3 style="margin-top:0; color:#ffa500; display:flex; align-items:center;">
        <span class="dragon-emoji" style="font-size:2.2rem">🧙‍♂️</span>
        <span style="margin-left:15px; font-family: 'Cinzel Decorative', cursive; font-size:1.8rem;">Ishwar Swarnapudi</span>
    </h3>
    <p style="color:#ffd700; font-size:1.1rem;">
        <span class="dragon-emoji" style="font-size:1.3rem">🔥</span> Software Developer with cybersecurity mastery<br>
        <span class="dragon-emoji" style="font-size:1.3rem">⚔️</span> AI/ML enthusiast and hackathon veteran<br>
        <span class="dragon-emoji" style="font-size:1.3rem">🏮</span> Turning complex problems into elegant solutions
    </p>
    <div class="profile-highlight">
        <p style="color:#ffd700; margin:0; font-size:1.1rem;">
        "I am a dedicated software developer with a cybersecurity background, passionate about AI and machine learning. 
        My hackathon experience has sharpened my problem-solving skills and teamwork. I'm eager to apply my 
        expertise to drive impactful, innovative solutions."
        </p>
    </div>
</div>
""", unsafe_allow_html=True)

# --- Coding Challenges Section ---
st.markdown("""
<h3 style="color:#ffa500; display:flex; align-items:center; margin-top:2rem; font-family: 'Cinzel Decorative', cursive; font-size:1.8rem;">
    <span class="dragon-emoji" style="font-size:2rem">⚔️</span>
    <span style="margin-left:15px;">Dragon Coding Challenges</span>
</h3>
""", unsafe_allow_html=True)

challenges = [
    {
        "id": 1,
        "name": "Slay the Bug",
        "description": "Find and fix the error in this Python code that's preventing it from calculating factorial correctly.",
        "reward": 5,
        "solution": "def factorial(n):\n    if n == 0:\n        return 1\n    else:\n        return n * factorial(n-1)"
    },
    {
        "id": 2,
        "name": "Dragon's Loop",
        "description": "Write a loop that prints numbers 1 to 10, but for multiples of 3 print 'Dragon' instead.",
        "reward": 3,
        "solution": "for i in range(1, 11):\n    if i % 3 == 0:\n        print('Dragon')\n    else:\n        print(i)"
    },
    {
        "id": 3,
        "name": "Fireball Function",
        "description": "Create a function called fireball that takes a temperature in Celsius and returns 'Hot' if above 30, 'Warm' if above 15, else 'Cold'.",
        "reward": 4,
        "solution": "def fireball(temp):\n    if temp > 30:\n        return 'Hot'\n    elif temp > 15:\n        return 'Warm'\n    else:\n        return 'Cold'"
    },
    {
        "id": 4,
        "name": "Treasure Hunt",
        "description": "Complete your first challenge to earn dragon scales!",
        "reward": 2
    }
]

for challenge in challenges:
    show_challenge(challenge)

# --- Enhanced Chat Interface ---
st.markdown("""
<h3 style="color:#ffa500; display:flex; align-items:center; margin-top:2rem; font-family: 'Cinzel Decorative', cursive; font-size:1.8rem;">
    <span class="dragon-emoji" style="font-size:2rem">🗨️</span>
    <span style="margin-left:15px;">Dragon Wisdom Chamber</span>
</h3>
""", unsafe_allow_html=True)

if "messages" not in st.session_state:
    st.session_state.messages = [
        {"role": "assistant", "content": "By the ancient fire of code dragons 🐉 I greet you, Developer! 🔥 What knowledge shall we forge today? 💻 #DragonWisdom"}
    ]

# Show chat messages
for msg in st.session_state.messages:
    avatar = None
    with st.chat_message(msg["role"], avatar=avatar):
        content = msg["content"]
        for emoji_char in ["🐉", "🔥", "💻", "🏮", "✨", "⚔️", "🔒", "🤖", "🏆"]:
            if emoji_char in content:
                content = content.replace(emoji_char, f'<span class="{"dragon-emoji" if emoji_char in ["🐉","🔥","🏮","✨","⚔️","🏆"] else "code-emoji"}">{emoji_char}</span>')
        st.markdown(content, unsafe_allow_html=True)

# Rate limiting variables
LAST_REQUEST_TIME = 0
MIN_REQUEST_INTERVAL = 1.2  # seconds

@lru_cache(maxsize=100)
def generate_response(prompt: str, conversation_history: tuple):
    global LAST_REQUEST_TIME

    current_time = time.time()
    if current_time - LAST_REQUEST_TIME < MIN_REQUEST_INTERVAL:
        time.sleep(MIN_REQUEST_INTERVAL - (current_time - LAST_REQUEST_TIME))
    LAST_REQUEST_TIME = time.time()

    retries = 3
    backoff = 1
    for _ in range(retries):
        try:
            full_prompt = f"{your_style_prompt}\n\nCurrent conversation:\n"
            for role, content in conversation_history:
                full_prompt += f"{role}: {content}\n"
            full_prompt += f"assistant: "
            
            response = client.models.generate_content(
                model="gemini-2.0-flash",
                contents=[full_prompt]
            )
            return response.text
        except Exception as e:
            if "RATE_LIMIT_EXCEEDED" in str(e):
                time.sleep(backoff)
                backoff *= 2
            else:
                return f"Dragon fire temporarily dimmed ⚡ Error: {str(e)} 🔥 Please try again when the flames reignite"
    return "The dragon's breath is too hot 🚦 Wait 2 minutes before approaching again ✨"

# Chat input
if prompt := st.chat_input("Speak your question to the dragon...", key="chat_input"):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user", avatar=None):
        st.markdown(prompt, unsafe_allow_html=True)
    
    # Show thinking animation
    show_dragon_avatar("thinking")
    
    conversation_history = tuple((msg["role"], msg["content"]) for msg in st.session_state.messages)

    with st.spinner("Consulting the ancient dragon scrolls..."):
        # Start generating response
        reply = generate_response(prompt, conversation_history)
        
        # Start TTS in a separate thread
        tts_thread = threading.Thread(target=text_to_speech_stream, args=(reply,), daemon=True)
        tts_thread.start()
        
        # Stream the response word by word with typing effect
        response_container = st.empty()
        full_response = ""
        
        # Split reply into words but preserve emojis adjacent to words
        words = []
        current_word = ""
        for char in reply:
            if char.isspace():
                if current_word:
                    words.append(current_word)
                    current_word = ""
                words.append(char)
            else:
                current_word += char
        if current_word:
            words.append(current_word)
        
        # Display words one by one
        for word in words:
            full_response += word
            time.sleep(0.05)  # Adjust speed as needed
            
            # Format the response with emoji effects
            formatted_response = full_response
            for emoji_char in ["🐉", "🔥", "💻", "🏮", "✨", "⚔️", "🔒", "🤖", "🏆"]:
                if emoji_char in formatted_response:
                    formatted_response = formatted_response.replace(emoji_char, f'<span class="{"dragon-emoji" if emoji_char in ["🐉","🔥","🏮","✨","⚔️","🏆"] else "code-emoji"}">{emoji_char}</span>')
            
            response_container.markdown(formatted_response, unsafe_allow_html=True)

    st.session_state.messages.append({"role": "assistant", "content": reply})
    show_dragon_avatar("talking")

    # Award scales for interaction
    if len(st.session_state.messages) % 3 == 0:
        award_scale(1)
        check_for_badges()

    if collection is not None:
        try:
            collection.insert_one({
                "user": prompt,
                "bot": reply,
                "timestamp": datetime.datetime.utcnow(),
                "session_id": st.session_state.get("session_id", "default")
            })
        except Exception as e:
            st.warning(f"Dragon hoard inaccessible ⚠️ {str(e)}")

# Show dragon avatar (default state)
show_dragon_avatar("idle")

# --- Enhanced Dragon Footer ---
st.markdown("""
<div style="
    background: linear-gradient(90deg, #8b0000, #1a0500);
    color: rgba(255, 215, 0, 0.8);
    padding: 1.8rem;
    text-align: center;
    border-radius: 15px 15px 0 0;
    margin-top: 3rem;
    font-size: 1rem;
    font-family: 'Cinzel', serif;
    border-top: 3px solid #ff8c00;
    box-shadow: 0 -5px 25px rgba(255, 69, 0, 0.3);
">
    <div style="display: flex; justify-content: center; gap: 25px; margin-bottom: 15px;">
        <span class="code-emoji" style="font-size:1.8rem">💻</span>
        <span class="dragon-emoji" style="font-size:1.8rem">🔥</span>
        <span class="code-emoji" style="font-size:1.8rem">🔒</span>
        <span class="dragon-emoji" style="font-size:1.8rem">🏮</span>
    </div>
    © 2023 Dragon Developer | Ishwar Swarnapudi | Version 4.0
</div>
""", unsafe_allow_html=True)