# vision.py

import base64
import requests
import json
# REMOVED: from config import OPENAI_API_KEY  <-- DELETE THIS LINE

def encode_image(image_path):
    """
    Converts a local image file to a Base64 string for API calls. (No change)
    """
    try:
        with open(image_path, "rb") as image_file:
            return base64.b64encode(image_file.read()).decode('utf-8')
    except FileNotFoundError:
        print(f"Error: The image file was not found at {image_path}")
        return None
    except Exception as e:
        print(f"An error occurred while encoding the image: {e}")
        return None

# MODIFIED: Accepts the key as an argument
def analyze_meal_photo(image_path, user_goal, openai_api_key):
    """
    Analyzes a meal photo using OpenAI's Vision API.
    """
    base64_image = encode_image(image_path)
    if not base64_image:
        return "Error: Could not process image."

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {openai_api_key}" # Use the argument here
    }
    
    # ... (rest of the payload and API call remains the same) ...