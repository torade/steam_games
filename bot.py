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

def suggest_short_games(library_data, max_minutes=60): 
    """
    Filter for games with playtime under a certain limit (e.g., 1 hour).
    Note: playtime_forever is in minutes.
    """
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
            # Updated to match steam.py's new output structure
            game_copy['price_str'] = details.get('price_str', "N/A")
            game_copy['score'] = details.get('score', "N/A")
            game_copy['desc'] = details.get('desc', "")
        enriched_library.append(game_copy)
    return enriched_library

async def show_results_page(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Helper to display a page of results."""
    query = update.callback_query
    results = context.user_data.get('current_results', [])
    page = context.user_data.get('current_page', 0)
    ITEMS_PER_PAGE = 5
    
    if not results:
        await query.edit_message_text(
            text="No matching games found in your library.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back to Menu", callback_data="back")]])
        )
        return

    # Calculate total pages
    total_pages = (len(results) + ITEMS_PER_PAGE - 1) // ITEMS_PER_PAGE
    
    # Ensure page is valid
    if page < 0: page = 0
    if page >= total_pages: page = total_pages - 1
    
    # Slice data
    start_idx = page * ITEMS_PER_PAGE
    end_idx = start_idx + ITEMS_PER_PAGE
    current_batch = results[start_idx:end_idx]
    
    # Build Message
    response_text = f"**Found {len(results)} games (Page {page + 1}/{total_pages}):**\n\n"
    
    for game in current_batch:
        name = game.get('name', 'Unknown')
        playtime = round(game.get('playtime_forever', 0) / 60, 1)
        
        # Extract category descriptions
        categories = [c.get('description') for c in game.get('categories', [])]
        categories_str = ", ".join(categories[:3]) if categories else "N/A"
        
        response_text += f"*{name}*\n"
        response_text += f"_{categories_str} | {playtime} hrs_\n\n"

    # Build Navigation Buttons
    buttons = []
    nav_row = []
    if page > 0:
        nav_row.append(InlineKeyboardButton("⬅️ Previous", callback_data="prev_page"))
    if page < total_pages - 1:
        nav_row.append(InlineKeyboardButton("Next ➡️", callback_data="next_page"))
    
    if nav_row:
        buttons.append(nav_row)
        
    buttons.append([InlineKeyboardButton("🔙 Back to Menu", callback_data="back")])
    
    await query.edit_message_text(
        text=response_text, 
        reply_markup=InlineKeyboardMarkup(buttons), 
        parse_mode='Markdown'
    )

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
            InlineKeyboardButton("⏱️ Max 1 Hour", callback_data="short"),
            InlineKeyboardButton("👥 Co-op", callback_data="coop"),
        ],
        [
            InlineKeyboardButton("📂 Category / Genre", callback_data="category_menu"),
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

async def show_category_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Displays the category submenu."""
    keyboard = [
        [
            InlineKeyboardButton("👤 Singleplayer", callback_data="cat_single"),
            InlineKeyboardButton("👥 Multiplayer", callback_data="cat_multi"),
        ],
        [
            InlineKeyboardButton("⚔️ RPG", callback_data="cat_rpg"),
            InlineKeyboardButton("💖 Cute & Relaxing", callback_data="cat_cute"),
        ],
        [
            InlineKeyboardButton("👻 Horror", callback_data="cat_horror"),
        ],
        [
            InlineKeyboardButton("🔙 Back to Main Menu", callback_data="back"),
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    query = update.callback_query
    await query.edit_message_text(text="Select a category or genre:", reply_markup=reply_markup)
    return MAIN_MENU

async def menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles button clicks from the main menu."""
    query = update.callback_query
    await query.answer() # Acknowledge the button click
    
    data = query.data
    library = context.user_data.get('library', [])
    
    # Handle Navigation
    if data == "next_page":
        context.user_data['current_page'] += 1
        return await show_results_page(update, context)
    elif data == "prev_page":
        context.user_data['current_page'] -= 1
        return await show_results_page(update, context)
    elif data == "back":
        return await show_main_menu(update, context)
    elif data == "category_menu":
        return await show_category_menu(update, context)
    
    # Handle Profile Change
    if data == "change_profile":
        context.user_data.clear()
        await query.edit_message_text("⚙️ Profile cleared.")
        await query.message.reply_text("Please send your Steam Profile URL.")
        return WAITING_FOR_URL

    if not library:
        await query.edit_message_text("⚠️ Library data missing. Please /start again.")
        return ConversationHandler.END

    # Handle Filters
    results = []
    
    if data == "short":
        results = suggest_short_games(library, max_minutes=60)
    elif data == "coop":
        results = find_coop(library)
    elif data == "cat_cute":
        results = find_cute_relaxing(library)
    elif data == "cat_single":
        results = [g for g in library if any(c.get('description') == 'Single-player' for c in g.get('categories', []))]
    elif data == "cat_multi":
        results = [g for g in library if any(c.get('description') == 'Multi-player' for c in g.get('categories', []))]
    elif data == "cat_rpg":
        results = find_by_genre(library, "RPG")
    elif data == "cat_horror":
        results = find_by_genre(library, "Horror")
    elif data == "random":
        if library:
            results = [random.choice(library)]
    elif data == "analysis":
        # Analysis doesn't use pagination logic
        total_playtime = sum(g.get('playtime_forever', 0) for g in library)
        hours = total_playtime // 60
        most_played = max(library, key=lambda x: x.get('playtime_forever', 0))
        response_text = (
            f"📊 **Library Analysis**\n"
            f"Total Games: {len(library)}\n"
            f"Total Playtime: {hours} hours\n"
            f"Most Played: {most_played['name']} ({round(most_played.get('playtime_forever',0)/60, 1)} hrs)"
        )
        keyboard = [[InlineKeyboardButton("🔙 Back to Menu", callback_data="back")]]
        await query.edit_message_text(text=response_text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
        return MAIN_MENU

    # Save results and reset page for pagination
    context.user_data['current_results'] = results
    context.user_data['current_page'] = 0
    
    await show_results_page(update, context)
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