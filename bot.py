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
from recommender import find_coop, find_cute_relaxing, find_by_genre
from gemini_chat import ai_chat
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
    enriched = []
    for g in owned_games:
        appid = g.get("appid")
        details = get_game_details(appid)
        item = g.copy()
        if details:
            item["genres"] = details.get("genres", [])
            item["categories"] = details.get("categories", [])
        enriched.append(item)
    return enriched


def suggest_short_games(library_list, max_minutes=60):
    return [
        g for g in library_list
        if g.get("playtime_forever", 0) <= max_minutes
    ]


async def show_results_page(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    results = context.user_data.get("current_results", [])
    page = context.user_data.get("current_page", 0)

    ITEMS = 5
    if not results:
        await query.edit_message_text(
            "No matching games found.",
            reply_markup=InlineKeyboardMarkup(
                [[InlineKeyboardButton("🔙 Back to Menu", callback_data="back")]]
            )
        )
        return

    total_pages = max(1, (len(results) + ITEMS - 1) // ITEMS)
    page = max(0, min(page, total_pages - 1))
    context.user_data["current_page"] = page

    start = page * ITEMS
    batch = results[start:start + ITEMS]

    text = f"**Found {len(results)} games (Page {page + 1}/{total_pages})**\n\n"
    for game in batch:
        cats = ", ".join(
            c.get("description", "")
            for c in game.get("categories", [])[:3]
        ) or "N/A"
        text += f"*{game['name']}*\n_{cats}_\n\n"

    buttons = []
    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton("⬅️ Previous", callback_data="next_prev_prev"))
    if page < total_pages - 1:
        nav.append(InlineKeyboardButton("Next ➡️", callback_data="next_prev_next"))
    if nav:
        buttons.append(nav)

    buttons.append([InlineKeyboardButton("🔙 Back to Menu", callback_data="back")])

    await query.edit_message_text(
        text=text,
        reply_markup=InlineKeyboardMarkup(buttons),
        parse_mode="Markdown"
    )


# ---------------- /start ----------------

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Hi! Send me your **Steam Profile URL** to begin.\n\nExample:\n"
        "https://steamcommunity.com/id/yourname/",
        parse_mode="Markdown"
    )
    return WAITING_FOR_URL


# ---------------- Handle URL ----------------

async def handle_url(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = update.message.text.strip()
    vanity = re.search(r"steamcommunity.com/id/([^/]+)", url)
    profile = re.search(r"steamcommunity.com/profiles/(\d+)", url)

    if vanity:
        steam_id = resolve_vanity_url(vanity.group(1))
    elif profile:
        steam_id = profile.group(1)
    else:
        steam_id = resolve_vanity_url(url)

    if not steam_id:
        await update.message.reply_text("❌ Invalid Steam URL. Try again.")
        return WAITING_FOR_URL

    await update.message.reply_text("⏳ Loading your Steam library...")

    games = get_owned_games(steam_id)
    if not games:
        return await update.message.reply_text("❌ Your profile must be public.")

    library_list = await enrich_library_data(games)
    library_dict = {str(g["appid"]): g for g in library_list}

    context.user_data["library_list"] = library_list
    context.user_data["library_dict"] = library_dict
    context.user_data["ai_mode"] = False

    await update.message.reply_text(f"📚 Loaded {len(library_list)} games!")

    return await show_main_menu(update, context)


# ---------------- Main Menu ----------------

async def show_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):

    keyboard = [
        [
            InlineKeyboardButton("⏱️ Short Games", callback_data="short"),
            InlineKeyboardButton("👥 Co-op", callback_data="coop"),
        ],
        [
            InlineKeyboardButton("📂 Categories", callback_data="cat_menu"),
            InlineKeyboardButton("🎲 Random", callback_data="random"),
        ],
        [
            InlineKeyboardButton("🤖 AI Chat", callback_data="ai_chat"),
        ],
    ]

    markup = InlineKeyboardMarkup(keyboard)

    if update.callback_query:
        await update.callback_query.edit_message_text(
            "What would you like to do?", reply_markup=markup
        )
    else:
        await update.message.reply_text("What would you like to do?", reply_markup=markup)

    return MAIN_MENU


# ---------------- Category Menu ----------------

async def category_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    kb = [
        [
            InlineKeyboardButton("👤 Singleplayer", callback_data="single"),
            InlineKeyboardButton("👥 Multiplayer", callback_data="multi"),
        ],
        [
            InlineKeyboardButton("⚔️ RPG", callback_data="rpg"),
            InlineKeyboardButton("💖 Cute/Relaxing", callback_data="cute"),
        ],
        [
            InlineKeyboardButton("👻 Horror", callback_data="horror"),
        ],
        [
            InlineKeyboardButton("🔙 Back", callback_data="back"),
        ]
    ]
    await update.callback_query.edit_message_text(
        "Choose a category:", reply_markup=InlineKeyboardMarkup(kb)
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
    await update.message.reply_text(reply[:4096])

    keyboard = [[InlineKeyboardButton("🔙 Back to Menu", callback_data="back")]]
    await update.message.reply_text(
        "Send another message to continue chatting, or go back:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

    return AI_CHAT


# ---------------- Button Callback Handler ----------------

async def menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    try:
        await query.answer()
    except BadRequest:
        pass

    data = query.data

    library_list = context.user_data.get("library_list", [])
    library_dict = context.user_data.get("library_dict", {})

    # ---- Back to Menu ----
    if data == "back":
        context.user_data["ai_mode"] = False
        await show_main_menu(update, context)
        return MAIN_MENU

    # ---- Pagination ----
    if data == "next_prev_next":
        context.user_data["current_page"] += 1
        await show_results_page(update, context)
        return MAIN_MENU

    if data == "next_prev_prev":
        context.user_data["current_page"] -= 1
        await show_results_page(update, context)
        return MAIN_MENU

    # ---- Category Menu ----
    if data == "cat_menu":
        return await category_menu(update, context)

    # ---- AI Chat ----
    if data == "ai_chat":
        context.user_data["ai_mode"] = True
        await query.edit_message_text("🤖 AI chat started! Send me a message.")
        return AI_CHAT

    # ---- Game Filters ----
    results = []

    if data == "short":
        results = suggest_short_games(library_list)

    elif data == "coop":
        results = find_coop(library_list)

    elif data == "cute":
        results = find_cute_relaxing(library_list)

    elif data == "single":
        results = [
            g for g in library_list
            if any(c.get("description") == "Single-player" for c in g.get("categories", []))
        ]

    elif data == "multi":
        results = [
            g for g in library_list
            if any(c.get("description") == "Multi-player" for c in g.get("categories", []))
        ]

    elif data == "rpg":
        results = find_by_genre(library_list, "RPG")

    elif data == "horror":
        results = find_by_genre(library_list, "Horror")

    elif data == "random":
        if library_list:
            results = [random.choice(library_list)]

    if results:
        context.user_data["current_results"] = results
        context.user_data["current_page"] = 0
        await show_results_page(update, context)
        return MAIN_MENU

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
            ]
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    application.add_handler(conv_handler)

    print("Bot running…")
    application.run_polling()


if __name__ == "__main__":
    main()
