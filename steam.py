import requests
import json

# Your Steam Web API Key
STEAM_API_KEY = "7D3524268C7892917F37673A0DB6489F"

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
            return data["response"]["steamid"]
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
        "include_appinfo": 1,  # To get game names
        "include_played_free_games": 1,
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
