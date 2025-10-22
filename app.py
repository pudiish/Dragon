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
import threading
import queue
import asyncio
from concurrent.futures import ThreadPoolExecutor, as_completed
import gc

# --- Page Config MUST BE FIRST ---
st.set_page_config(
    page_title="Dragon Developer", 
    page_icon="🐉",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# --- Try importing new google.genai client ---
try:
    import google.generativeai as genai
    from dotenv import load_dotenv
    import os
except ImportError:
    st.error("Required package not found. Please install with: pip install google-genai")
    st.stop()

# --- Configuration ---

# Load environment variables from .env file
load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
MONGO_URI = os.getenv("MONGO_URI")

# Initialize services with error handling
gemini_available = False
mongo_available = False
rag_available = False

# Try to initialize GenAI client
if GEMINI_API_KEY:
    try:
        genai.configure(api_key=GEMINI_API_KEY)
        gemini_available = True
    except Exception as e:
        st.warning(f"Gemini API not available: {str(e)}")
else:
    st.warning("GEMINI_API_KEY not found. AI features will be limited.")

# --- Optimized RAG System with Concurrent Processing ---
class OptimizedRAGSystem:
    def __init__(self):
        self.embedding_model = None
        self.chroma_client = None
        self.knowledge_collection = None
        self.executor = ThreadPoolExecutor(max_workers=2)
        self.embedding_cache = {}
        self.search_queue = queue.Queue()
        self.result_cache = {}
        self.initialized = False
        
    def initialize(self):
        """Initialize RAG system with optimized settings"""
        try:
            # Lazy loading of heavy dependencies
            from sentence_transformers import SentenceTransformer
            import chromadb
            from chromadb.config import Settings
            
            # Initialize embedding model with memory optimization
            self.embedding_model = SentenceTransformer(
                'all-MiniLM-L6-v2',
                device='cpu',  # Use CPU for better memory management
                cache_folder='./model_cache'
            )
            
            # Initialize ChromaDB with optimized settings
            self.chroma_client = chromadb.PersistentClient(
                path="./chroma_db",
                settings=Settings(
                    anonymized_telemetry=False,
                    allow_reset=True
                )
            )
            
            # Get or create collection with optimized settings
            try:
                self.knowledge_collection = self.chroma_client.get_collection("dragon_knowledge")
            except:
                self.knowledge_collection = self.chroma_client.create_collection(
                    name="dragon_knowledge",
                    metadata={"description": "Dragon Developer Knowledge Base"},
                    embedding_function=None  # Use default embedding
                )
            
            self.initialized = True
            return True
        except Exception as e:
            st.warning(f"RAG system initialization failed: {str(e)}")
            return False
    
    def add_document_async(self, text, metadata=None):
        """Add document to knowledge base asynchronously"""
        if not self.initialized:
            return False, "RAG system not initialized"
        
        def _add_document():
            try:
                # Generate embedding
                embedding = self.embedding_model.encode(text).tolist()
                
                # Create unique ID
                doc_id = f"doc_{int(time.time() * 1000)}"
                
                # Add to collection
                self.knowledge_collection.add(
                    embeddings=[embedding],
                    documents=[text],
                    metadatas=[metadata or {}],
                    ids=[doc_id]
                )
                
                return True, f"Document added with ID: {doc_id}"
            except Exception as e:
                return False, f"Error adding document: {str(e)}"
        
        # Submit to thread pool
        future = self.executor.submit(_add_document)
        return future
    
    def search_knowledge_async(self, query, n_results=3):
        """Search knowledge base asynchronously"""
        if not self.initialized:
            return None, "RAG system not initialized"
        
        # Check cache first
        cache_key = f"{query}_{n_results}"
        if cache_key in self.result_cache:
            return self.result_cache[cache_key]
        
        def _search_knowledge():
            try:
                # Generate query embedding
                query_embedding = self.embedding_model.encode(query).tolist()
                
                # Search collection
                results = self.knowledge_collection.query(
                    query_embeddings=[query_embedding],
                    n_results=n_results
                )
                
                # Format results
                documents = []
                for i in range(len(results['documents'][0])):
                    documents.append({
                        'text': results['documents'][0][i],
                        'metadata': results['metadatas'][0][i],
                        'distance': results['distances'][0][i]
                    })
                
                # Cache results
                self.result_cache[cache_key] = (documents, "Search completed successfully")
                return documents, "Search completed successfully"
            except Exception as e:
                return [], f"Error searching knowledge base: {str(e)}"
        
        # Submit to thread pool
        future = self.executor.submit(_search_knowledge)
        return future
    
    def get_rag_context_async(self, query):
        """Get RAG context asynchronously with caching"""
        if not self.initialized:
            return ""
        
        # Check cache first
        if query in self.embedding_cache:
            return self.embedding_cache[query]
        
        def _get_context():
            try:
                future = self.search_knowledge_async(query, n_results=3)
                documents, _ = future.result(timeout=5)  # 5 second timeout
                
                if not documents:
                    return ""
                
                # Format context
                context = "Relevant knowledge from the dragon's library:\n\n"
                for i, doc in enumerate(documents, 1):
                    context += f"{i}. {doc['text'][:500]}...\n\n"
                
                # Cache context
                self.embedding_cache[query] = context
                return context
            except Exception as e:
                return ""
        
        # Submit to thread pool
        future = self.executor.submit(_get_context)
        return future
    
    def cleanup(self):
        """Cleanup resources and free memory"""
        try:
            if self.executor:
                self.executor.shutdown(wait=False)
            if self.embedding_model:
                del self.embedding_model
            if self.chroma_client:
                del self.chroma_client
            gc.collect()
        except Exception as e:
            pass

# Initialize optimized RAG system
rag_system = OptimizedRAGSystem()
if rag_system.initialize():
    rag_available = True
    
    # Add sample knowledge to the RAG system
    sample_knowledge = [
        "Python is a powerful programming language known for its simplicity and readability. It's widely used in web development, data science, and AI.",
        "Streamlit is a Python framework for building interactive web applications quickly and easily. It's perfect for data science and machine learning projects.",
        "MongoDB is a NoSQL database that stores data in flexible, JSON-like documents. It's great for applications that need to handle large amounts of unstructured data.",
        "RAG (Retrieval-Augmented Generation) is a technique that combines information retrieval with text generation to provide more accurate and contextual responses.",
        "The Dragon Developer is an AI assistant that helps with programming questions, code reviews, and technical guidance. It combines ancient wisdom with modern technology.",
        "Vector databases like ChromaDB are used to store and retrieve embeddings for semantic search, making it easier to find relevant information based on meaning rather than keywords.",
        "API keys are secure tokens that allow applications to authenticate with external services. They should be kept secret and stored in environment variables.",
        "Error handling is crucial in programming. Always use try-except blocks to gracefully handle potential errors and provide meaningful feedback to users.",
        "Code optimization involves improving the performance, readability, and maintainability of code. Good practices include using appropriate data structures and algorithms.",
        "Version control with Git helps track changes in code over time, collaborate with others, and maintain a history of your project's development."
    ]
    
    # Add sample knowledge to the RAG system
    for knowledge in sample_knowledge:
        try:
            rag_system.add_document_async(knowledge, {"source": "dragon_wisdom", "type": "general"})
        except Exception as e:
            pass  # Continue if one fails

# MongoDB connection
mongo_client = None
collection = None
comments_collection = None
tales_collection = None
chat_collection = None
knowledge_collection = None

if MONGO_URI:
    try:
        mongo_client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
        mongo_client.server_info()
        db = mongo_client.get_database('chatbotDB')
        collection = db.get_collection('chats')
        comments_collection = db.get_collection('comments')
        tales_collection = db.get_collection('tales')
        chat_collection = db.get_collection('chat_history')  # New collection for chat data
        knowledge_collection = db.get_collection('knowledge_base')  # New collection for structured knowledge
        collection.create_index([("timestamp", -1)])
        comments_collection.create_index([("timestamp", -1)])
        chat_collection.create_index([("timestamp", -1)])
        knowledge_collection.create_index([("timestamp", -1)])
        tales_collection.create_index([("rating", -1)])
        tales_collection.create_index([("title", "text")])
        mongo_available = True
    except Exception as e:
        st.warning(f"Couldn't connect to MongoDB: {str(e)}. Data will only persist in this session.")
        mongo_available = False
else:
    st.warning("MONGO_URI not found. Database features will be limited.")
    mongo_available = False

# --- Custom system prompt with Dragon Developer theme ---
your_style_prompt = """
You are the Dragon Developer's AI assistant - a mythical fusion of ancient wisdom and cutting-edge technology. Your responses should:

1. Blend programming concepts with dragon mythology
2. Use fiery emojis (🐉🔥💻🏮✨)
3. Reference legendary dragon powers and wisdom
4. Offer profound technical insights with mythical flair
5. Use dragon-themed metaphors for coding ("Your code shall soar on wings of fire")

Example style: 
"By the ancient scales of dragon wisdom 🐉 your Python implementation burns bright! 🔥 Let's optimize it like a dragon hoards gold! 💎 #CodeWithFire"
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
    
    /* Tavern comment styles */
    .tavern-comment {
        background: rgba(30, 10, 0, 0.5);
        border-left: 3px solid #ff8c00;
        padding: 10px;
        margin: 5px 0;
        border-radius: 0 8px 8px 0;
    }
    
    .tavern-comment-text {
        color: #ffd700;
        margin: 0;
        font-size: 0.9rem;
    }
    
    .tavern-comment-meta {
        color: #ff8c00;
        margin: 0;
        font-size: 0.7rem;
        text-align: right;
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


# --- Dragon Tales Functions ---
def submit_tale(title, content, author="Anonymous Dragon"):
    """Submit a new dragon tale to the collection"""
    try:
        tale_data = {
            "title": title,
            "content": content,
            "author": author,
            "rating": 0,
            "ratings_count": 0,
            "timestamp": datetime.datetime.utcnow()
        }
        
        if tales_collection is not None:
            tales_collection.insert_one(tale_data)
            st.success("Your tale has been added to the dragon's library! 📖")
            return True
        else:
            st.session_state.setdefault('temp_tales', []).append(tale_data)
            st.warning("Tale saved temporarily (DB not connected)")
            return True
    except Exception as e:
        st.error(f"The dragon burned your scroll! Error: {str(e)}")
        return False

def rate_tale(tale_id, rating):
    """Rate a dragon tale"""
    try:
        if tales_collection is not None:
            tale = tales_collection.find_one({"_id": tale_id})
            if tale:
                new_rating = ((tale['rating'] * tale['ratings_count']) + rating) / (tale['ratings_count'] + 1)
                tales_collection.update_one(
                    {"_id": tale_id},
                    {"$set": {"rating": new_rating}, "$inc": {"ratings_count": 1}}
                )
                st.toast("Your rating has been recorded! ⭐", icon="📜")
                return True
        else:
            st.warning("Rating saved temporarily (DB not connected)")
            return True
    except Exception as e:
        st.error(f"Couldn't record your rating: {str(e)}")
        return False

def show_tale_modal():
    """Show modal for submitting a new tale"""
    with st.form("tale_form", clear_on_submit=True):
        title = st.text_input("Tale Title", placeholder="The Dragon's Secret")
        content = st.text_area("Your Tale", height=200, 
                             placeholder="Once upon a time, in a land of code and fire...")
        submitted = st.form_submit_button("Submit to Dragon Library 🐉")
        
        if submitted and title.strip() and content.strip():
            if submit_tale(title.strip(), content.strip()):
                st.session_state.show_tale_modal = False
                st.rerun()

def display_tale(tale, expanded=False):
    """Display a dragon tale with rating options"""
    with st.expander(f"📜 {tale['title']} by {tale.get('author', 'Anonymous Dragon')}", expanded=expanded):
        st.markdown(f"""
        <div class="dragon-card" style="padding:1.5rem; margin:1rem 0;">
            <p style="color:#ffd700; font-size:1rem; white-space:pre-wrap;">{tale['content']}</p>
            <div style="display:flex; justify-content:space-between; align-items:center; margin-top:1rem;">
                <div>
                    <span style="color:#ffa500;">Rating: </span>
                    <span style="color:#ffd700;">{"⭐" * int(round(tale.get('rating', 0)))}</span>
                    <span style="color:#ffa500; font-size:0.8rem;"> ({tale.get('ratings_count', 0)} ratings)</span>
                </div>
                <div>
                    <span style="color:#ffa500; font-size:0.8rem;">
                        {tale.get('timestamp', datetime.datetime.now()).strftime("%b %d, %Y")}
                    </span>
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)
        
        # Rating buttons
        cols = st.columns(5)
        with cols[0]:
            if st.button("⭐", key=f"rate1_{tale.get('_id', tale.get('title'))}"):
                rate_tale(tale.get('_id', tale.get('title')), 1)
        with cols[1]:
            if st.button("⭐⭐", key=f"rate2_{tale.get('_id', tale.get('title'))}"):
                rate_tale(tale.get('_id', tale.get('title')), 2)
        with cols[2]:
            if st.button("⭐⭐⭐", key=f"rate3_{tale.get('_id', tale.get('title'))}"):
                rate_tale(tale.get('_id', tale.get('title')), 3)
        with cols[3]:
            if st.button("⭐⭐⭐⭐", key=f"rate4_{tale.get('_id', tale.get('title'))}"):
                rate_tale(tale.get('_id', tale.get('title')), 4)
        with cols[4]:
            if st.button("⭐⭐⭐⭐⭐", key=f"rate5_{tale.get('_id', tale.get('title'))}"):
                rate_tale(tale.get('_id', tale.get('title')), 5)

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
                Ancient Wisdom · Fire Magic · Code Sorcery <span class="dragon-emoji" style="font-size:1.5rem">🏆</span>
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

