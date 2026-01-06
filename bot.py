# ---------------- IMPORTS ----------------
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
from steam import resolve_vanity_url, get_owned_games, get_game_details, fetch_game_tags
from recommender import find_coop, find_cute_relaxing, find_by_genre, find_fps, find_short_games
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
            game_copy["tags"] = details.get("tags", {})  # ADD THIS LINE - this was missing!
        enriched_library.append(game_copy)

    return enriched_library


def unplayed_games(library_data, max_minutes=60):
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
    search_title = context.user_data.get("search_title", "your library")
    response_text = f"**Found {len(results)} games (Page {page + 1}/{total_pages}) for {search_title}:**\n\n"

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
        name = game.get("name", "Unknown")
        playtime = round(game.get("playtime_forever", 0) / 60, 1)

        if cover:
            text_msg = (
                f'<a href="{cover}">&#8203;</a>'
                f"<b>{name}</b>\n"
                f"{playtime} hrs"
            )
        else:
            text_msg = f"<b>{name}</b>\n{playtime} hrs"

        await query.message.reply_text(text=text_msg, parse_mode="HTML")

    # ----- Send bottom action buttons again -----
    await query.message.reply_text(
        "👇 Choose what to do next:",
        reply_markup=InlineKeyboardMarkup(buttons),
    )


# ---------------- /start ----------------

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Entry point: ask for Steam profile URL, or go straight to menu if we already know this user.

    If an argument is provided with the command (e.g., `/start BAILOPANN`),
    attempt to resolve that argument as a vanity name or profile URL and
    fetch the library immediately.
    """
    user = update.effective_user

    # If library already loaded, jump back to menu
    if "library_list" in context.user_data:
        await update.message.reply_text(f"Welcome back, {user.first_name}!")
        return await show_main_menu(update, context)

    # If user passed an argument with /start (e.g., /start BAILOPANN), try to fetch immediately
    args = getattr(context, "args", []) or []
    if args:
        arg_text = " ".join(args).strip()

        await update.message.reply_text(
            f"Looking up Steam profile for '{arg_text}'..."
        )

        # Reuse the same resolution logic from handle_url
        vanity_match = re.search(r"steamcommunity.com/id/([^/]+)", arg_text)
        profile_match = re.search(r"steamcommunity.com/profiles/(\d+)", arg_text)

        steam_id = None
        if vanity_match:
            steam_id = resolve_vanity_url(vanity_match.group(1))
        elif profile_match:
            steam_id = profile_match.group(1)
        else:
            # Try resolving raw text as a vanity name or numeric id
            steam_id = resolve_vanity_url(arg_text)

        if not steam_id:
            await update.message.reply_text(
                "❌ I couldn't resolve that argument to a Steam ID.\n"
                "Please make sure it's a valid vanity name or public profile URL."
            )
            return WAITING_FOR_URL

        await update.message.reply_text(
            "✅ Found profile! Fetching your library... (this might take a moment)"
        )

        games = get_owned_games(steam_id)
        if not games:
            await update.message.reply_text(
                "❌ I couldn't find any games. Make sure the profile is public."
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

    # Default: ask user for their Steam profile URL
    await update.message.reply_text(
        f"Hi {user.first_name}! I'm your Steam Library Assistant.\n\n"
        "To get started, please send me your **Steam Profile URL**.\n"
        "(e.g., https://steamcommunity.com/id/yourname/)",
        parse_mode="Markdown",
    )
    return WAITING_FOR_URL


# ---------------- /help ----------------

async def help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Display help information."""
    help_text = (
        "🤖 **Steam Library Assistant Help**\n\n"
        "Use /start {your custom URL} to begin or change your Steam profile.\n\n"
        "Available commands:\n"
        "/start {your custom URL} - Start or restart the bot\n"
        "/cancel - End the conversation\n"
        "/help - Show this help message\n\n"
        "In the main menu, you can filter your games by playtime, co-op availability, "
        "genre, get random picks, or analyze your library.\n\n"
        "You can also chat with the AI about your game library by selecting 'AI Chat' "
        "from the menu."
    )
    # Send help text
    if update.message:
        await update.message.reply_text(help_text, parse_mode="Markdown")

    # If library is already loaded, show main menu; otherwise prompt to /start
    if "library_list" in context.user_data:
        return await show_main_menu(update, context)
    else:
        await update.message.reply_text("Type /start to load your Steam profile.")
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


# ---------------- Multi-Filter Setup ----------------

