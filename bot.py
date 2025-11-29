import logging
import random
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    ContextTypes,
    CommandHandler,
    MessageHandler,
    filters,
    ConversationHandler,
    CallbackQueryHandler,
)
from steam import resolve_vanity_url, get_owned_games, get_game_details
from recommender import find_coop, find_cute_relaxing, find_by_genre
import re

# --- Configuration ---
TOKEN = "8493785994:AAHFydSXKNj2BQ4lf_tkdTPgNmcLy48g6FM"  # Replace with your actual token

# --- States for ConversationHandler ---
WAITING_FOR_URL, MAIN_MENU = range(2)

# --- Logging Setup ---
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

#================== HELPER FUNCTIONS ==================

def suggest_short_games(library_data, max_minutes=60): #COMPLETELY WRONG!! --- no dataset for this, so use GEMINI to suggest from library
    """
    Filter for games with playtime under a certain limit (e.g., 1 hour).
    Note: playtime_forever is in minutes.
    """
    # Filter games that have been played but less than max_minutes
    # Or games that haven't been played (0 minutes)
    return [
        g for g in library_data 
        if g.get('playtime_forever', 0) <= max_minutes
    ]

async def enrich_library_data(owned_games): # owned games get more details from steam store API (categories, genres)
    enriched_library = []
    for game in owned_games: 
        appid = game.get('appid')
        details = get_game_details(appid) # uses local cache logic
        
        game_copy = game.copy()
        if details:
            game_copy['categories'] = details.get('categories', [])
            game_copy['genres'] = details.get('genres', [])
            game_copy['price_overview'] = details.get('price_overview', {})
            game_copy['short_description'] = details.get('short_description', "")
            game_copy['reviews'] = details.get('reviews', "")
        enriched_library.append(game_copy)
    return enriched_library

# --- Bot Command Handlers ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    
    # Check if we already have the SteamID in user_data
    if 'steam_id' in context.user_data:
        await update.message.reply_text(f"Welcome back, {user.first_name}!")
        return await show_main_menu(update, context)
    
    await update.message.reply_text(
        f"Hi {user.first_name}! I'm your Steam Library Assistant.\n\n"
        "To get started, please send me your **Steam Profile URL**.\n"
        "(e.g., https://steamcommunity.com/id/yourname/)",
        parse_mode='Markdown'
    )
    return WAITING_FOR_URL