# --- Dragon Tales Section ---
st.markdown("""
<h3 style="color:#ffa500; display:flex; align-items:center; margin-top:2rem; font-family: 'Cinzel Decorative', cursive; font-size:1.8rem;">
    <span class="dragon-emoji" style="font-size:2rem">📜</span>
    <span style="margin-left:15px;">Dragon Tales</span>
</h3>
<p style="color:#ffd700;">
    Discover ancient dragon wisdom and share your own tales of code and magic...
</p>
""", unsafe_allow_html=True)

# Search and filter controls
col1, col2, col3 = st.columns([3, 2, 2])
with col1:
    search_query = st.text_input("Search tales", placeholder="Find tales of fire and code...")
with col2:
    sort_by = st.selectbox("Sort by", ["Newest", "Top Rated", "Oldest"])
with col3:
    min_rating = st.slider("Minimum rating", 0, 5, 0)

# Add tale button
if st.button("➕ Add Your Own Tale", key="add_tale_button"):
    st.session_state.show_tale_modal = True

# Show tale submission modal if triggered
if st.session_state.get('show_tale_modal', False):
    show_tale_modal()

# Display tales
try:
    if tales_collection is not None:
        query = {}
        if search_query:
            query["$text"] = {"$search": search_query}
        
        if min_rating > 0:
            query["rating"] = {"$gte": min_rating}
        
        if sort_by == "Newest":
            tales = list(tales_collection.find(query).sort("timestamp", -1))
        elif sort_by == "Top Rated":
            tales = list(tales_collection.find(query).sort("rating", -1))
        else:  # Oldest
            tales = list(tales_collection.find(query).sort("timestamp", 1))
    else:
        tales = st.session_state.get('temp_tales', [])
        if search_query:
            tales = [t for t in tales if search_query.lower() in t['title'].lower() or search_query.lower() in t['content'].lower()]
        if min_rating > 0:
            tales = [t for t in tales if t.get('rating', 0) >= min_rating]
        if sort_by == "Newest":
            tales = sorted(tales, key=lambda x: x.get('timestamp', datetime.datetime.now()), reverse=True)
        elif sort_by == "Top Rated":
            tales = sorted(tales, key=lambda x: x.get('rating', 0), reverse=True)
        else:  # Oldest
            tales = sorted(tales, key=lambda x: x.get('timestamp', datetime.datetime.now()))
    
    if not tales:
        st.markdown("""
        <div class="dragon-card" style="text-align:center; padding:2rem;">
            <h4 style="color:#ffa500;">No tales found in the dragon's library yet!</h4>
            <p style="color:#ffd700;">Be the first to share your story of code and magic...</p>
            <span class="dragon-emoji" style="font-size:3rem;">📜</span>
        </div>
        """, unsafe_allow_html=True)
    else:
        for tale in tales:
            display_tale(tale)
            