TAG_GROUPS = {
    "btn_shooter": ["FPS", "Shooter", "Third-Person Shooter", "Hero Shooter", "Arena Shooter", "Looter Shooter", "Shoot 'Em Up", "Sniper"],
    "btn_rpg": ["RPG", "Action RPG", "JRPG", "Strategy RPG", "Turn-Based", "Party-Based RPG", "Roguelike", "Rogue-lite"],
    "btn_strategy": ["Strategy", "RTS", "Turn-Based Strategy", "Grand Strategy", "City Builder", "Management", "Colony Sim", "4X", "Tower Defense", "Card Game"],
    "btn_story": ["Story Rich", "Narrative", "Visual Novel", "Choices Matter", "Interactive Fiction", "Walking Simulator", "Lore-Rich", "Atmospheric"],
    "btn_coop": ["Co-op", "Online Co-Op", "Local Co-Op", "Multiplayer", "4 Player Local", "Split Screen"],
    "btn_horror": ["Horror", "Survival Horror", "Psychological Horror", "Dark", "Zombies", "Gore"],
    "btn_chill": ["Relaxing", "Cozy", "Casual", "Farming Sim", "Wholesome", "Puzzle", "Family Friendly", "Life Sim", "Simulation"],
    "btn_action": ["Action", "Fast-Paced", "Hack and Slash", "Beat 'em up", "Fighting", "Spectacle fighter", "Platformer", "2D Platformer", "3D Platformer"],
    "btn_openworld": ["Open World", "Open World Survival Craft", "Sandbox", "Exploration", "Survival", "Crafting"],
    "btn_comedy": ["Comedy", "Funny", "Parody", "Memes", "Dark Humor", "Satire"],
    "btn_scifi": ["Sci-fi", "Space", "Cyberpunk", "Futuristic", "Robots", "Mechs", "Aliens"],
    "btn_fantasy": ["Fantasy", "Magic", "Medieval", "Dragons", "Dungeon Crawler"]
}

# Friendly labels for each filter
FILTER_LABELS = {
    "btn_shooter": "🔫 Shooter",
    "btn_rpg": "⚔️ RPG",
    "btn_strategy": "🧠 Strategy",
    "btn_story": "📖 Story Rich",
    "btn_coop": "👥 Co-op",
    "btn_horror": "👻 Horror",
    "btn_chill": "☕ Chill/Relaxing",
    "btn_action": "💥 Action",
    "btn_openworld": "🌍 Open World",
    "btn_comedy": "😂 Comedy",
    "btn_scifi": "🚀 Sci-Fi",
    "btn_fantasy": "🐉 Fantasy",
    "btn_unplayed": "⏱️ Unplayed"
}


def check_tags(game, allowed_tags):
    """
    Returns True if the game has at least one of the allowed_tags.
    Case-insensitive comparison.
    """
    game_tags = game.get("tags", {})
    if not game_tags:
        return False
    
    # Convert game tags to lowercase for comparison
    if isinstance(game_tags, dict):
        game_tags_lower = {tag.lower() for tag in game_tags.keys()}
    else:
        return False
    
    allowed_tags_lower = {tag.lower() for tag in allowed_tags}
    
    # Check if there's any intersection
    return bool(game_tags_lower & allowed_tags_lower)

def filter_unplayed(library_data):
    """Filter for unplayed games (< 60 minutes)."""
    return [g for g in library_data if g.get("playtime_forever", 0) < 60]

# Build FILTER_MAP dynamically from TAG_GROUPS
FILTER_MAP = {
    key: {
        "label": FILTER_LABELS[key],
        "func": lambda lib, tags=tags: [g for g in lib if check_tags(g, tags)]
    }
    for key, tags in TAG_GROUPS.items()
}

# Add manual entry for "Unplayed"
FILTER_MAP["btn_unplayed"] = {
    "label": FILTER_LABELS["btn_unplayed"],
    "func": filter_unplayed
}

def apply_filters(library_list, selected_filters):
    """Applies all selected filters sequentially (AND logic)."""
    current_results = library_list
    for key in selected_filters:
        if key in FILTER_MAP:
            filter_func = FILTER_MAP[key]["func"]
            current_results = filter_func(current_results)
    return current_results

