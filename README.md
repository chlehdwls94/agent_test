# Home Product Recommendation AI Agent

This project is a conversational AI agent that recommends home products to users based on an analysis of a room image and their preferences.

## Architecture

The project is evolving from a simple, single-agent system to a more robust, scalable, and event-driven architecture. 

### Proposed Architecture

```
[User Upload Image] ─> [Cloud Storage Bucket]
        │
        └─> [Cloud Function Trigger]
                │
                ├─> [Vision API + OpenCV] ─> Brightness/Color Analysis
                │
                └─> [Vertex AI Model] ─> Space Classification
                        │
                        └─> [BigQuery / Vector DB] ─> Product Matching
                                │
                                └─> [Vertex AI Agent] ─> Generate Recommendation
```

## Features

- **Conversational Interface:** Interact with the agent through a web-based chat UI.
- **Image-based Recommendations:** Get product recommendations based on an image of your room.
- **Database-driven:** Product information is stored in BigQuery for scalability.
- **Advanced Image Analysis (Phase 2):** A Cloud Function uses the Vision API and OpenCV to perform detailed image analysis, including brightness calculation.

## Setup and Installation

### Prerequisites

- Google Cloud SDK (`gcloud`) installed and configured.
- Python 3.10+
- A Google Cloud project with billing enabled.

### Installation

1.  **Clone the repository:**
    ```bash
    git clone <repository-url>
    cd <repository-name>
    ```

2.  **Create a virtual environment:**
    ```bash
    python -m venv .venv
    source .venv/bin/activate
    ```

3.  **Install the dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

## Configuration

### 1. Environment Variables

Create a `.env` file inside the `image_agent` directory (`image_agent/.env`) with the following content:

```
GOOGLE_GENAI_USE_VERTEXAI=TRUE
GOOGLE_CLOUD_PROJECT=<your-gcp-project-id>
GOOGLE_CLOUD_LOCATION=<your-gcp-region> # e.g., us-central1
MODEL=gemini-1.5-flash
```

Replace `<your-gcp-project-id>` and `<your-gcp-region>` with your Google Cloud project ID and region.

### 2. Google Cloud Authentication

Authenticate your local environment by running:

```bash
gcloud auth application-default login
```

### 3. BigQuery Setup

The agent uses BigQuery to store product data. You need to create a dataset and a table.

1.  **Create the dataset:**
    ```bash
    bq mk --dataset product_recommendations
    ```

2.  **Create the table:**
    ```bash
    bq query --use_legacy_sql=false 'CREATE TABLE product_recommendations.products (product_id STRING, brand STRING, product_name STRING, product_type STRING, specs STRING, rtings_scores STRING, price_usd STRING, summary STRING)'
    ```

3.  **Load the data:**
    Run the following script to load the data from `products.json` into the BigQuery table:
    ```bash
    python load_data_to_bq.py
    ```

## Usage

### Running the Agent (Deployment)

The agent is designed to be deployed as a service on Google Cloud Run. The `deploy.sh` script handles the deployment.

```bash
./deploy.sh
```

After the deployment is complete, the script will output a URL to a web UI where you can interact with the agent.

### Image Analysis Cloud Function (Phase 2)

The `image_analysis_function` directory contains a Cloud Function for advanced image analysis. 

**Deployment:**

To deploy this function, you will need a Cloud Storage bucket. 

1. **Create a Cloud Storage Bucket:**
   ```bash
   gsutil mb gs://<your-bucket-name>
   ```

2. **Deploy the function:**
   Replace `<your-bucket-name>` with your bucket name and run the following command:

   ```bash
   gcloud functions deploy analyze_image_properties \
   --gen2 \
   --runtime python312 \
   --source ./image_analysis_function \
   --entry-point analyze_image_properties \
   --trigger-resource <your-bucket-name> \
   --trigger-event google.storage.object.finalize
   ```

This will deploy a Cloud Function that automatically analyzes any image uploaded to the specified bucket.

## Project Structure

```
.
├── .gitignore
├── deploy.sh
├── image_agent
│   ├── .env
│   ├── __init__.py
│   ├── agent.py
│   ├── home_recommendation_tools.py
│   ├── prompt.py
│   └── tools.py
├── image_analysis_function
│   ├── main.py
│   └── requirements.txt
├── images
│   └── ...
├── load_data_to_bq.py
├── products.json
├── README.md
└── requirements.txt
```