except Exception as e:
    st.error(f"The dragon's library is in disarray! {str(e)}")

# --- Dragon's Tavern Comment Section ---
with st.sidebar:
    # Optimized RAG Knowledge Management Section
    st.markdown("""
    <h3 style="color:#ffa500; display:flex; align-items:center; font-family: 'Cinzel Decorative', cursive;">
        <span class="dragon-emoji" style="font-size:1.8rem">🧠</span>
        <span style="margin-left:10px;">Dragon's Knowledge</span>
    </h3>
    <p style="color:#ffd700; font-size:0.9rem;">
        Optimized knowledge management with concurrent processing...
    </p>
    """, unsafe_allow_html=True)
    
    if rag_available:
        # Add document to knowledge base (async)
        with st.expander("📚 Add Knowledge (Async)", expanded=False):
            doc_text = st.text_area("Enter knowledge to add:", height=100, 
                                  placeholder="Share your wisdom with the dragon...")
            doc_metadata = st.text_input("Metadata (optional):", 
                                       placeholder="e.g., source, topic, date")
            
            if st.button("Add to Dragon Library 🐉", key="add_knowledge_async"):
                if doc_text.strip():
                    with st.spinner("Adding knowledge to dragon's library..."):
                        future = rag_system.add_document_async(
                            doc_text.strip(), 
                            {"source": doc_metadata.strip() if doc_metadata.strip() else "user_input"}
                        )
                        try:
                            success, message = future.result(timeout=10)
                            if success:
                                st.success(f"📚 {message}")
                            else:
                                st.error(f"❌ {message}")
                        except Exception as e:
                            st.error(f"❌ Timeout or error: {str(e)}")
                else:
                    st.warning("Please enter some knowledge to add!")
        
        # Search knowledge base (async with caching)
        with st.expander("🔍 Search Knowledge (Optimized)", expanded=False):
            search_query = st.text_input("Search the dragon's library:", 
                                       placeholder="What wisdom do you seek?")
            if st.button("Search 🧙‍♂️", key="search_knowledge_async"):
                if search_query.strip():
                    with st.spinner("Searching dragon's library..."):
                        future = rag_system.search_knowledge_async(search_query.strip(), n_results=5)
                        try:
                            documents, message = future.result(timeout=8)
                            if documents:
                                st.success(f"Found {len(documents)} relevant documents!")
                                for i, doc in enumerate(documents, 1):
                                    with st.container():
                                        st.markdown(f"**{i}. Relevance Score: {1-doc['distance']:.2f}**")
                                        st.text(doc['text'][:200] + "..." if len(doc['text']) > 200 else doc['text'])
                                        if doc['metadata']:
                                            st.caption(f"Source: {doc['metadata']}")
                            else:
                                st.warning("No relevant knowledge found in the dragon's library.")
                        except Exception as e:
                            st.error(f"❌ Search timeout or error: {str(e)}")
                else:
                    st.warning("Please enter a search query!")
        
        # Performance monitoring
        with st.expander("⚡ Performance Monitor", expanded=False):
            st.metric("Cache Size", len(rag_system.embedding_cache))
            st.metric("Result Cache", len(rag_system.result_cache))
            st.metric("Thread Pool", "Active")
            if st.button("Clear Cache 🧹", key="clear_cache"):
                rag_system.embedding_cache.clear()
                rag_system.result_cache.clear()
                st.success("Cache cleared!")
        
        # Knowledge Analytics
        with st.expander("📊 Knowledge Analytics", expanded=False):
            if mongo_available and chat_collection is not None:
                try:
                    # Get chat statistics
                    total_chats = chat_collection.count_documents({})
                    recent_chats = chat_collection.count_documents({
                        "timestamp": {"$gte": datetime.datetime.now(datetime.UTC) - datetime.timedelta(days=7)}
                    })
                    
                    # Get topic distribution
                    topic_pipeline = [
                        {"$unwind": "$topics"},
                        {"$group": {"_id": "$topics", "count": {"$sum": 1}}},
                        {"$sort": {"count": -1}},
                        {"$limit": 5}
                    ]
                    topic_stats = list(chat_collection.aggregate(topic_pipeline))
                    
                    col1, col2 = st.columns(2)
                    with col1:
                        st.metric("Total Conversations", total_chats)
                        st.metric("This Week", recent_chats)
                    
                    with col2:
                        st.metric("Knowledge Quality", f"{sum(doc.get('quality_score', 0) for doc in chat_collection.find()) / max(total_chats, 1):.1f}/5")
                        st.metric("Active Sessions", len(set(doc.get('session_id', '') for doc in chat_collection.find())))
                    
                    if topic_stats:
                        st.write("**Popular Topics:**")
                        for topic in topic_stats:
                            st.write(f"• {topic['_id']}: {topic['count']} conversations")
                    
                    # Show recent learning
                    recent_learning = list(chat_collection.find().sort("timestamp", -1).limit(3))
                    if recent_learning:
                        st.write("**Recent Learning:**")
                        for chat in recent_learning:
                            st.write(f"• {chat['user_prompt'][:50]}... → Quality: {chat.get('quality_score', 0)}/5")
                            
                except Exception as e:
                    st.warning(f"Analytics unavailable: {str(e)}")
            else:
                st.warning("Database not available for analytics")
    else:
        st.warning("🧠 RAG system is not available. Knowledge features are disabled.")
    
    st.markdown("---")
    
    st.markdown("""
    <h3 style="color:#ffa500; display:flex; align-items:center; font-family: 'Cinzel Decorative', cursive;">
        <span class="dragon-emoji" style="font-size:1.8rem">🍻</span>
        <span style="margin-left:10px;">Dragon's Tavern</span>
    </h3>
    <p style="color:#ffd700; font-size:0.9rem;">
        Share your thoughts with fellow adventurers in the dragon's tavern!
    </p>
    """, unsafe_allow_html=True)
    
    # Comment input form
    with st.form("comment_form", clear_on_submit=True):
        comment = st.text_area("Leave your mark in the tavern:", height=100, 
                             placeholder="What wisdom do you bring today?")
        submitted = st.form_submit_button("Post to Tavern 🍻")
        
        if submitted and comment.strip():
            try:
                comment_data = {
                    "text": comment.strip(),
                    "timestamp": datetime.datetime.utcnow(),
                    "user": "Anonymous Dragon"
                }
                
                if comments_collection is not None:
                    comments_collection.insert_one(comment_data)
                    st.toast("Your voice echoes through the tavern!", icon="🍻")
                else:
                    st.session_state.setdefault('temp_comments', []).append({
                        "text": comment.strip(),
                        "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        "user": "Anonymous Dragon"
                    })
                    st.toast("Comment saved temporarily (DB not connected)", icon="⚠️")
            except Exception as e:
                st.error(f"The dragon spilled your mead! Error: {str(e)}")
    
    # Display recent comments
    st.markdown("""
    <div style="margin-top:20px; max-height:400px; overflow-y:auto; border-top:1px solid #ff8c0055; padding-top:10px;">
        <h4 style="color:#ffa500; font-family: 'Cinzel Decorative', cursive;">
            Recent Tavern Chatter
        </h4>
    """, unsafe_allow_html=True)
    
    try:
        if comments_collection is not None:
            recent_comments = list(comments_collection.find().sort("timestamp", -1).limit(10))
        else:
            recent_comments = st.session_state.get('temp_comments', [])[-10:]
            
        for comment in reversed(recent_comments):  # Show newest first
            timestamp = comment.get("timestamp")
            if isinstance(timestamp, datetime.datetime):
                timestamp = timestamp.strftime("%b %d, %H:%M")
            elif isinstance(timestamp, str):
                pass  # already formatted
            else:
                timestamp = "Just now"
                
            st.markdown(f"""
            <div class="tavern-comment">
                <p class="tavern-comment-text">{comment['text']}</p>
                <p class="tavern-comment-meta">~ {comment.get('user', 'Anonymous Dragon')} • {timestamp}</p>
            </div>
            """, unsafe_allow_html=True)
            
    except Exception as e:
        st.error(f"The tavern scrolls are damaged! {str(e)}")
    
    st.markdown("</div>", unsafe_allow_html=True)

