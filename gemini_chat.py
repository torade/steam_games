import json
import google.generativeai as genai
from config_gemini import GEMINI_API_KEY, SYSTEM_PROMPT

# Configure Gemini
genai.configure(api_key=GEMINI_API_KEY)

def load_library_data(cache_file="game_cache.json"):
    """Load the Steam library data from cache"""
    try:
        with open(cache_file, 'r') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}

def format_library_context(library_data):
    """Format library data into a context string for Gemini"""
    if not library_data:
        return "No Steam library data available."
    
    # Create a summary
    games_list = []
    for appid, game_info in library_data.items():
        name = game_info.get('name', 'Unknown')
        genres = [g.get('description', '') for g in game_info.get('genres', [])]
        categories = [c.get('description', '') for c in game_info.get('categories', [])]
        
        games_list.append({
            'name': name,
            'genres': genres,
            'categories': categories
        })
    
    context = f"Steam Library Summary:\n"
    context += f"Total games: {len(games_list)}\n\n"
    context += "Games in library:\n"
    
    for game in sorted(games_list, key=lambda x: x['name']):
        context += f"- {game['name']}\n"
        if game['genres']:
            context += f"  Genres: {', '.join(game['genres'])}\n"
        if game['categories']:
            context += f"  Categories: {', '.join(game['categories'])}\n"
    
    return context

def chat_with_gemini(library_data):
    """Start an interactive chat session with Gemini about the Steam library"""
    
    # Prepare the context
    library_context = format_library_context(library_data)
    
    # Initialize the model
    model = genai.GenerativeModel('gemini-2.5-flash')
    
    # Start chat with context
    full_prompt = f"{SYSTEM_PROMPT}\n\n{library_context}"
    
    chat = model.start_chat(history=[])
    
    print("\n" + "="*60)
    print("Gemini Chat - Steam Library Assistant")
    print("="*60)
    print("Type 'exit' or 'quit' to end the conversation\n")
    
    # Send initial context as a system message
    response = chat.send_message(full_prompt)
    print(f"Assistant: {response.text}\n")
    
    # Main chat loop
    while True:
        try:
            user_input = input("You: ").strip()
            
            if user_input.lower() in ['exit', 'quit', 'bye']:
                print("\nGoodbye! Happy gaming!")
                break
            
            if not user_input:
                continue
            
            # Send message and get response
            response = chat.send_message(user_input)
            print(f"\nAssistant: {response.text}\n")
            
        except KeyboardInterrupt:
            print("\n\nGoodbye! Happy gaming!")
            break
        except Exception as e:
            print(f"\nError: {e}")
            print("Please try again.\n")

if __name__ == "__main__":
    # Load library data
    library_data = load_library_data()
    
    if not library_data:
        print("No Steam library data found. Please run the main script first to populate the cache.")
    else:
        print(f"Loaded {len(library_data)} games from your Steam library.")
        chat_with_gemini(library_data)