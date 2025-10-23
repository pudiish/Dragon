"""Context utilities for the Dragon app.

This module centralizes prompt composition, RAG context collection and the
RAG-only fallback response generation. It is intentionally dependency-light
and takes the stateful objects (rag_system, db collections) as parameters so
it can be imported without causing heavy imports at UI startup.
"""
from typing import Optional
import datetime
import time

# --- Dragon style system prompt ---
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


def get_enhanced_rag_context(
    prompt: str,
    enable_rag: bool,
    rag_system=None,
    rag_available: bool = False,
    mongo_available: bool = False,
    chat_collection=None,
    comments_collection=None,
    timeout: float = 3.0,
) -> str:
    """Collect contextual RAG and small-scope DB signals.

    Parameters are passed in so the caller (app.py) can keep ownership of
    heavy objects and the UI can control whether RAG is used.
    """
    if not enable_rag:
        return ""

    context_parts = []

    # Knowledge base via rag_system
    if rag_available and rag_system is not None:
        try:
            future = rag_system.get_rag_context_async(prompt)
            rag_context = future.result(timeout=timeout)
            if rag_context:
                context_parts.append(f"Knowledge Base: {rag_context}")
        except Exception:
            pass

    # Recent chat conversations (DB)
    if mongo_available and chat_collection is not None:
        try:
            recent_chats = list(chat_collection.find().sort("timestamp", -1).limit(3))
            if recent_chats:
                chat_context = "Recent conversations:\n"
                for chat in recent_chats:
                    chat_context += f"Q: {chat.get('user_prompt','')[:100]}...\nA: {chat.get('dragon_response','')[:100]}...\n\n"
                context_parts.append(chat_context)
        except Exception:
            pass

    # Tavern comments
    if mongo_available and comments_collection is not None:
        try:
            recent_comments = list(comments_collection.find().sort("timestamp", -1).limit(3))
            if recent_comments:
                tavern_context = "Dragon's Tavern wisdom:\n"
                for comment in recent_comments:
                    tavern_context += f"• {comment.get('text','')[:100]}...\n"
                context_parts.append(tavern_context)
        except Exception:
            pass

    return "\n\n".join(context_parts) if context_parts else ""


def build_full_prompt(
    prompt: str,
    conversation_history: tuple,
    enable_rag: bool,
    rag_system=None,
    rag_available: bool = False,
    mongo_available: bool = False,
    chat_collection=None,
    comments_collection=None,
    timeout: float = 3.0,
) -> str:
    """Compose the full system+context+conversation prompt.

    This mirrors the previous in-app composition but is centralized here so
    formatting and behavior are consistent.
    """
    rag_context = get_enhanced_rag_context(
        prompt,
        enable_rag,
        rag_system=rag_system,
        rag_available=rag_available,
        mongo_available=mongo_available,
        chat_collection=chat_collection,
        comments_collection=comments_collection,
        timeout=timeout,
    )

    full_prompt = f"{your_style_prompt}\n\n"
    if rag_context:
        full_prompt += f"{rag_context}\n\n"
        full_prompt += (
            "Use the above knowledge to provide accurate and helpful responses. "
            "If the knowledge doesn't contain relevant information, you can still provide general assistance.\n\n"
        )

    full_prompt += "Current conversation:\n"
    for role, content in conversation_history:
        full_prompt += f"{role}: {content}\n"
    full_prompt += "assistant: "
    return full_prompt


def generate_rag_only_response(
    prompt: str,
    rag_context: str,
    enable_rag: bool,
    rag_system=None,
    rag_available: bool = False,
    mongo_available: bool = False,
    chat_collection=None,
    comments_collection=None,
):
    """Fallback text when no LLM backend is available; uses RAG context if present."""
    enhanced_context = ""
    try:
        enhanced_context = get_enhanced_rag_context(
            prompt,
            enable_rag,
            rag_system=rag_system,
            rag_available=rag_available,
            mongo_available=mongo_available,
            chat_collection=chat_collection,
            comments_collection=comments_collection,
        )
    except Exception:
        enhanced_context = ""

    if rag_context or enhanced_context:
        response = f"🐉 By the ancient wisdom of the dragon's library! 🔥\n\n"
        if rag_context:
            response += f"{rag_context}\n\n"
        if enhanced_context:
            response += f"{enhanced_context}\n\n"
        response += "Based on the knowledge from my vast library, I can help you with this. "
        if "code" in prompt.lower() or "programming" in prompt.lower():
            response += (
                "The dragon's code wisdom suggests focusing on clean, efficient implementations that burn bright like dragon fire! 💻✨"
            )
        elif "help" in prompt.lower() or "how" in prompt.lower():
            response += "The ancient scrolls reveal that the path to mastery lies in persistent practice and learning from the wisdom of others! 🏮"
        else:
            response += "The dragon's knowledge illuminates your path forward! ✨"
        return response

    # No RAG context available
    response = (
        "🐉 The dragon's wisdom flows through me, though my main scrolls are currently sealed! 🔒\n\n"
        "While I cannot access my full knowledge at this moment, I can still offer guidance:\n\n"
    )
    if "code" in prompt.lower() or "programming" in prompt.lower():
        response += (
            "💻 For coding wisdom: Remember that great code is like dragon fire - clean, powerful, and purposeful! 🔥\n"
        )
    elif "help" in prompt.lower():
        response += "🏮 For guidance: The path to mastery is through continuous learning and practice! ✨\n"
    else:
        response += "✨ The dragon's spirit guides you - trust in your abilities and keep learning! 🐉\n"
    response += "\n🍻 Check the Dragon's Tavern for recent wisdom from fellow adventurers!"
    return response