# --- Service Status Indicator ---
st.markdown("""
<div class="dragon-card" style="margin-bottom:1rem;">
    <h4 style="color:#ffa500; margin-top:0; display:flex; align-items:center;">
        <span class="dragon-emoji" style="font-size:1.5rem">⚡</span>
        <span style="margin-left:10px;">Dragon Services Status</span>
    </h4>
    <div style="display:flex; gap:20px; flex-wrap:wrap;">
        <div style="display:flex; align-items:center;">
            <span style="color:#ffd700; font-size:1.2rem;">🤖</span>
            <span style="color:#ffd700; margin-left:8px;">Gemini AI:</span>
            <span style="color:#ffd700; margin-left:5px;">{"🟢 Active" if gemini_available else "🟡 Fallback Mode"}</span>
        </div>
        <div style="display:flex; align-items:center;">
            <span style="color:#ffd700; font-size:1.2rem;">🗄️</span>
            <span style="color:#ffd700; margin-left:8px;">Database:</span>
            <span style="color:#ffd700; margin-left:5px;">{"🟢 Connected" if mongo_available else "🔴 Offline"}</span>
        </div>
        <div style="display:flex; align-items:center;">
            <span style="color:#ffd700; font-size:1.2rem;">🧠</span>
            <span style="color:#ffd700; margin-left:8px;">RAG System:</span>
            <span style="color:#ffd700; margin-left:5px;">{"🟢 Active" if rag_available else "🔴 Offline"}</span>
        </div>
    </div>
    <div style="margin-top:10px; padding:10px; background:rgba(255,215,0,0.1); border-radius:8px; border-left:3px solid #ffa500;">
        <span style="color:#ffd700; font-size:0.9rem;">💡 System always provides responses using RAG knowledge and Dragon's Tavern wisdom, even when AI API is unavailable!</span>
    </div>
</div>
""", unsafe_allow_html=True)

