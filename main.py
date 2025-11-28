import re
import time
import json
import os
from steam import resolve_vanity_url, get_owned_games, get_game_details
from recommender import find_coop, find_cute_relaxing, find_by_genre

CACHE_FILE = "game_cache.json"

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
        print(f"Attempting to process profile URL: {profile_url}")
        steam_id = None
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

        # 1. Co-op
        coop_games = find_coop(games_list)
        print(f"\nFound {len(coop_games)} Co-op games:")
        for game in coop_games[:5]:
            print(f"- {game['name']}")

        # 2. Cute/Relaxing
        cute_games = find_cute_relaxing(games_list)
        print(f"\nFound {len(cute_games)} Cute/Relaxing games:")
        for game in cute_games[:5]:
            print(f"- {game['name']}")

        # 3. Genre Search (e.g., Action)
        search_genre = "Action"
        action_games = find_by_genre(games_list, search_genre)
        print(f"\nFound {len(action_games)} games with genre '{search_genre}':")
        for game in action_games[:5]:
            print(f"- {game['name']}")

if __name__ == "__main__":
    main()
