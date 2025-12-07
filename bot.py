import logging
import random
import re

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)
from telegram.ext import (
    ApplicationBuilder,
    ContextTypes,
    CommandHandler,
    MessageHandler,
    ConversationHandler,
    CallbackQueryHandler,
    filters,
)
from telegram.error import BadRequest

from steam import resolve_vanity_url, get_owned_games, get_game_details
from recommender import find_coop, find_cute_relaxing, find_by_genre, find_fps
from gmini_chat import ai_chat
from API_keys import TELEGRAM_TOKEN

# ---------------- CONFIG & STATES ----------------
TOKEN = TELEGRAM_TOKEN

WAITING_FOR_URL, MAIN_MENU, AI_CHAT = range(3)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


# ---------------- Helper Functions ----------------

async def enrich_library_data(owned_games):
    """
    Enrich owned games with Steam Store details (categories, genres, desc, header_image, etc.)
    using get_game_details (which uses local cache).
    """
    enriched_library = []
    for game in owned_games:
        appid = game.get("appid")
        details = get_game_details(appid)  # uses local cache logic

        game_copy = game.copy()
        if details:
            game_copy["categories"] = details.get("categories", [])
            game_copy["genres"] = details.get("genres", [])
            game_copy["price_str"] = details.get("price_str", "N/A")
            game_copy["score"] = details.get("score", "N/A")
            game_copy["desc"] = details.get("desc", "")
            game_copy["header_image"] = details.get("header_image")
        enriched_library.append(game_copy)

    return enriched_library


def suggest_short_games(library_data, max_minutes=60):
    """Filter games with playtime under a certain limit (in minutes)."""
    return [
        g for g in library_data
        if g.get("playtime_forever", 0) <= max_minutes
    ]