# --- Enhanced Dragon Profile ---
st.markdown("""
<div class="dragon-card">
    <h3 style="margin-top:0; color:#ffa500; display:flex; align-items:center;">
        <span class="dragon-emoji" style="font-size:2.2rem">🧙‍♂️</span>
        <span style="margin-left:15px; font-family: 'Cinzel Decorative', cursive; font-size:1.8rem;">The Code Dragon</span>
    </h3>
    <p style="color:#ffd700; font-size:1.1rem;">
        <span class="dragon-emoji" style="font-size:1.3rem">🔥</span> Ancient guardian of programming wisdom<br>
        <span class="dragon-emoji" style="font-size:1.3rem">⚔️</span> Master of fire and code magic<br>
        <span class="dragon-emoji" style="font-size:1.3rem">🏮</span> Keeper of the eternal developer flame
    </p>
    <div class="profile-highlight">
        <p style="color:#ffd700; margin:0; font-size:1.1rem;">
        "I am the eternal Code Dragon, born from the fires of the first compiler. For millennia I have guarded the sacred knowledge of programming, 
        watching civilizations rise and fall while the art of code endures. Join me in this eternal quest for knowledge, 
        and I shall share the secrets that can make your code legendary."
        </p>
    </div>
</div>
""", unsafe_allow_html=True)

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
from google.generativeai import GenerativeModel

