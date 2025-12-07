# gemini_chat.py
import json
import os
import google.generativeai as genai
from config_gemini import GEMINI_API_KEY, SYSTEM_PROMPT

# Configure Gemini
genai.configure(api_key=GEMINI_API_KEY)


# 1. HISTORY MANAGEMENT

HISTORY_FILE = "gemini_history.json"

def load_history():
    """Load previous chat history from disk."""
    if not os.path.exists(HISTORY_FILE):
        return []

    try:
        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return []


def save_history(history):
    """Save updated chat history to disk."""
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(history, f, indent=4)


# 2. LIBRARY → TEXT SUMMARY (for prompt)

def build_library_text(library):
    """Convert library dict (from cache) into readable text for Gemini."""
    if not library:
        return "No games found."

    lines = []
    lines.append(f"Total games: {len(library)}\n")

    for appid, g in library.items():
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


# 3. AI CHAT (with persistent memory)

def ai_chat(user_message, library_data):
    """Chat with Gemini with persistent history."""
    history = load_history()

    library_text = build_library_text(library_data)

    model = genai.GenerativeModel("gemini-2.5-flash")
    chat = model.start_chat(history=history)

    # Construct AI input
    full_prompt = (
        SYSTEM_PROMPT
        + "\n\nHere is the user's Steam game library:\n"
        + library_text
        + "\n\nUser message: "
        + user_message
    )

    response = chat.send_message(full_prompt)
    reply_text = response.text

    # Update & save new history
    history.append({"role": "user", "parts": [{"text": user_message}]})
    history.append({"role": "model", "parts": [{"text": reply_text}]})
    save_history(history)

    return reply_text


# 4. AI-ENHANCED LIBRARY SUMMARY (smart summary)
def enhanced_summary(library_data):
    """Ask Gemini to provide an intelligent summary of the user's library."""
    library_text = build_library_text(library_data)

    prompt = f"""
You are an expert game analyst.

Given this Steam library:

{library_text}

Please generate a **smart summary** describing:
- The user's top genres and playstyle
- Typical difficulty level of the games they enjoy
- Whether they prefer solo, multiplayer, or co-op
- What type of gamer they appear to be
- Any patterns you notice in game selection

Write it in **friendly and concise** paragraphs.
"""

    model = genai.GenerativeModel("gemini-2.5-flash")
    response = model.generate_content(prompt)

    return response.text


# 5. AI FULL GAME REPORT (one-shot analysis)
def ai_chat(user_message, library_data):
    """Chat with Gemini with persistent history. """
    history = load_history()

    library_text = build_library_text(library_data)

    model = genai.GenerativeModel("gemini-2.5-flash")
    chat = model.start_chat(history=history)

    full_prompt = f"""
{SYSTEM_PROMPT}

Here is the user's Steam game library:
{library_text}

IMPORTANT INSTRUCTIONS:
- You may recommend games that are ALREADY in the user's library above.
- You may ALSO recommend great Steam games that are NOT in the user's library yet.
- When you recommend a game that is NOT in the library list above, add the text
  "(not in your library yet)" after its name so the user knows it's new.
- Focus on 3–6 strong suggestions and explain briefly why each one fits.

User message: {user_message}
"""

    response = chat.send_message(full_prompt)
    reply_text = response.text

    history.append({"role": "user", "parts": [{"text": user_message}]})
    history.append({"role": "model", "parts": [{"text": reply_text}]})
    save_history(history)

    return reply_text



# 6. CLI TEST ENTRY

if __name__ == "__main__":
    print("Simple AI test. Type something (or 'exit' to quit).")
    dummy_library = {}

    while True:
        msg = input("> ")
        if msg.lower() in ("exit", "quit"):
            break
        reply = ai_chat(msg, dummy_library)
        print(reply)
