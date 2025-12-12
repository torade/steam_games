# Steam Library Assistant Telegram Bot

This project is a Python-based Telegram bot that acts as a personal assistant for your Steam game library. It uses the Steam Web API to fetch your games, enriches the data with details from the Steam Store, and leverages the Google Gemini API for intelligent analysis and recommendations. 

## Features

- **Connect Your Steam Account**: Simply provide your public Steam profile URL to get started.
- **Fetch and Cache Library**: Retrieves your entire game library, including playtime, and caches game details to speed up future requests.
- **AI-Powered Analysis**: Uses Google Gemini to analyze your library and categorize games by playtime, providing smart insights.
- **Advanced Filtering**:
    - Find games playable in under an hour. 
    - Filter for Co-op, Multiplayer, or Single-player titles.
    - Discover games by genre (e.g., RPG, Horror, Relaxing).
- **Game Recommendations**:
    - Get a random game suggestion from your library.
    - View a short analysis of your library, including total playtime and your most-played game.
- **Interactive UI**: A clean, menu-driven interface using Telegram's inline keyboards.
- **Profile Management**: Easily switch between different Steam profiles.

## How It Works

- **Bot Framework**: The bot is built using the `python-telegram-bot` library, managing user states and interactions through a `ConversationHandler`.
- **Steam Integration**: The [`steam.py`](steam.py) module handles all communication with the Steam Web API. It resolves vanity URLs, fetches owned games, and retrieves detailed game information like genres and categories.
- **AI Enrichment**: [`gemini_chat.py`](gemini_chat.py) integrates with the Google Gemini API. It takes the user's library, sends it to the AI for analysis, and adds time-based categories to each game. This process runs asynchronously to avoid blocking the bot.
- **Recommender Logic**: The [`recommender.py`](recommender.py) module contains various filter functions that power the bot's search capabilities.

## Setup and Installation

1.  **Clone the Repository**
    ```sh
    git clone <your-repository-url>
    cd steam_games
    ```

2.  **Install Dependencies**
    It's recommended to use a virtual environment.
    ```sh
    python -m venv venv
    source venv/bin/activate  # On Windows, use `venv\Scripts\activate`
    ```
    Create a `requirements.txt` file with the following content:
    ```txt
    python-telegram-bot
    requests
    google-generativeai
    ```
    Then install the packages:
    ```sh
    pip install -r requirements.txt
    ```

3.  **Configure API Keys**
    Create a file named `API_keys.py` in the root directory and add your keys:
    ```python
    # filepath: API_keys.py
    # Get from BotFather on Telegram
    TELEGRAM_TOKEN = "YOUR_TELEGRAM_BOT_TOKEN"

    # Get from https://steamcommunity.com/dev/apikey
    STEAM_API_KEY = "YOUR_STEAM_WEB_API_KEY"

    # Get from https://aistudio.google.com/app/apikey
    GEMINI_API_KEY = "YOUR_GEMINI_API_KEY"
    ```
    **Important**: Add `API_keys.py` to your `.gitignore` file to keep your keys private.

4.  **Run the Bot**
    Execute the `bot.py` script to start the bot.
    ```sh
    python bot.py
    ```

## Usage

1.  Find your bot on Telegram and send the `/start` command.
2.  The bot will ask for your Steam Profile URL. Send a valid, public profile URL.
3.  The bot will fetch your library, and the AI will perform its analysis.
4.  Once loaded, you can use the inline keyboard buttons to explore your library, get recommendations, and view analysis.