def get_multifilter_keyboard(selected_filters):
    """
    Returns an InlineKeyboardMarkup for the multi-filter menu.
    Organizes buttons in a 2-column grid.
    """
    keyboard = []
    
    # Get all filter keys in a specific order
    filter_keys = [
        "btn_shooter", "btn_rpg",
        "btn_strategy", "btn_story",
        "btn_coop", "btn_horror",
        "btn_chill", "btn_action",
        "btn_openworld", "btn_comedy",
        "btn_scifi", "btn_fantasy",
        "btn_unplayed"
    ]
    
    # Create rows of 2 buttons each
    for i in range(0, len(filter_keys), 2):
        row = []
        for j in range(2):
            if i + j < len(filter_keys):
                key = filter_keys[i + j]
                icon = "✅" if key in selected_filters else "⬜"
                label = f"{icon} {FILTER_LABELS[key]}"
                row.append(InlineKeyboardButton(label, callback_data=f"toggle_{key}"))
        keyboard.append(row)
    
    # Add action buttons
    keyboard.append([InlineKeyboardButton("🔎 Search", callback_data="search_filters")])
    keyboard.append([InlineKeyboardButton("🔙 Back to Main Menu", callback_data="back")])
    
    return InlineKeyboardMarkup(keyboard)


# ---------------- Main Menu ----------------

async def show_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Main menu with SIX options from second version + AI Chat:
      ⏱️ Unplayed games
      ⏳ Short games
      🎲 Random Pick
      📊 Smart Analysis
      ⚙️ Change Profile
      🤖 AI Chat
    """
    keyboard = [
        [
            InlineKeyboardButton("⏱️ Unplayed", callback_data="unplayed"),
            InlineKeyboardButton("⏳ Short", callback_data="short_games"),
            InlineKeyboardButton("🎲 Random", callback_data="random"),

        ],
        [
            InlineKeyboardButton("📊 Smart Analysis", callback_data="analysis"),
            InlineKeyboardButton("🤖 AI Chat", callback_data="ai_chat"),
        ],
        [
            InlineKeyboardButton("🎛️ Categories", callback_data="categories"),
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


async def show_multifilter_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Displays the multi-filter menu with checkboxes."""
    selected = context.user_data.get("selected_filters", set())
    
    reply_markup = get_multifilter_keyboard(selected)

    if update.callback_query:
        await update.callback_query.edit_message_text(
            text="Select filters to apply (AND logic):\nGames must match ALL selected filters.",
            reply_markup=reply_markup
        )
    else:
        await update.message.reply_text(
            text="Select filters to apply (AND logic):\nGames must match ALL selected filters.",
            reply_markup=reply_markup
        )
    return MAIN_MENU


# ---------------- Category Menu ----------------

