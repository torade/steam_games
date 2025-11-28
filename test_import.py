"""
Test file to verify Google Generative AI import works correctly
"""

try:
    import google.generativeai as genai
    print("✓ Import successful!")
    print(f"✓ Package version: {genai.__version__}")
    print("✓ google.generativeai is installed correctly")
except ImportError as e:
    print(f"✗ Import failed: {e}")
    print("Try: python -m pip install google-generativeai")