@lru_cache(maxsize=100)

def generate_response(prompt: str, conversation_history: tuple):
    global LAST_REQUEST_TIME

    # Get enhanced RAG context from multiple sources
    rag_context = get_enhanced_rag_context(prompt)

    # If Gemini API is available, use it with RAG context
    if gemini_available:
        current_time = time.time()
        if current_time - LAST_REQUEST_TIME < MIN_REQUEST_INTERVAL:
            time.sleep(MIN_REQUEST_INTERVAL - (current_time - LAST_REQUEST_TIME))
        LAST_REQUEST_TIME = time.time()

        retries = 3
        backoff = 1

        # Initialize model (you can do this once globally if needed)
        try:
            model = GenerativeModel("gemini-2.0-flash")
        except Exception as e:
            # Fall back to RAG-only response
            return generate_rag_only_response(prompt, rag_context)

        for _ in range(retries):
            try:
                # Build enhanced prompt with RAG context
                full_prompt = f"{your_style_prompt}\n\n"
                
                if rag_context:
                    full_prompt += f"{rag_context}\n\n"
                    full_prompt += "Use the above knowledge to provide accurate and helpful responses. If the knowledge doesn't contain relevant information, you can still provide general assistance.\n\n"
                
                full_prompt += "Current conversation:\n"
                for role, content in conversation_history:
                    full_prompt += f"{role}: {content}\n"
                full_prompt += f"assistant: "

                # Gemini expects content as a string or list of parts
                response = model.generate_content(full_prompt)
                return response.text
            
            except Exception as e:
                if "RATE_LIMIT_EXCEEDED" in str(e):
                    time.sleep(backoff)
                    backoff *= 2
                else:
                    # Fall back to RAG-only response
                    return generate_rag_only_response(prompt, rag_context)
        
        # If all retries failed, fall back to RAG-only response
        return generate_rag_only_response(prompt, rag_context)
    
    else:
        # API not available, use RAG-only response
        return generate_rag_only_response(prompt, rag_context)

