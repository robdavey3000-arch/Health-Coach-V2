# vision.py

import base64
import requests
import json

# NOTE: Removed 'from config import OPENAI_API_KEY' for security and modularity.

def encode_image(image_path):
    """
    Converts a local image file to a Base64 string for API calls.
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

# CRITICAL UPDATE: Added openai_api_key parameter to the function signature
def analyze_meal_photo(image_path, user_goal, openai_api_key):
    """
    Analyzes a meal photo using OpenAI's Vision API.
    The key is now passed explicitly for better security and structure.
    """
    base64_image = encode_image(image_path)
    if not base64_image:
        return "Error: Could not process image."

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {openai_api_key}" # Use the passed key
    }

    payload = {
        "model": "gpt-4o",
        "messages": [
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": f"This is a photo of my meal. My diet plan is: {user_goal}. Please analyze the meal and tell me if it aligns with my plan. Identify the food items and provide specific feedback and suggestions for improvement."
                    },
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/jpeg;base64,{base64_image}"
                        }
                    }
                ]
            }
        ],
        "max_tokens": 500
    }

    try:
        print("Sending photo to AI for analysis...")
        response = requests.post("https://api.openai.com/v1/chat/completions", headers=headers, json=payload)
        response.raise_for_status()  # This will raise an HTTPError for bad responses (4xx or 5xx)
        
        return response.json()["choices"][0]["message"]["content"]
    
    except requests.exceptions.HTTPError as http_err:
        print(f"HTTP error occurred: {http_err} - {response.text}")
        return "Error analyzing meal. Check your API key or permissions."
    except Exception as e:
        print(f"An error occurred: {e}")
        return "An unknown error occurred during analysis."

# We will test this function later in the main.py file.
