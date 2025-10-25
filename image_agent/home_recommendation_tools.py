import os
import json
from dotenv import load_dotenv
from google.adk.tools import ToolContext
from google import genai
from google.genai import types
from google.cloud import bigquery
import logging

logger = logging.getLogger(__name__)

# --- Constants ---
MODEL_FLASH = "gemini-1.5-flash"
MODEL_PRO = "gemini-1.5-pro"

# --- Model Initialization ---
# Manually read the .env file to get the project ID
project_id = None
try:
    with open("image_agent/.env", "r") as f:
        for line in f:
            if line.strip().startswith("GOOGLE_CLOUD_PROJECT="):
                project_id = line.strip().split('=')[1]
                break
except FileNotFoundError:
    logger.error("Error: image_agent/.env file not found.")

if not project_id:
    logger.error("Error: GOOGLE_CLOUD_PROJECT not found in image_agent/.env file.")

# Instantiate models once to be reused
try:
    flash_model = genai.GenerativeModel(MODEL_FLASH)
    pro_model = genai.GenerativeModel(MODEL_PRO)
except Exception as e:
    logger.error(f"Failed to initialize generative models: {e}")
    flash_model = None
    pro_model = None

# --- Tool Functions ---

def ImageAnalyzer(file_path: str) -> str:
    """
    Analyzes an image of a room and returns a detailed description of its characteristics.
    """
    if not flash_model:
        return "Error: Model not initialized."
    if not os.path.exists(file_path):
        logger.error(f"Image file not found at path: {file_path}")
        return f"Error: The image file was not found at '{file_path}'."

    try:
        with open(file_path, "rb") as f:
            image_bytes = f.read()
        image = types.Part.from_data(data=image_bytes, mime_type="image/png")
        response = flash_model.generate_content(["Describe the room's style, lighting conditions, main colors, and any key furniture or objects.", image])
        return response.text
    except FileNotFoundError:
        logger.error(f"Image file not found at path: {file_path}")
        return f"Error: The image file was not found at '{file_path}'."
    except Exception as e:
        logger.error(f"An error occurred during image analysis: {e}")
        return "Error: Could not analyze the image."

def ContextExtractor(user_text: str) -> dict:
    """
    Extracts the purpose, budget, and product preference from the user's text.
    """
    if not pro_model:
        return {"error": "Model not initialized."}

    prompt = f"""Extract the purpose, budget, and product preference from the following text.
        Return the result in a JSON format with the following keys: purpose, budget, product_preference.

        Text: {user_text}
        """
    try:
        response = pro_model.generate_content(prompt)
        return json.loads(response.text)
    except json.JSONDecodeError:
        logger.error(f"Failed to decode JSON from ContextExtractor response: {response.text}")
        return {"error": "Failed to parse user context from text."}
    except Exception as e:
        logger.error(f"An error occurred in ContextExtractor: {e}")
        return {"error": "Could not extract user context."}

def ProductMatcher(room_description: str, user_context: dict) -> list:
    """
    Matches products from the BigQuery database based on the room description and user context.
    """
    if not pro_model:
        return [{"error": "Model not initialized."}]

    try:
        client = bigquery.Client(project=project_id)
        query = f"""SELECT * FROM `{project_id}.product_recommendations.products`"""
        query_job = client.query(query)
        products = [dict(row) for row in query_job]

        # Convert the JSON strings back to dicts
        for product in products:
            product['specs'] = json.loads(product['specs'])
            product['rtings_scores'] = json.loads(product['rtings_scores'])
            product['price_usd'] = json.loads(product['price_usd'])

    except Exception as e:
        logger.error(f"Failed to query BigQuery: {e}")
        return [{"error": "Failed to retrieve product data from BigQuery."}]

    budget = user_context.get("budget", float('inf'))
    affordable_products = [p for p in products if p.get("price_usd", {}).get("55", 0) <= budget]

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
    try:
        response = pro_model.generate_content(prompt)
        json_str = response.text[response.text.find('['):response.text.rfind(']')+1]
        if not json_str:
            logger.warning(f"No JSON list found in ProductMatcher response: {response.text}")
            return []
        return json.loads(json_str)
    except json.JSONDecodeError:
        logger.error(f"Failed to decode JSON from ProductMatcher model response: {response.text}")
        return []
    except Exception as e:
        logger.error(f"An error occurred in ProductMatcher: {e}")
        return []

def RecommendationExplainer(products: list, room_description: str, user_context: dict) -> str:
    """
    Generates a human-readable recommendation explaining why the products are a good fit.
    """
    if not pro_model:
        return "Error: Model not initialized."

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
    """
    try:
        response = pro_model.generate_content(prompt)
        return response.text
    except Exception as e:
        logger.error(f"An error occurred in RecommendationExplainer: {e}")
        return "Error: Could not generate the recommendation."