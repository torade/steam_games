"""
Game recommendation functions that filter library based on tags, categories, and genres.
"""


def check_tags(game, required_tags):
    """
    Check if game has at least one of the required tags.
    Case-insensitive comparison.
    
    Args:
        game: Game dictionary with 'tags' key
        required_tags: List of tag names to check for
    
    Returns:
        bool: True if game has any of the required tags
    """
    game_tags = game.get("tags", {})
    if not game_tags:
        return False
    
    # Handle both dict format {tag: count} and ensure we get keys
    if isinstance(game_tags, dict):
        game_tags_lower = {tag.lower() for tag in game_tags.keys()}
    else:
        return False
    
    required_tags_lower = {tag.lower() for tag in required_tags}
    
    return bool(game_tags_lower & required_tags_lower)


def check_categories(game, required_categories):
    """
    Check if game has at least one of the required categories.
    Case-insensitive comparison.
    
    Args:
        game: Game dictionary with 'categories' key
        required_categories: List of category descriptions to check for
    
    Returns:
        bool: True if game has any of the required categories
    """
    categories = game.get("categories", [])
    if not categories:
        return False
    
    category_descriptions = {cat.get("description", "").lower() for cat in categories}
    required_lower = {cat.lower() for cat in required_categories}
    
    return bool(category_descriptions & required_lower)


def check_genres(game, required_genres):
    """
    Check if game has at least one of the required genres.
    Case-insensitive comparison.
    
    Args:
        game: Game dictionary with 'genres' key
        required_genres: List of genre descriptions to check for
    
    Returns:
        bool: True if game has any of the required genres
    """
    genres = game.get("genres", [])
    if not genres:
        return False
    
    genre_descriptions = {g.get("description", "").lower() for g in genres}
    required_lower = {g.lower() for g in required_genres}
    
    return bool(genre_descriptions & required_lower)


def find_coop(library_list):
    """
    Find co-op games using both tags and categories.
    
    Args:
        library_list: List of game dictionaries
    
    Returns:
        list: Filtered list of co-op games
    """
    coop_tags = ["Co-op", "Online Co-Op", "Local Co-Op", "Multiplayer", 
                 "Co-op Campaign", "Split Screen"]
    coop_categories = ["Co-op", "Online Co-op", "Local Co-op", 
                       "Shared/Split Screen Co-op"]
    
    results = []
    for game in library_list:
        if check_tags(game, coop_tags) or check_categories(game, coop_categories):
            results.append(game)
    
    return results


def find_cute_relaxing(library_list):
    """
    Find cute and relaxing games.
    
    Args:
        library_list: List of game dictionaries
    
    Returns:
        list: Filtered list of cute/relaxing games
    """
    relaxing_tags = ["Relaxing", "Cute", "Cozy", "Casual", "Wholesome", 
                     "Family Friendly", "Peaceful", "Chill"]
    
    results = []
    for game in library_list:
        if check_tags(game, relaxing_tags):
            results.append(game)
    
    return results


def find_fps(library_list):
    """
    Find first-person shooter games.
    
    Args:
        library_list: List of game dictionaries
    
    Returns:
        list: Filtered list of FPS games
    """
    fps_tags = ["FPS", "First-Person", "Shooter", "First-Person Shooter"]
    
    results = []
    for game in library_list:
        if check_tags(game, fps_tags):
            results.append(game)
    
    return results


def find_by_genre(library_list, genre_name):
    """
    Find games by specific genre.
    
    Args:
        library_list: List of game dictionaries
        genre_name: Genre to search for (e.g., "Action", "RPG", "Strategy")
    
    Returns:
        list: Filtered list of games matching the genre
    """
    results = []
    for game in library_list:
        if check_genres(game, [genre_name]):
            results.append(game)
    
    return results


def find_by_tag(library_list, tag_name):
    """
    Find games by specific tag.
    
    Args:
        library_list: List of game dictionaries
        tag_name: Tag to search for (e.g., "Horror", "Puzzle", "Open World")
    
    Returns:
        list: Filtered list of games matching the tag
    """
    results = []
    for game in library_list:
        if check_tags(game, [tag_name]):
            results.append(game)
    
    return results


def find_unplayed(library_list, max_minutes=60):
    """
    Find games with minimal playtime (unplayed or barely played).
    
    Args:
        library_list: List of game dictionaries
        max_minutes: Maximum playtime in minutes (default: 60)
    
    Returns:
        list: Filtered list of unplayed games
    """
    return [
        game for game in library_list
        if game.get("playtime_forever", 0) <= max_minutes
    ]


def find_most_played(library_list, limit=10):
    """
    Find most played games in library.
    
    Args:
        library_list: List of game dictionaries
        limit: Number of games to return (default: 10)
    
    Returns:
        list: Sorted list of most played games
    """
    sorted_games = sorted(
        library_list,
        key=lambda x: x.get("playtime_forever", 0),
        reverse=True
    )
    return sorted_games[:limit]


def find_by_multiple_tags(library_list, tags, match_all=False):
    """
    Find games matching multiple tags.
    
    Args:
        library_list: List of game dictionaries
        tags: List of tags to search for
        match_all: If True, game must have ALL tags (AND logic).
                   If False, game needs at least one tag (OR logic).
    
    Returns:
        list: Filtered list of games
    """
    if match_all:
        # Game must have ALL tags
        results = []
        for game in library_list:
            game_tags_lower = {tag.lower() for tag in game.get("tags", {}).keys()}
            required_tags_lower = {tag.lower() for tag in tags}
            
            if required_tags_lower.issubset(game_tags_lower):
                results.append(game)
        return results
    else:
        # Game needs at least one tag (OR logic)
        return [game for game in library_list if check_tags(game, tags)]


def find_short_games(library_list):
    """
    Find short games using 'Save Anytime' category and 'short' tag.
    
    Args:
        library_list: List of game dictionaries
    
    Returns:
        list: Filtered list of short games
    """
    short_tags = ["Short", "Quick"]
    short_categories = ["Save Anytime"]
    
    results = []
    for game in library_list:
        if check_tags(game, short_tags) or check_categories(game, short_categories):
            results.append(game)
    
    return results