async def show_results_page(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    results = context.user_data.get("current_results", [])
    page = context.user_data.get("current_page", 0)
    ITEMS_PER_PAGE = 5

    if not results:
        await query.edit_message_text(
            text="No matching games found in your library.",
            reply_markup=InlineKeyboardMarkup(
                [[InlineKeyboardButton("🔙 Back to Menu", callback_data="back")]]
            ),
        )
        return

    # Total pages
    total_pages = (len(results) + ITEMS_PER_PAGE - 1) // ITEMS_PER_PAGE

    # Clamp page
    if page < 0:
        page = 0
    if page >= total_pages:
        page = total_pages - 1
    context.user_data["current_page"] = page

    # Slice data
    start_idx = page * ITEMS_PER_PAGE
    end_idx = start_idx + ITEMS_PER_PAGE
    current_batch = results[start_idx:end_idx]

    # ----- Text list -----
    response_text = f"**Found {len(results)} games (Page {page + 1}/{total_pages}):**\n\n"

    for game in current_batch:
        name = game.get("name", "Unknown")
        playtime = round(game.get("playtime_forever", 0) / 60, 1)

        categories = [c.get("description") for c in game.get("categories", [])]
        categories_str = ", ".join(categories[:3]) if categories else "N/A"

        response_text += f"*{name}*\n"
        response_text += f"_{categories_str} | {playtime} hrs_\n\n"

    # ----- Buttons -----
    buttons = []
    nav_row = []
    if page > 0:
        nav_row.append(InlineKeyboardButton("⬅️ Previous page", callback_data="prev_page"))
    if page < total_pages - 1:
        nav_row.append(InlineKeyboardButton("Next page ➡️", callback_data="next_page"))

    if nav_row:
        buttons.append(nav_row)

    buttons.append([InlineKeyboardButton("🔙 Back to Menu", callback_data="back")])

    # Edit main text message
    await query.edit_message_text(
        text=response_text,
        reply_markup=InlineKeyboardMarkup(buttons),
        parse_mode="Markdown",
    )

    # ----- Send ALL cover images for current page -----
    for game in current_batch:
        cover = game.get("header_image")
        if not cover:
            continue

        name = game.get("name", "Unknown")
        playtime = round(game.get("playtime_forever", 0) / 60, 1)
        caption = f"{name}\n{playtime} hrs"

        await query.message.reply_photo(photo=cover, caption=caption)

    # ----- Send bottom action buttons again -----
    await query.message.reply_text(
        "👇 Choose what to do next:",
        reply_markup=InlineKeyboardMarkup(buttons),
    )


# ---------------- /start ----------------

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Entry point: ask for Steam profile URL, or go straight to menu if we already know this user."""
    user = update.effective_user

    # If library already loaded, jump back to menu
    if "library_list" in context.user_data:
        await update.message.reply_text(f"Welcome back, {user.first_name}!")
        return await show_main_menu(update, context)

    await update.message.reply_text(
        f"Hi {user.first_name}! I'm your Steam Library Assistant.\n\n"
        "To get started, please send me your **Steam Profile URL**.\n"
        "(e.g., https://steamcommunity.com/id/yourname/)",
        parse_mode="Markdown",
    )
    return WAITING_FOR_URL


# ---------------- Handle URL ----------------

async def handle_url(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Validates URL, resolves SteamID, fetches and enriches the library."""
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
        # Try passing raw text if user just sent the custom name
        steam_id = resolve_vanity_url(url)

    if not steam_id:
        await update.message.reply_text(
            "❌ I couldn't resolve that URL to a Steam ID.\n"
            "Please make sure it's a valid public profile URL and try again."
        )
        return WAITING_FOR_URL

    await update.message.reply_text(
        "✅ Found profile! Fetching your library... (this might take a moment)"
    )

    games = get_owned_games(steam_id)
    if not games:
        await update.message.reply_text(
            "❌ I couldn't find any games. Make sure your profile is public."
        )
        return WAITING_FOR_URL

    library_list = await enrich_library_data(games)

    # Build dict for AI chat (appid -> game)
    library_dict = {str(g["appid"]): g for g in library_list}

    # Save to context
    context.user_data["steam_id"] = steam_id
    context.user_data["library_list"] = library_list
    context.user_data["library_dict"] = library_dict
    context.user_data["ai_mode"] = False

    await update.message.reply_text(
        f"📚 Successfully loaded {len(library_list)} games!"
    )
    return await show_main_menu(update, context)


# ---------------- Main Menu ----------------

async def show_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Main menu with SIX options from second version + AI Chat:
      ⏱️ Max 1 Hour
      👥 Co-op
      📂 Category / Genre
      🎲 Random Pick
      📊 Smart Analysis
      ⚙️ Change Profile
      🤖 AI Chat
    """
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
            InlineKeyboardButton("🤖 AI Chat", callback_data="ai_chat"),
        ],
        [
            InlineKeyboardButton("⚙️ Change Profile", callback_data="change_profile"),
        ],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    text = "What are you looking for today?"

    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.edit_message_text(
            text=text, reply_markup=reply_markup
        )
    else:
        await update.message.reply_text(text, reply_markup=reply_markup)

    return MAIN_MENU


# ---------------- Category Menu ----------------

async def show_category_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Big genre menu from second version."""
    keyboard = [
        [
            InlineKeyboardButton("🎮 Action", callback_data="cat_action"),
            InlineKeyboardButton("🔫 FPS", callback_data="cat_fps"),
        ],
        [
            InlineKeyboardButton("⚔️ RPG", callback_data="cat_rpg"),
            InlineKeyboardButton("🧠 Strategy", callback_data="cat_strategy"),
        ],
        [
            InlineKeyboardButton("🏎️ Racing", callback_data="cat_racing"),
            InlineKeyboardButton("👾 Indie", callback_data="cat_indie"),
        ],
        [
            InlineKeyboardButton("🧩 Puzzle", callback_data="cat_puzzle"),
            InlineKeyboardButton("😱 Horror", callback_data="cat_horror"),
        ],
        [
            InlineKeyboardButton("🌍 Open World", callback_data="cat_openworld"),
            InlineKeyboardButton("🛠 Simulation", callback_data="cat_simulation"),
        ],
        [
            InlineKeyboardButton("🔙 Back to Main Menu", callback_data="back"),
        ],
    ]

    await update.callback_query.message.reply_text(
        "Choose a game genre:",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )
    return MAIN_MENU


# ---------------- AI Chat Text Handler ----------------

async def ai_text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.user_data.get("ai_mode"):
        return

    if not update.message:
        return

    user_msg = update.message.text
    library_dict = context.user_data.get("library_dict", {})

    if user_msg.lower() in ["exit", "quit", "bye"]:
        context.user_data["ai_mode"] = False
        await update.message.reply_text("AI chat ended. Returning to menu…")
        await show_main_menu(update, context)
        return MAIN_MENU

    reply = ai_chat(user_msg, library_dict)

    if reply:
        await update.message.reply_text(reply[:4096])
    else:
        await update.message.reply_text(
            "Sorry, I couldn't generate a reply this time."
        )

    keyboard = [[InlineKeyboardButton("🔙 Back to Menu", callback_data="back")]]
    await update.message.reply_text(
        "Send another message to continue chatting, or go back:",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )

    return AI_CHAT

# ---------------- Button Callback Handler ----------------

async def menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle ALL button presses (menu, filters, pagination, AI, etc.)."""
    query = update.callback_query
    try:
        await query.answer()
    except BadRequest:
        # Sometimes Telegram complains if we've already answered
        pass

    data = query.data
    library_list = context.user_data.get("library_list", [])

    # ---- Navigation: back to main menu ----
    if data == "back":
        context.user_data["ai_mode"] = False
        return await show_main_menu(update, context)

    # ---- Pagination ----
    if data == "next_page":
        context.user_data["current_page"] = context.user_data.get("current_page", 0) + 1
        await show_results_page(update, context)
        return MAIN_MENU

    if data == "prev_page":
        context.user_data["current_page"] = context.user_data.get("current_page", 0) - 1
        await show_results_page(update, context)
        return MAIN_MENU

    # ---- Category Menu ----
    if data == "category_menu":
        return await show_category_menu(update, context)

    # ---- Change Profile ----
    if data == "change_profile":
        context.user_data.clear()
        await query.edit_message_text("⚙️ Profile cleared.")
        await query.message.reply_text("Please send your Steam Profile URL.")
        return WAITING_FOR_URL

    # ---- Start AI Chat ----
    if data == "ai_chat":
        context.user_data["ai_mode"] = True
        await query.edit_message_text("🤖 AI chat started! Send me a message.")
        return AI_CHAT

    # If we reach here, we expect library data
    if not library_list:
        await query.edit_message_text(
            "⚠️ Library data missing. Please /start again."
        )
        return ConversationHandler.END

    # ---- Filters ----
    results = []

    if data == "short":
        results = suggest_short_games(library_list, max_minutes=60)

    elif data == "coop":
        results = find_coop(library_list)

    elif data == "cat_action":
        results = find_by_genre(library_list, "Action")

    elif data == "cat_fps":
        results = find_fps(library_list)

    elif data == "cat_rpg":
        results = find_by_genre(library_list, "RPG")

    elif data == "cat_strategy":
        results = find_by_genre(library_list, "Strategy")

    elif data == "cat_racing":
        results = find_by_genre(library_list, "Racing")

    elif data == "cat_indie":
        results = find_by_genre(library_list, "Indie")

    elif data == "cat_puzzle":
        results = find_by_genre(library_list, "Puzzle")

    elif data == "cat_horror":
        results = find_by_genre(library_list, "Horror")

    elif data == "cat_openworld":
        results = find_by_genre(library_list, "Open World")

    elif data == "cat_simulation":
        results = find_by_genre(library_list, "Simulation")

    elif data == "random":
        if library_list:
            results = [random.choice(library_list)]

    elif data == "analysis":
        # Simple stats about the library
        total_playtime = sum(g.get("playtime_forever", 0) for g in library_list)
        hours = total_playtime // 60
        most_played = max(
            library_list, key=lambda x: x.get("playtime_forever", 0)
        )
        response_text = (
            f"📊 **Library Analysis**\n"
            f"Total Games: {len(library_list)}\n"
            f"Total Playtime: {hours} hours\n"
            f"Most Played: {most_played['name']} "
            f"({round(most_played.get('playtime_forever', 0) / 60, 1)} hrs)"
        )
        keyboard = [[InlineKeyboardButton("🔙 Back to Menu", callback_data="back")]]
        await query.edit_message_text(
            text=response_text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown",
        )
        return MAIN_MENU

    # Save results for pagination (if any filter produced results)
    if results:
        context.user_data["current_results"] = results
        context.user_data["current_page"] = 0
        await show_results_page(update, context)

    return MAIN_MENU


# ---------------- Cancel ----------------

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Bye! Type /start to begin again.")
    return ConversationHandler.END


# ---------------- Main ----------------

def main():
    application = ApplicationBuilder().token(TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            WAITING_FOR_URL: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_url)
            ],
            MAIN_MENU: [
                CallbackQueryHandler(menu_callback),
                MessageHandler(filters.TEXT & ~filters.COMMAND, ai_text_handler),
            ],
            AI_CHAT: [
                CallbackQueryHandler(menu_callback),
                MessageHandler(filters.TEXT & ~filters.COMMAND, ai_text_handler),
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    application.add_handler(conv_handler)

    print("Bot running…")
    application.run_polling()


if __name__ == "__main__":
    main()
