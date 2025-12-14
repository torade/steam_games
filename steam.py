import requests
import json
import os
from API_keys import STEAM_API_KEY

CACHE_FILE = "game_cache.json"
STEAMSPY_APPDETAILS_URL = "https://steamspy.com/api.php"  # added

def fetch_game_tags(appid):
    """Fetch top tags for an appid using SteamSpy."""
    params = {"request": "appdetails", "appid": appid}
    try:
        resp = requests.get(STEAMSPY_APPDETAILS_URL, params=params, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        return data.get("tags", {}) if isinstance(data, dict) else {}
    except requests.RequestException as e:
        print(f"Error fetching tags for appid {appid}: {e}")
        return {}

def resolve_vanity_url(vanity_url):
    """
    Resolves a Steam vanity URL to a 64-bit Steam ID.
    :param vanity_url: The custom profile name.
    :return: The 64-bit Steam ID as a string, or None if not found.
    """
    url = "https://api.steampowered.com/ISteamUser/ResolveVanityURL/v1/"
    params = {
        "key": STEAM_API_KEY,
        "vanityurl": vanity_url
    }
    try:
        response = requests.get(url, params=params)
        response.raise_for_status()
        data = response.json()
        if data.get("response", {}).get("success") == 1:
            return data["response"]["steamid"] # Return the resolved SteamID
        else:
            print(f"Could not resolve vanity URL '{vanity_url}'. Response: {data}")
            return None
    except requests.exceptions.RequestException as e:
        print(f"An error occurred while resolving vanity URL: {e}")
        return None

def get_owned_games(steam_id):
    """
    Fetches a user's owned games from the Steam Web API.
    :param steam_id: The 64-bit Steam ID of the user.
    :return: A list of owned games, or None if an error occurs.
    """
    url = "https://api.steampowered.com/IPlayerService/GetOwnedGames/v1/"
    params = {
        "key": STEAM_API_KEY,
        "steamid": steam_id,
        "include_appinfo": 1, # true
        "include_played_free_games": 1, # true
        "format": "json"
    }
    try:
        response = requests.get(url, params=params)
        response.raise_for_status()
        data = response.json()
        return data.get("response", {}).get("games", [])
    except requests.exceptions.RequestException as e:
        print(f"An error occurred while fetching owned games: {e}")
        return None

def get_game_details(appid):  # steam store API is public => no key needed BUT multiple requests might get blocked => use caching
    """
    Fetches details for a specific game from the Steam Store API or local cache.
    :param appid: The Steam Application ID.
    :return: A dictionary of game details (categories, genres), or None.
    """
    # 1. Try loading existing cache
    cache = {}
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE, "r", encoding="utf-8") as f:
                cache = json.load(f)
        except (json.JSONDecodeError, IOError):
            cache = {}

    appid_str = str(appid)
    
    # 2. Check if game is in cache
    if appid_str in cache:
        return cache[appid_str]

    # 3. If not in cache, fetch from API
    url = "https://store.steampowered.com/api/appdetails"
    params = {"appids": appid}
    
    try:
        response = requests.get(url, params=params)
        if response.status_code == 200:
            data = response.json()
            # API structure: { "appid": { "success": true, "data": {...} } }
            if data and appid_str in data:
                app_data = data[appid_str]
                if app_data.get("success"):
                    game_data = app_data.get("data", {})
                    
                    tags = fetch_game_tags(appid)  # added
                    
                    # Extract relevant fields
                    details = {
                        "name": game_data.get("name"),
                        "categories": game_data.get("categories", []),
                        "genres": game_data.get("genres", []),
                        "desc": game_data.get("short_description", ""),
                        "header_image": game_data.get("header_image"),
                        "tags": tags  # added
                    }
                    
                    # 4. Save to cache
                    cache[appid_str] = details
                    with open(CACHE_FILE, "w", encoding="utf-8") as f:
                        json.dump(cache, f, indent=4)
                        
                    return details
    except requests.RequestException as e:
        print(f"Error fetching details for appid {appid}: {e}")

    return None
