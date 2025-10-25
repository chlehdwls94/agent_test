import json
import os
from google.cloud import bigquery

def load_data_to_bq():
    """
    Reads product data from a JSON file and loads it into a BigQuery table.
    """
    # Manually read the .env file to get the project ID
    project_id = None
    try:
        with open("image_agent/.env", "r") as f:
            for line in f:
                if line.strip().startswith("GOOGLE_CLOUD_PROJECT="):
                    project_id = line.strip().split('=')[1]
                    break
    except FileNotFoundError:
        print("Error: image_agent/.env file not found.")
        return

    if not project_id:
        print("Error: GOOGLE_CLOUD_PROJECT not found in image_agent/.env file.")
        return

    client = bigquery.Client(project=project_id)
    table_id = f"{project_id}.product_recommendations.products"

    # Read the JSON file
    with open('products.json', 'r') as f:
        products_data = json.load(f)

    rows_to_insert = []
    for product in products_data:
        row = {
            "product_id": product.get("product_id"),
            "brand": product.get("brand"),
            "product_name": product.get("product_name"),
            "product_type": product.get("product_type"),
            "specs": json.dumps(product.get("specs")),
            "rtings_scores": json.dumps(product.get("rtings_scores")),
            "price_usd": json.dumps(product.get("price_usd")),
            "summary": product.get("summary"),
        }
        rows_to_insert.append(row)

    if not rows_to_insert:
        print("No data to insert.")
        return

    errors = client.insert_rows_json(table_id, rows_to_insert)
    if errors == []:
        print(f"{len(rows_to_insert)} new rows have been added to {table_id}.")
    else:
        print(f"Encountered errors while inserting rows: {errors}")

if __name__ == "__main__":
    load_data_to_bq()
