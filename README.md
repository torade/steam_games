# Steam Library Assistant Telegram Bot

This Telegram Bot acts as an assistant who recommends video games to you, based on your Steam library.<img src="https://github.com/user-attachments/assets/412bb763-96e2-4e35-a697-914ee28a8200" width="88">



## Features

- **Connect Your Steam Account**: Simply provide your public Steam profile URL to get started.
- **Fetch and Cache Library**: Retrieves your entire game library, including playtime, and caches game details to speed up future requests.
- **AI-Powered Suggestions**: The bot has an option for chatting with AI, where it can give suggestions both based on owned and unowned games. It can understand more complex filters than the ones integrated into the "Categories" section and give more accurate recommendations (based on preference description).
- **Filters and options**:
    - Find unplayed games (less than 1 hour playtime)
    - Find short games: games where progress can be saved at any time
    - Randomly pick a game from the library
    - Smart Analysis: provide insight into the user's playing trends
    - AI Chat: use natural language to discuss about games and preferences
    - Categories: multi/single filtering options for game genres/categories/tags
    <table>
  <tr>
    <td valign="top">
      <ul>
        <li>Shooter</li>
        <li>RPG</li>
        <li>Strategy</li>
        <li>Story Rich</li>
        <li>Co-Op</li>
        <li>Horror</li>
      </ul>
    </td>
    <td valign="top">
      <ul>
        <li>Chill/Relaxing</li>
        <li>Action</li>
        <li>Open World</li>
        <li>Comedy</li>
        <li>Sci-Fi</li>
        <li>Fantasy</li>
      </ul>
    </td>
  </tr>
</table>

- **Interactive UI**: A clean, menu-driven interface using Telegram's inline keyboards.
- **Profile Management**: Easily switch between different Steam profiles.

## How It Works

- **Bot Framework**: The bot is built using the `python-telegram-bot` library, managing user states and interactions through a `ConversationHandler`.
- **Steam Integration**: The [`steam.py`](steam.py) module handles all communication with the Steam Web API. It resolves vanity URLs, fetches owned games, and retrieves detailed game information like genres and categories.
- **AI Enrichment**: [`gemini_chat.py`](gemini_chat.py) integrates with the Google Gemini API. It takes the user's library, sends it to the AI for analysis. This process runs asynchronously to avoid blocking the bot.
- **Recommender Logic**: The [`recommender.py`](recommender.py) module contains the various filter functions used to suggest games.

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
    # Get from BotFather on Telegram
    TELEGRAM_TOKEN = "YOUR_TELEGRAM_BOT_TOKEN"

    # Get from https://steamcommunity.com/dev/apikey
    STEAM_API_KEY = "YOUR_STEAM_WEB_API_KEY"

    # Get from https://aistudio.google.com/app/apikey
    GEMINI_API_KEY = "YOUR_GEMINI_API_KEY"
    ```

4.  **Run the Bot**
    Execute the `bot.py` script to start the bot.
    ```sh
    python bot.py
    ```

5.  **Extra**
    For development:
    - Add `API_keys.py` to your `.gitignore` file to keep your keys private.
    - The bot saves `game_cache.json` and `gemini_history.json` files locally. It is recommended to also add those to `.gitignore`

## Usage

1.  Find your bot on Telegram and send the `/start` command.
2.  The bot will ask for your Steam Profile URL. Send a valid, public profile URL.
3.  The bot will fetch your library, and the AI will perform its analysis.
4.  Once loaded, you can use the inline keyboard buttons to explore your library, get recommendations, and view analysis.