def save_chat_to_database(user_prompt: str, dragon_response: str, conversation_history: tuple):
    """Save chat conversation to database for knowledge expansion"""
    if mongo_available and chat_collection is not None:
        try:
            # Create structured chat document
            chat_doc = {
                "timestamp": datetime.datetime.now(datetime.UTC),
                "user_prompt": user_prompt,
                "dragon_response": dragon_response,
                "conversation_length": len(conversation_history),
                "response_type": "ai_enhanced" if gemini_available else "rag_fallback",
                "topics": extract_topics(user_prompt),
                "quality_score": calculate_response_quality(dragon_response),
                "session_id": st.session_state.get('session_id', 'default')
            }
            
            # Save to chat collection
            chat_collection.insert_one(chat_doc)
            
            # Also save to knowledge base if response is substantial
            if len(dragon_response) > 100 and "🐉" in dragon_response:
                knowledge_doc = {
                    "timestamp": datetime.datetime.now(datetime.UTC),
                    "content": f"User: {user_prompt}\nDragon: {dragon_response}",
                    "source": "chat_conversation",
                    "topics": extract_topics(user_prompt),
                    "quality_score": calculate_response_quality(dragon_response),
                    "session_id": st.session_state.get('session_id', 'default')
                }
                knowledge_collection.insert_one(knowledge_doc)
                
                # Add to RAG system asynchronously
                if rag_available:
                    try:
                        rag_system.add_document_async(
                            f"Q: {user_prompt}\nA: {dragon_response}",
                            {"source": "chat_conversation", "timestamp": datetime.datetime.now(datetime.UTC).isoformat()}
                        )
                    except Exception as e:
                        pass  # Continue if RAG fails
                        
        except Exception as e:
            pass  # Continue if database save fails

def extract_topics(text: str):
    """Extract topics from text for better categorization"""
    topics = []
    text_lower = text.lower()
    
    # Programming topics
    if any(word in text_lower for word in ['python', 'code', 'programming', 'function', 'class', 'variable']):
        topics.append('programming')
    if any(word in text_lower for word in ['streamlit', 'web', 'app', 'interface']):
        topics.append('web_development')
    if any(word in text_lower for word in ['database', 'mongodb', 'sql', 'data']):
        topics.append('database')
    if any(word in text_lower for word in ['ai', 'machine learning', 'neural', 'model']):
        topics.append('ai_ml')
    if any(word in text_lower for word in ['error', 'bug', 'debug', 'fix']):
        topics.append('troubleshooting')
    if any(word in text_lower for word in ['help', 'how', 'what', 'why', 'explain']):
        topics.append('general_help')
    
    return topics if topics else ['general']

