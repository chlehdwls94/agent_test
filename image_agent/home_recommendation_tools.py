import os
import json
from dotenv import load_dotenv
from google.adk.tools import ToolContext
from google import genai
from google.genai import types
import logging

logger = logging.getLogger(__name__)

load_dotenv()
PROJECT_ID = os.getenv("GOOGLE_CLOUD_PROJECT")

if not PROJECT_ID:
    logger.error("GOOGLE_CLOUD_PROJECT is not set")

genai.configure(project=PROJECT_ID, location="us-central1")

def ImageAnalyzer(file_path: str) -> str:
    """
    Analyzes an image of a room and returns a detailed description of its characteristics.

    Args:
        file_path (str): The path to the image file.

    Returns:
        str: A detailed description of the room including style, lighting, colors, and existing furniture.
    """
    model = genai.GenerativeModel("gemini-1.5-flash")
    with open(file_path, "rb") as f:
        image_bytes = f.read()
    image = types.Part.from_data(data=image_bytes, mime_type="image/png")
    response = model.generate_content(["Describe the room's style, lighting conditions, main colors, and any key furniture or objects.", image])
    return response.text

def ContextExtractor(user_text: str) -> dict:
    """
    Extracts the purpose, budget, and product preference from the user's text.

    Args:
        user_text (str): The user's text.

    Returns:
        dict: A dictionary containing the purpose, budget, and product preference.
    """
    model = genai.GenerativeModel("gemini-1.5-pro")
    response = model.generate_content(
        f"""Extract the purpose, budget, and product preference from the following text.
        Return the result in a JSON format with the following keys: purpose, budget, product_preference.

        Text: {user_text}
        """
    )
    return response.json()

def ProductMatcher(room_description: str, user_context: dict) -> list:
    """
    Matches products from the local JSON database based on the room description and user context.

    Args:
        room_description (str): A description of the room.
        user_context (dict): A dictionary containing the purpose, budget, and product preference.

    Returns:
        list: A list of recommended products.
    """
    with open('products.json', 'r') as f:
        products = json.load(f)

    # Filter by budget first
    budget = user_context.get("budget", float('inf'))
    affordable_products = [p for p in products if p.get("price_usd", 0) <= budget]

    # Let the model decide the best matches based on the context
    model = genai.GenerativeModel("gemini-1.5-pro")
    prompt = f"""
    Based on the following room description and user preferences, select the top 3-5 most suitable products from the list.
    Return a list of the selected product dictionaries.

    Room Description:
    {room_description}

    User Preferences:
    - Purpose: {user_context.get("purpose")}
    - Product Preference: {user_context.get("product_preference")}

    Available Products:
    {json.dumps(affordable_products, indent=2)}
    """
    response = model.generate_content(prompt)
    
    try:
        # The model might return text before or after the JSON list.
        # We attempt to find the JSON list within the response.
        json_start = response.text.find('[')
        json_end = response.text.rfind(']') + 1
        if json_start != -1 and json_end != 0:
            recommended_products_str = response.text[json_start:json_end]
            recommended_products = json.loads(recommended_products_str)
        else:
            recommended_products = []
    except (json.JSONDecodeError, IndexError):
        recommended_products = []
        logger.error("Failed to decode JSON from ProductMatcher model response.")

    return recommended_products

def RecommendationExplainer(products: list, room_description: str, user_context: dict) -> str:
    """
    Generates a human-readable recommendation explaining why the products are a good fit, acting as an expert from rtings.com.

    Args:
        products (list): A list of recommended products with detailed specs and scores.
        room_description (str): The analysis of the room image.
        user_context (dict): The user's stated needs and preferences.

    Returns:
        str: A detailed, expert recommendation in the style of a rtings.com review.
    """
    model = genai.GenerativeModel("gemini-1.5-pro")
    prompt = f"""
    You are an expert product reviewer from rtings.com. Your task is to provide a detailed and helpful recommendation to a user.

    First, present your expert analysis of the user's room image.
    Then, based on this analysis and the user's preferences, present your top recommendations from the provided product list.

    For each recommended product, you must provide a clear, data-driven explanation for *why* it's a great choice. 
    - Reference the specific `rtings_scores` (e.g., movies, gaming).
    - Connect the product's `specs` (e.g., brightness, type, refresh rate) to the room's characteristics (e.g., bright, dark) and the user's goals (e.g., gaming, home theater).
    - Adopt a helpful, expert tone. Start with a summary of your findings.

    **User's Room Analysis:**
    {room_description}

    **User's Preferences:**
    {json.dumps(user_context, indent=2)}

    **Products to Evaluate:**
    {json.dumps(products, indent=2)}

    **Example of a good explanation:**
    'For your living room, which has a lot of natural light, my top pick is the **Samsung S95F OLED**. While most OLEDs struggle with glare, this model is a standout performer in bright rooms. Our tests show it gets significantly brighter than most other OLEDs. This means you'll get a vibrant, punchy image even during the day. It also scored a 9.3 for video games in our lab, thanks to its 144Hz refresh rate and low input lag, which will be perfect for your PS5.'
    """
    response = model.generate_content(prompt)
    return response.text