async def show_category_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Big genre menu from second version."""
    keyboard = [
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

    # ---- Short Games ----
    if data == "short_games":
        results = find_short_games(library_list)
        search_title = "Short Games"
        
        if results:
            context.user_data["current_results"] = results
            context.user_data["current_page"] = 0
            context.user_data["search_title"] = search_title
            await show_results_page(update, context)
        else:
            await query.edit_message_text(
                text="No short games found in your library.",
                reply_markup=InlineKeyboardMarkup(
                    [[InlineKeyboardButton("🔙 Back to Menu", callback_data="back")]]
                ),
            )
        return MAIN_MENU
        
    # ---- Multi-Filter Menu ----
    if data == "categories":
        if "selected_filters" not in context.user_data:
            context.user_data["selected_filters"] = set()
        return await show_multifilter_menu(update, context)

    if data.startswith("toggle_"):
        key = data.replace("toggle_", "")
        selected = context.user_data.get("selected_filters", set())

        if key in selected:
            selected.remove(key)
        else:
            selected.add(key)

        context.user_data["selected_filters"] = selected
        return await show_multifilter_menu(update, context)

    if data == "search_filters":
        selected = context.user_data.get("selected_filters", set())
        results = apply_filters(library_list, selected)
        
        # Create a title from selected filters
        if selected:
            filter_labels = [FILTER_MAP[k]["label"] for k in selected if k in FILTER_MAP]
            search_title = " + ".join(filter_labels)
        else:
            search_title = "All Games"

        context.user_data["search_title"] = search_title

        if results:
            context.user_data["current_results"] = results
            context.user_data["current_page"] = 0
            await show_results_page(update, context)
        else:
            await query.edit_message_text(
                text="No games found matching ALL selected filters.",
                reply_markup=InlineKeyboardMarkup(
                    [[InlineKeyboardButton("🔙 Back to Filters", callback_data="categories")]]
                ),
            )
        return MAIN_MENU

    # ---- Change Profile ----
    if data == "change_profile":
        context.user_data.clear()
        await query.edit_message_text("⚙️ Profile cleared.")
        await query.message.reply_text("Please send your Steam Profile URL.")
        return WAITING_FOR_URL

    # ---- Start AI Chat ----
    if data == "ai_chat":
        context.user_data["ai_mode"] = True
        await query.edit_message_text("🤖 AI chat started. Ask away!")
        return AI_CHAT

    # If we reach here, we expect library data
    if not library_list:
        await query.edit_message_text(
            "⚠️ Library data missing. Please /start again."
        )
        return ConversationHandler.END

    # ---- Filters ----
    results = []
    search_title = "your selection"

    if data == "unplayed":
        results = unplayed_games(library_list, max_minutes=60)
        search_title = "Unplayed Games"

    elif data == "coop":
        results = find_coop(library_list)
        search_title = "Co-op Games"

    elif data == "random":
        if library_list:
            results = [random.choice(library_list)]
            search_title = "Random Pick"

    elif data == "analysis":
        # Enhanced library analysis with detailed metrics
        total_games = len(library_list)
        
        # Pile of Shame: Games with 0 playtime
        unplayed_count = sum(1 for g in library_list if g.get("playtime_forever", 0) == 0)
        played_count = total_games - unplayed_count
        played_percentage = (played_count / total_games * 100) if total_games > 0 else 0
        
        # Time Investment: Total playtime in days
        total_playtime = sum(g.get("playtime_forever", 0) for g in library_list)
        total_hours = total_playtime / 60
        total_days = total_hours / 24
        
        # The Podium: Top 3 most played games
        sorted_games = sorted(
            library_list, 
            key=lambda x: x.get("playtime_forever", 0), 
            reverse=True
        )
        medals = ["🥇", "🥈", "🥉"]
        podium_text = ""
        for i in range(min(3, len(sorted_games))):
            game = sorted_games[i]
            hours = round(game.get("playtime_forever", 0) / 60, 1)
            podium_text += f"{medals[i]} {game['name']} ({hours} hrs)\n"
        
        # Habit Breakdown: Three tiers
        hardcore = sum(1 for g in library_list if g.get("playtime_forever", 0) > 6000)
        regular = sum(1 for g in library_list if 600 <= g.get("playtime_forever", 0) <= 6000)
        casual = sum(1 for g in library_list if g.get("playtime_forever", 0) < 600)
        
        response_text = (
            f"📊 *Library Analysis*\n\n"
            f"*💼 The Collection*\n"
            f"Total Games: {total_games}\n\n"
            f"*🎮 Pile of Shame*\n"
            f"Unplayed: {unplayed_count}\n"
            f"Played: {played_count} ({played_percentage:.1f}%)\n\n"
            f"*⏰ Time Investment*\n"
            f"Total Hours: {total_hours:.1f}\n"
            f"Total Days: {total_days:.1f}\n\n"
            f"*🏆 The Podium*\n"
            f"{podium_text}\n"
            f"*📈 Habit Breakdown*\n"
            f"Hardcore (>100 hrs): {hardcore}\n"
            f"Regular (10-100 hrs): {regular}\n"
            f"Casual (<10 hrs): {casual}"
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
        context.user_data["search_title"] = search_title
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
        entry_points=[CommandHandler("start", start), CommandHandler("help", help)],
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
        fallbacks=[CommandHandler("cancel", cancel), CommandHandler("start", start), CommandHandler("help", help)],
    )


    application.add_handler(conv_handler)

    # Central prompt message used for unknown commands and general guidance
    PROMPT_START_HELP = "Hi! To get started please type /start to provide your Steam profile, or /help to see available commands."

    async def prompt_start_or_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not update.message:
            return
        await update.message.reply_text(PROMPT_START_HELP)

    async def unknown_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Catch-all handler for unknown commands (e.g., /sda)."""
        if not update.message:
            return
        text = (update.message.text or "").strip()
        if not text.startswith("/"):
            return

        cmd = text.split()[0].lstrip('/').lower()

        known_commands = {"start", "help", "cancel"}
        if cmd in known_commands:
            return
        await update.message.reply_text(PROMPT_START_HELP)


    application.add_handler(MessageHandler(filters.COMMAND, unknown_command))

    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, prompt_start_or_help))


    print("Bot running…")
    application.run_polling()


if __name__ == "__main__":
    main()
