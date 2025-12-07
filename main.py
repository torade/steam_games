import re
import time
import json
import os
from steam import resolve_vanity_url, get_owned_games, get_game_details, CACHE_FILE
from recommender import find_coop, find_cute_relaxing, find_by_genre


def find_common_games(steam_id_list, library_data=None, filter_func=None):
    """
    Fetches owned games for all provided Steam IDs and returns games owned by everyone.
    
    Args:
        steam_id_list (list): List of SteamID strings.
        library_data (dict): Optional local cache of game details to enrich results.
        filter_func (function): Optional function to filter the resulting list (e.g., find_coop).
    """
    if not steam_id_list:
        return []

    print(f"Finding common games for {len(steam_id_list)} users...")
    
    # Sets to store appids for intersection
    common_appids = None
    
    # Dictionary to store basic game info (name) from the API responses
    game_info_map = {}

    for steam_id in steam_id_list:
        print(f"Fetching games for SteamID: {steam_id}")
        games = get_owned_games(steam_id)
        
        if games is None:
            print(f"Could not fetch games for {steam_id}. Skipping intersection for this user (or aborting).")
            return []
            
        current_appids = set()
        for g in games:
            appid = str(g['appid'])
            current_appids.add(appid)
            # Keep track of names
            if appid not in game_info_map:
                game_info_map[appid] = g['name']
        
        if common_appids is None:
            common_appids = current_appids
        else:
            common_appids = common_appids.intersection(current_appids)
            
    if not common_appids:
        print("No common games found.")
        return []

    print(f"Found {len(common_appids)} common AppIDs.")

    # Construct the result list. 
    # If we have library_data (cache), we use it to get full details (categories, genres).
    # Otherwise, we just return the basic name from the ownership check.
    result_games = []
    
    for appid in common_appids:
        if library_data and appid in library_data:
            result_games.append(library_data[appid])
        else:
            # Fallback to basic info if not in cache
            result_games.append({'appid': appid, 'name': game_info_map.get(appid, "Unknown")})

    # Apply optional filter
    if filter_func:
        print("Applying filter...")
        # Note: Filters in recommender.py expect a list of game dicts with 'categories'/'genres'
        # If the game isn't in library_data, filters might fail or return nothing.
        result_games = filter_func(result_games)

    return result_games

def steam_api_caller(steam_id):
    print(f"Resolved SteamID: {steam_id}")
    
    # Get owned games
    owned_games = get_owned_games(steam_id)
    if owned_games is None:
        return {}

    print(f"\nFound {len(owned_games)} games.")
    
    games_data = {}
    
    print("\nPopulating game details cache (this may take a while)...")
    # Loop through all games to populate cache
    for game in owned_games:
        appid = str(game['appid'])
        name = game['name']
        
        details = get_game_details(int(appid))
        
        if details:
            # Store relevant details
            games_data[appid] = {
                "name": name,
                "categories": details.get('categories', []),
                "genres": details.get('genres', [])
            }
            genres = [g['description'] for g in details.get('genres', [])]
            print(f"Processed {name}: Found {len(genres)} genres.")
        else:
            print(f"Could not get details for {name}")
        
        # Sleep briefly to be polite to the API (avoid Rate Limiting)
        time.sleep(0.1)
        
    return games_data

def main():
    # Example usage with a profile URL.
    profile_url = "https://steamcommunity.com/id/sadade00/" # replace this with any valid steam profile
    
    library_data = {}
    steam_id = None  # Initialize steam_id here

    # Resolve SteamID first so it's available for common games check later
    print(f"Attempting to process profile URL: {profile_url}")
    # Try to extract vanity name or profile ID from URL
    vanity_match = re.search(r"steamcommunity.com/id/([^/]+)", profile_url)
    profile_match = re.search(r"steamcommunity.com/profiles/(\d+)", profile_url)

    if vanity_match:
        vanity_name = vanity_match.group(1)
        print(f"Found vanity name: {vanity_name}")
        steam_id = resolve_vanity_url(vanity_name)
    elif profile_match:
        steam_id = profile_match.group(1)
        print(f"Found SteamID: {steam_id}")
    else:
        print("Could not parse SteamID or vanity name from URL.")
    
    # Ask user if they want to update the library
    response = input("Do you want to update library? (yes/no): ").strip().lower()
    update_library = response == 'yes'

    # Check if cache exists and is not empty
    if os.path.exists(CACHE_FILE) and os.path.getsize(CACHE_FILE) > 0 and not update_library:
        print("Loading games from cache...")
        try:
            with open(CACHE_FILE, 'r') as f:
                library_data = json.load(f)
        except json.JSONDecodeError:
            print("Error reading cache file.")
            library_data = {}

    # If no cache or update requested, fetch from API
    if not library_data:
        if steam_id:
            library_data = steam_api_caller(steam_id)
            # Save to cache
            with open(CACHE_FILE, 'w') as f:
                json.dump(library_data, f, indent=4)
    
    if library_data:
        print(f"\nLibrary contains {len(library_data)} games.")
        print("Here are some of your games:")
        # Sort by name
        sorted_games = sorted(library_data.values(), key=lambda x: x['name'])
        for game in sorted_games[:15]:
            print(f"- {game['name']}")

        # --- Recommender Demonstrations ---
        print("\n--- Recommender Demonstrations ---")
        
        # Convert dictionary values to a list for the recommender functions
        games_list = list(library_data.values())



        # --- NEW: Gemini Chat Option ---
        print("\n" + "="*60)
        gemini_response = input("Would you like to chat with Gemini about your library? (yes/no): ").strip().lower()
        if gemini_response == 'yes':
            try:
                from gemini_chat import chat_with_gemini
                chat_with_gemini(library_data)
            except ImportError:
                print("Gemini chat module not found. Make sure gemini_chat.py is in the same directory.")
            except Exception as e:
                print(f"Error starting Gemini chat: {e}")

if __name__ == "__main__":
    main()