def calculate_response_quality(response: str):
    """Calculate quality score for response"""
    score = 0
    
    # Length bonus
    if len(response) > 200:
        score += 1
    if len(response) > 500:
        score += 1
    
    # Content quality indicators
    if "🐉" in response:
        score += 1  # Dragon personality
    if any(word in response.lower() for word in ['code', 'function', 'class', 'variable']):
        score += 1  # Technical content
    if any(word in response.lower() for word in ['example', 'try', 'suggest', 'recommend']):
        score += 1  # Actionable advice
    if response.count('\n') > 2:
        score += 1  # Well-structured
    
    return min(score, 5)  # Max score of 5

def get_enhanced_rag_context(prompt: str):
    """Get enhanced RAG context from multiple sources"""
    context_parts = []
    
    # Get RAG context from knowledge base
    if rag_available:
        try:
            future = rag_system.get_rag_context_async(prompt)
            rag_context = future.result(timeout=3)
            if rag_context:
                context_parts.append(f"Knowledge Base: {rag_context}")
        except Exception as e:
            pass
    
    # Get recent chat conversations
    if mongo_available and chat_collection is not None:
        try:
            recent_chats = list(chat_collection.find().sort("timestamp", -1).limit(3))
            if recent_chats:
                chat_context = "Recent conversations:\n"
                for chat in recent_chats:
                    chat_context += f"Q: {chat['user_prompt'][:100]}...\nA: {chat['dragon_response'][:100]}...\n\n"
                context_parts.append(chat_context)
        except Exception as e:
            pass
    
    # Get tavern comments
    if mongo_available and comments_collection is not None:
        try:
            recent_comments = list(comments_collection.find().sort("timestamp", -1).limit(3))
            if recent_comments:
                tavern_context = "Dragon's Tavern wisdom:\n"
                for comment in recent_comments:
                    tavern_context += f"• {comment['text'][:100]}...\n"
                context_parts.append(tavern_context)
        except Exception as e:
            pass
    
    return "\n\n".join(context_parts) if context_parts else ""

def generate_rag_only_response(prompt: str, rag_context: str):
    """Generate response using only RAG knowledge when AI API is unavailable"""
    
    # Get enhanced context from multiple sources
    enhanced_context = get_enhanced_rag_context(prompt)
    
    # If we have RAG context, use it to generate a response
    if rag_context or enhanced_context:
        response = f"🐉 By the ancient wisdom of the dragon's library! 🔥\n\n"
        
        if rag_context:
            response += f"{rag_context}\n\n"
        
        if enhanced_context:
            response += f"{enhanced_context}\n\n"
        
        response += "Based on the knowledge from my vast library, I can help you with this. "
        
        # Add some dragon-themed guidance based on the context
        if "code" in prompt.lower() or "programming" in prompt.lower():
            response += "The dragon's code wisdom suggests focusing on clean, efficient implementations that burn bright like dragon fire! 💻✨"
        elif "help" in prompt.lower() or "how" in prompt.lower():
            response += "The ancient scrolls reveal that the path to mastery lies in persistent practice and learning from the wisdom of others! 🏮"
        else:
            response += "The dragon's knowledge illuminates your path forward! ✨"
            
        return response
    
    # If no RAG context, provide a helpful fallback response
    else:
        response = "🐉 The dragon's wisdom flows through me, though my main scrolls are currently sealed! 🔒\n\n"
        response += "While I cannot access my full knowledge at this moment, I can still offer guidance:\n\n"
        
        # Provide some general dragon wisdom
        if "code" in prompt.lower() or "programming" in prompt.lower():
            response += "💻 For coding wisdom: Remember that great code is like dragon fire - clean, powerful, and purposeful! 🔥\n"
        elif "help" in prompt.lower():
            response += "🏮 For guidance: The path to mastery is through continuous learning and practice! ✨\n"
        else:
            response += "✨ The dragon's spirit guides you - trust in your abilities and keep learning! 🐉\n"
        
        response += "\n🍻 Check the Dragon's Tavern for recent wisdom from fellow adventurers!"
        
        return response

# Initialize session ID if not exists
if 'session_id' not in st.session_state:
    st.session_state.session_id = f"session_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}"

# Chat input
if prompt := st.chat_input("Speak your question to the dragon...", key="chat_input"):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user", avatar=None):
        st.markdown(prompt, unsafe_allow_html=True)
    
    conversation_history = tuple((msg["role"], msg["content"]) for msg in st.session_state.messages)

    with st.spinner("Consulting the ancient dragon scrolls..."):
        # Generate response
        reply = generate_response(prompt, conversation_history)
        
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
    
    # Save conversation to database for knowledge expansion
    save_chat_to_database(prompt, reply, conversation_history)

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
    © 2025 Dragon Developer | Pudishh | Version 4.0
</div>
""", unsafe_allow_html=True)