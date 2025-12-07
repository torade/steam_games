import logging
from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, ContextTypes, filters
import requests
import json

# PUT YOUR API KEY HERE
API_KEY = "AIzaSyABiUW95vjRbw2VdHuLQoFQKACw8unicgE"  # ← Get from: https://aistudio.google.com/app/apikey
TOKEN = "8019426767:AAH-sRlPbtgI20VgVkqnXjRrdWZPvbnVSHY" # PUT YOUR TELEGRAM BOT TOKEN HERE

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)

# Note: This global history will be shared across all users.
# For a multi-user bot, you should store history per user/chat.
conversation_history = []

def chat_with_memory(user_message, personality="You are a helpful study assistant."):
    """
    Enhanced chat that remembers the entire conversation
    """
    # Add user message to history in the correct format
    conversation_history.append({
        "role": "user",
        "parts": [{"text": user_message}]
    })

    url = (
        "https://generativelanguage.googleapis.com/v1beta/models/"
        f"gemini-2.5-flash:generateContent?key={API_KEY}"
    )
    headers = {"Content-Type": "application/json"}

    # The 'contents' field should contain the whole conversation history
    data = {
        "system_instruction": {
            "parts": [{"text": personality}]
        },
        "contents": conversation_history
    }

    response = requests.post(url, headers=headers, json=data)

    # Check HTTP status
    if response.status_code != 200:
        print("HTTP error:", response.status_code, response.text)
        return f"Error: HTTP {response.status_code}"

    result = response.json()
    # Debug print if something is off
    if "candidates" not in result:
        print("API error response:", result)
        return f"Error from API: {result.get('error', {}).get('message', 'Unknown error')}"

    bot_response = result["candidates"][0]["content"]["parts"][0]["text"]

    # Add bot response to history
    conversation_history.append({
        "role": "model", # Use 'model' role for bot responses
        "parts": [{"text": bot_response}]
    })

    return bot_response

async def send_long_message(update: Update, text: str):
    """Sends a long message by splitting it into chunks."""
    max_length = 4096
    for i in range(0, len(text), max_length):
        await update.message.reply_text(text[i:i + max_length])

async def reply(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message and update.message.text:
        user_message = update.message.text
        # You can change the personality here if you want
        bot_response = chat_with_memory(user_message, "You are a helpful study assistant.")
        await send_long_message(update, bot_response)

def main():
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, reply))

    # FIX: use run_polling() WITHOUT asyncio.run()
    app.run_polling()

if __name__ == "__main__":
    main()