async def handle_url(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Validates URL and fetches library."""
    url = update.message.text.strip()
    
    """ Extract vanity name or ID (Simple logic, relying on steam.py mostly)
    !! resolve_vanity_url expects just the name, not the full URL,
    but we parse it here for user convenience."""

    vanity_match = re.search(r"steamcommunity.com/id/([^/]+)", url)
    profile_match = re.search(r"steamcommunity.com/profiles/(\d+)", url)
    
    steam_id = None
    if vanity_match:
        vanity_name = vanity_match.group(1)
        steam_id = resolve_vanity_url(vanity_name)
    elif profile_match:
        steam_id = profile_match.group(1)
    else:
        # Try passing raw text if user just sent the name
        steam_id = resolve_vanity_url(url)

    if not steam_id:
        await update.message.reply_text(
            "❌ I couldn't resolve that URL to a Steam ID.\n"
            "Please make sure it's a valid public profile URL and try again."
        )
        return WAITING_FOR_URL

    await update.message.reply_text("✅ Found profile! Fetching your library... (this might take a moment)")

    # Fetch Library
    games = get_owned_games(steam_id)
    if not games:
        await update.message.reply_text("❌ I couldn't find any games. Make sure your profile is public.")
        return WAITING_FOR_URL

    # Enrich Data (categories, genres, prices, description, etc.)
    library = await enrich_library_data(games)

    # Save to context
    context.user_data['steam_id'] = steam_id
    context.user_data['library'] = library
    
    await update.message.reply_text(f"📚 Successfully loaded {len(games)} games!")
    return await show_main_menu(update, context)

async def show_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Displays the main menu options."""
    keyboard = [
        [
            InlineKeyboardButton("⏱️ Max 1 Hour", callback_data="short"), #CHANGE THIS OPTION TO HAVE MULTIPLE OPTIONS LATER (30 mins, 1 hour, etc.)
            InlineKeyboardButton("👥 Co-op", callback_data="coop"),
        ],
        [
            InlineKeyboardButton("💖 Relaxing", callback_data="cute"),
            InlineKeyboardButton("🎲 Random Pick", callback_data="random"),
        ],
        [
            InlineKeyboardButton("📊 Smart Analysis", callback_data="analysis"),
            InlineKeyboardButton("⚙️ Change Profile", callback_data="change_profile"),
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    text = "What are you looking for today?"
    
    # If called from a button click (CallbackQuery), edit the message
    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.edit_message_text(text=text, reply_markup=reply_markup)
    else:
        # If called from /start, send a new message
        await update.message.reply_text(text, reply_markup=reply_markup)
    
    return MAIN_MENU

async def menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles button clicks from the main menu."""
    query = update.callback_query
    await query.answer() # Acknowledge the button click
    
    data = query.data
    library = context.user_data.get('library', [])
    
    if not library and data != "change_profile":
        await query.edit_message_text("⚠️ Library data missing. Please /start again.")
        return ConversationHandler.END

    results = []
    response_text = ""

    if data == "short":
        results = suggest_short_games(library, max_minutes=60)
        response_text = "⏱️ **Quick Games (Under 1 Hour):**\n"
        
    elif data == "coop":
        results = find_coop(library)
        response_text = "👥 **Co-op Games:**\n"
        
    elif data == "cute":
        results = find_cute_relaxing(library)
        response_text = "💖 **Relaxing Games:**\n"
        
    elif data == "random":
        if library:
            results = [random.choice(library)]
        response_text = "🎲 **Random Pick:**\n"
        
    elif data == "analysis":
        # Simple analysis logic
        total_playtime = sum(g.get('playtime_forever', 0) for g in library)
        hours = total_playtime // 60
        response_text = (
            f"📊 **Library Analysis**\n"
            f"Total Games: {len(library)}\n"
            f"Total Playtime: {hours} hours\n"
            f"Most Played: {max(library, key=lambda x: x.get('playtime_forever', 0))['name']}"
        )
        # Skip the standard result loop for analysis
        keyboard = [[InlineKeyboardButton("🔙 Back to Menu", callback_data="back")]]
        await query.edit_message_text(text=response_text, reply_markup=InlineKeyboardMarkup(keyboard))
        return MAIN_MENU

    elif data == "change_profile":
        context.user_data.clear()
        await query.edit_message_text("⚙️ Profile cleared.")
        # Trigger the start flow again
        await query.message.reply_text("Please send your Steam Profile URL.")
        return WAITING_FOR_URL
    
    elif data == "back":
        return await show_main_menu(update, context)

    # --- Format Results ---
    if not results:
        response_text += "No matching games found in your library."
    else:
        # Take top 5
        for game in results[:5]:
            name = game.get('name', 'Unknown')
            playtime = game.get('playtime_forever', 0)
            hours = round(playtime / 60, 1)
            response_text += f"• {name} ({hours} hrs)\n"

    # Add a "Back" button
    keyboard = [[InlineKeyboardButton("🔙 Back to Menu", callback_data="back")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(text=response_text, reply_markup=reply_markup, parse_mode='Markdown')
    return MAIN_MENU

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Cancels and ends the conversation."""
    await update.message.reply_text("Bye! Type /start to chat again.")
    return ConversationHandler.END

def main():
    """Run the bot."""
    application = ApplicationBuilder().token(TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            WAITING_FOR_URL: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_url)],
            MAIN_MENU: [CallbackQueryHandler(menu_callback)],
        },
        fallbacks=[CommandHandler("cancel", cancel)]
    )

    application.add_handler(conv_handler)
    
    print("Bot is polling...")
    application.run_polling()

if __name__ == "__main__":
    main()