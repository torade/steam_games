"""
gemini_ai.py

This module provides 3 new AI features for Steam Library Assistant:
1. AI One-Shot Report (generate_ai_report)
2. Persistent AI Chat Memory (ai_chat)
3. AI Smart Summary (enhanced_summary)

How to use each function is written in comments below.
"""

import json
import os
import google.generativeai as genai
from config_gemini import GEMINI_API_KEY, SYSTEM_PROMPT

# Configure Gemini
genai.configure(api_key=GEMINI_API_KEY)

# File used for storing chat history
HISTORY_FILE = "gemini_history.json"


# ============================================
# Helper: Convert library dict into readable text
# ============================================
def build_library_text(library_data):
    """Convert game_cache.json data into readable text for the AI."""
    if not library_data:
        return "No games found."

    lines = [f"Total games: {len(library_data)}\n"]

    for appid, g in library_data.items():
        name = g.get("name", "Unknown")
        genres = ", ".join(x.get("description", "") for x in g.get("genres", []))
        categories = ", ".join(x.get("description", "") for x in g.get("categories", []))

        lines.append(f"- {name}")
        if genres:
            lines.append(f"  Genres: {genres}")
        if categories:
            lines.append(f"  Categories: {categories}")
        lines.append("")
    return "\n".join(lines)


# ============================================
# 1) Persistent Chat Memory
# ============================================
def load_history():
    """Load previous AI chat from disk. Returns [] if none exists."""
    if not os.path.exists(HISTORY_FILE):
        return []
    try:
        return json.load(open(HISTORY_FILE, "r", encoding="utf-8"))
    except:
        return []


def save_history(history):
    """Save updated chat history to disk."""
    json.dump(history, open(HISTORY_FILE, "w", encoding="utf-8"), indent=4)


def ai_chat(user_message, library_data):
    """
    Chat with Gemini using persistent conversation memory.

    Usage Example:
    >>> from gemini_ai import ai_chat
    >>> text = ai_chat("Recommend a cozy game.", library)
    >>> print(text)
    """
    history = load_history()
    library_text = build_library_text(library_data)

    model = genai.GenerativeModel("gemini-2.5-flash")
    chat = model.start_chat(history=history)

    full_prompt = (
        SYSTEM_PROMPT +
        "\n\nHere is the user's Steam library:\n" +
        library_text +
        "\n\nUser: " + user_message
    )

    response = chat.send_message(full_prompt)
    reply = response.text

    # Update history
    history.append({"role": "user", "parts": [{"text": user_message}]})
    history.append({"role": "model", "parts": [{"text": reply}]})
    save_history(history)

    return reply


# ============================================
# 2) AI Smart Summary of Steam Library
# ============================================
def enhanced_summary(library_data):
    """
    Generate a natural-language summary of the user's playstyle.

    Usage Example:
    >>> text = enhanced_summary(library)
    >>> print(text)
    """
    library_text = build_library_text(library_data)

    prompt = f"""
You are an expert Steam game analyst.

Given this Steam library:

{library_text}

Write a short smart summary describing:
- The user's top genres and playstyle
- Their typical pacing & difficulty preference
- Solo vs multiplayer tendency
- Any patterns in their collection

Write in friendly, human-like paragraphs.
"""

    model = genai.GenerativeModel("gemini-2.5-flash")
    response = model.generate_content(prompt)
    return response.text


# ============================================
# 3) AI One-Shot Full Game Report
# ============================================
def generate_ai_report(library_data):
    """
    Generate a full AI analysis report of the user's entire Steam library.

    Usage Example:
    >>> report = generate_ai_report(library)
    >>> print(report)
    """
    library_text = build_library_text(library_data)

    prompt = f"""
You are an AI Steam library analyst.
Create a detailed **Steam Library Report** including:

1. Overview of the user's game collection
2. Playstyle analysis
3. Personalized recommendations (from their own library)
4. Hidden gem suggestions
5. Tonight's recommended game

Here is the library data:

{library_text}
"""

    model = genai.GenerativeModel("gemini-2.5-flash")
    response = model.generate_content(prompt)
    return response.text


# Standalone test mode
if __name__ == "__main__":
    try:
        library = json.load(open("game_cache.json", "r", encoding="utf-8"))
    except:
        print("No game_cache.json found. Run main.py first.")
        exit()

    print("\n=== AI Full Report ===\n")
    print(generate_ai_report(library))
