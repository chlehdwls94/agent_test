










import os





from dotenv import load_dotenv











from google.adk.tools import ToolContext





import google.cloud.bigquery





from google import genai





from google.genai import types











import logging











logger = logging.getLogger(__name__)











load_dotenv()





PROJECT_ID = os.getenv("GOOGLE_CLOUD_PROJECT")











if not PROJECT_ID:





    logger.error("GOOGLE_CLOUD_PROJECT is not set")











CLIENT = genai.Client(vertexai=True, project=PROJECT_ID, location="us-central1")











def ImageAnalyzer(file_path: str) -> str:





    """





    Analyzes an image of a room and returns a description of the room.











    Args:





        file_path (str): The path to the image file.











    Returns:





        str: A description of the room.





    """





    model = CLIENT.models.get("gemini-2.5-flash")





    with open(file_path, "rb") as f:


        image_bytes = f.read()


    image = types.Part.from_data(data=image_bytes, mime_type="image/png")





    response = model.generate_content(image)





    return response.text











def ContextExtractor(user_text: str) -> dict:





    """





    Extracts the purpose, budget, and product preference from the user's text.











    Args:





        user_text (str): The user's text.











    Returns:





        dict: A dictionary containing the purpose, budget, and product preference.





    """





    model = CLIENT.models.get("gemini-2.5-pro")





    response = model.generate_content(





        f"""Extract the purpose, budget, and product preference from the following text.





        Return the result in a JSON format with the following keys: purpose, budget, product_preference.











        Text: {user_text}





        """





    )





    return response.json()











def ProductMatcher(room_description: str, user_context: dict) -> list:





    """





    Matches products from the BigQuery database based on the room description and user context.











    Args:





        room_description (str): A description of the room.





        user_context (dict): A dictionary containing the purpose, budget, and product preference.











    Returns:





        list: A list of recommended products.





    """





    client = google.cloud.bigquery.Client()





    query = f"""SELECT * FROM `home_products.display_products` WHERE recommended_room_types LIKE '%{user_context["purpose"]}' AND price_usd <= {user_context["budget"]}





    """





    query_job = client.query(query)





    results = query_job.result()





    products = []





    for row in results:





        products.append(dict(row))





    return products











def RecommendationExplainer(products: list) -> str:





    """





    Generates a human-readable recommendation based on the list of products.











    Args:





        products (list): A list of recommended products.











    Returns:





        str: A human-readable recommendation.





    """





    model = CLIENT.models.get("gemini-2.5-pro")





    response = model.generate_content(





        f"""Here are the recommended products:





        {products}











        Please provide a human-readable explanation for why these products are a good fit for the user.





        """





    )





    return response.text











