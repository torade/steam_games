import re
import time
import json
import os
from steam import resolve_vanity_url, get_owned_games, get_game_details, save_cache
from recommender import find_coop, find_cute_relaxing, find_by_genre

CACHE_DIR = "users_cache"

def get_user_data(profile_url, update_prompt=True, custom_cache_name=None, force_update=False):
    """
    Helper function to resolve SteamID, handle caching, and fetch data for a user.
    Returns tuple: (steam_id, library_data, vanity_name_or_id)
    """
    print(f"Attempting to process profile URL: {profile_url}")
    vanity_match = re.search(r"steamcommunity.com/id/([^/]+)", profile_url)
    profile_match = re.search(r"steamcommunity.com/profiles/(\d+)", profile_url)

    steam_id = None
    identifier = None
    cache_filename = None

    if vanity_match:
        identifier = vanity_match.group(1)
        print(f"Found vanity name: {identifier}")
        steam_id = resolve_vanity_url(identifier)
    elif profile_match:
        identifier = profile_match.group(1)
        steam_id = identifier
        print(f"Found SteamID: {steam_id}")
    else:
        print("Could not parse SteamID or vanity name from URL.")
        return None, {}, None

    if custom_cache_name:
        cache_filename = os.path.join(CACHE_DIR, custom_cache_name)
    else:
        cache_filename = os.path.join(CACHE_DIR, f"games_{identifier}.json")

    if not steam_id:
        print("Could not resolve SteamID.")
        return None, {}, None

    library_data = {}
    update_library = False
    
    if force_update:
        update_library = True
    elif update_prompt:
        response = input(f"Do you want to update library for {os.path.basename(cache_filename)}? (yes/no): ").strip().lower()
        update_library = response == 'yes'
    else:
        response = input(f"Do you want to update library for friend ({identifier})? (yes/no): ").strip().lower()
        update_library = response == 'yes'

    # Check cache
    if os.path.exists(cache_filename) and os.path.getsize(cache_filename) > 0 and not update_library:
        print(f"Loading games from cache ({cache_filename})...")
        try:
            with open(cache_filename, 'r') as f:
                library_data = json.load(f)
        except json.JSONDecodeError:
            print("Error reading cache file.")
            library_data = {}

    # Fetch from API if needed
    if not library_data:
        library_data = steam_api_caller(steam_id)
        # Save to cache
        with open(cache_filename, 'w') as f:
            json.dump(library_data, f, indent=4)
            print(f"Saved data to {cache_filename}")

    return steam_id, library_data, identifier

def find_common_games(libraries, filter_func=None):
    """
    Finds games present in all provided library dictionaries.
    
    Args:
        libraries (list): List of dictionaries where keys are AppIDs and values are game details.
        filter_func (function): Optional function to filter the resulting list.
    """
    if not libraries:
        return []

    print(f"Finding common games across {len(libraries)} libraries...")
    
    # Start with the keys (AppIDs) from the first library (usually main user)
    common_appids = set(libraries[0].keys())
    
    # Intersect with keys from all other libraries
    for lib in libraries[1:]:
        common_appids.intersection_update(lib.keys())
            
    if not common_appids:
        print("No common games found.")
        return []

    print(f"Found {len(common_appids)} common AppIDs.")

    # Construct the result list using details from the first library
    # (Assuming the first library is the main user and has full details)
    result_games = []
    main_lib = libraries[0]
    
    for appid in common_appids:
        if appid in main_lib:
            result_games.append(main_lib[appid])
        else:
            # Fallback if for some reason it's in keys but not accessible (unlikely)
            result_games.append({'name': f"AppID {appid}", 'categories': [], 'genres': []})

    # Apply optional filter
    if filter_func:
        print("Applying filter...")
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
    
    # Save the global game details cache
    save_cache()
        
    return games_data

def find_multiplayer_coop(games):
    """
    Filters list of games for those with Multi-player or Co-op categories.
    """
    result = []
    for game in games:
        categories = [c.get('description') for c in game.get('categories', [])]
        if "Multi-player" in categories or "Co-op" in categories or "Online Co-op" in categories:
            result.append(game)
    return result

def main():
    # Ensure cache directory exists
    if not os.path.exists(CACHE_DIR):
        os.makedirs(CACHE_DIR)
        print(f"Created cache directory: {CACHE_DIR}")

    # 1. Process Main User
    main_cache_path = os.path.join(CACHE_DIR, "main_user.json")
    main_library_data = {}
    main_steam_id = None

    if os.path.exists(main_cache_path):
        print("Found existing main user cache.")
        if input("Do you want to update it? (yes/no): ").strip().lower() == 'yes':
            profile_url = input("Please enter your Steam profile URL: ").strip()
            main_steam_id, main_library_data, main_identifier = get_user_data(profile_url, custom_cache_name="main_user.json", force_update=True)
        else:
            print(f"Loading games from cache ({main_cache_path})...")
            try:
                with open(main_cache_path, 'r') as f:
                    main_library_data = json.load(f)
                main_steam_id = "CachedUser" # Placeholder since we loaded from cache
            except json.JSONDecodeError:
                print("Error reading cache file.")
    else:
        profile_url = input("Please enter your Steam profile URL: ").strip()
        main_steam_id, main_library_data, main_identifier = get_user_data(profile_url, custom_cache_name="main_user.json")
    
    if not main_steam_id:
        return

    if main_library_data:
        print(f"\nLibrary contains {len(main_library_data)} games.")
        print("Here are some of your games:")
        sorted_games = sorted(main_library_data.values(), key=lambda x: x['name'])
        for game in sorted_games[:15]:
            print(f"- {game['name']}")

        # --- Recommender Demonstrations ---
        print("\n--- Recommender Demonstrations ---")
        games_list = list(main_library_data.values())

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

        # 3. Genre Search
        search_genre = "Action"
        action_games = find_by_genre(games_list, search_genre)
        print(f"\nFound {len(action_games)} games with genre '{search_genre}':")
        for game in action_games[:5]:
            print(f"- {game['name']}")

    # 2. Add Friends Logic
    friend_libraries = []
    
    while True:
        add_friend = input("\nDo you want to add a friend to compare games with? (yes/no): ").strip().lower()
        if add_friend != 'yes':
            break
            
        friend_url = input("Enter friend's Steam profile URL: ").strip()
        f_steam_id, f_library, f_ident = get_user_data(friend_url)
        
        if f_steam_id and f_library:
            friend_libraries.append(f_library)
            print(f"Added friend: {f_ident} ({f_steam_id})")
        else:
            print("Failed to add friend or fetch their library.")

    # 3. Common Games Feature
    if friend_libraries:
        check_common = input("\nDo you want to check common games with your added friends? (yes/no): ").strip().lower()
        if check_common == 'yes':
            print("\n--- Common Games Feature ---")
            
            # Combine main user library and friend libraries
            all_libraries = [main_library_data] + friend_libraries
            
            # Find common games using the cached data
            common = find_common_games(all_libraries)
            print(f"Common games count: {len(common)}")
            
            # Bonus: Filter for Multiplayer/Co-op among common games
            print("Filtering for common Multiplayer & Co-op games...")
            common_multi = find_common_games(all_libraries, filter_func=find_multiplayer_coop)
            print(f"Found {len(common_multi)} common Multiplayer & Co-op games:")
            for game in common_multi[:5]:
                print(f"- {game['name']}")

if __name__ == "__main__":
    main()
