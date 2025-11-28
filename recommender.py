def find_coop(library_data, min_players=1):
    """Filters for games with the 'Co-op' category."""
    results = []
    for game in library_data:
        categories = game.get('categories', [])
        if any(cat.get('description') == 'Co-op' for cat in categories):
            results.append(game)
    return results

def find_cute_relaxing(library_data):
    """Filters for games that have tags or genres like 'Casual', 'Simulation', 'Cute', or 'Relaxing'."""
    keywords = {'Casual', 'Simulation', 'Cute', 'Relaxing'}
    results = []
    for game in library_data:
        genres = game.get('genres', [])
        game_genres = {g.get('description') for g in genres}
        if not game_genres.isdisjoint(keywords):
            results.append(game)
    return results

def find_by_genre(library_data, genre_name):
    """Returns games matching a specific genre string (e.g., 'Horror')."""
    results = []
    for game in library_data:
        genres = game.get('genres', [])
        if any(genre_name.lower() in g.get('description', '').lower() for g in genres):
            results.append(game)
    return results
