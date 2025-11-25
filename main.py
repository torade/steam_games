import re
from steam import resolve_vanity_url, get_owned_games

def main():
    # Example usage with a profile URL.
    profile_url = "https://steamcommunity.com/id/sadade00/" # replace this with any valid steam profile
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
        print(f"Resolved SteamID: {steam_id}")
        
        # Get owned games
        owned_games = get_owned_games(steam_id)
        if owned_games is not None:
            print(f"\nFound {len(owned_games)} games.")
            print("Here are some of your games (sorted alphabetically):")
            # Print the first 15 games as an example
            for game in sorted(owned_games, key=lambda x: x['name'])[:15]:
                playtime_hours = game.get('playtime_forever', 0) / 60
                print(f"- {game['name']} (Playtime: {playtime_hours:.2f} hours)")
        else:
            print("Could not fetch owned games. The user's profile might be private.")

if __name__ == "__main__":
    main()
