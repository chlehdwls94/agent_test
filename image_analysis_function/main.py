# main.py
import functions_framework
import cv2
import numpy as np
from google.cloud import vision
from google.cloud import storage

@functions_framework.cloud_event
def analyze_image_properties(cloud_event):
    """This function is triggered by a Cloud Storage event.
    It analyzes the uploaded image using the Vision API and OpenCV.
    """
    data = cloud_event.data

    bucket = data["bucket"]
    name = data["name"]

    # Vision API client
    vision_client = vision.ImageAnnotatorClient()
    # Cloud Storage client
    storage_client = storage.Client()

    # Get the image from Cloud Storage
    image_uri = f"gs://{bucket}/{name}"
    image = vision.Image()
    image.source.image_uri = image_uri

    # --- Vision API Analysis ---
    # 1. Label Detection
    response_labels = vision_client.label_detection(image=image)
    labels = [label.description for label in response_labels.label_annotations]

    # 2. Image Properties (Color)
    response_props = vision_client.image_properties(image=image)
    dominant_colors = []
    for color_info in response_props.image_properties_annotation.dominant_colors.colors:
        dominant_colors.append(
            {
                "rgb": (
                    color_info.color.red,
                    color_info.color.green,
                    color_info.color.blue,
                ),
                "score": color_info.score,
            }
        )

    # --- OpenCV Analysis (Brightness) ---
    bucket_obj = storage_client.get_bucket(bucket)
    blob = bucket_obj.blob(name)
    # Download image to a temporary file
    temp_filename = f"/tmp/{name.split('/')[-1]}"
    blob.download_to_filename(temp_filename)

    # Read the image with OpenCV
    cv_image = cv2.imread(temp_filename)
    # Convert to HSV (Hue, Saturation, Value) color space
    hsv = cv2.cvtColor(cv_image, cv2.COLOR_BGR2HSV)
    # The 'V' channel represents the brightness
    brightness = np.mean(hsv[:, :, 2])

    # --- Construct the final result ---
    result = {
        "image_uri": image_uri,
        "labels": labels,
        "dominant_colors": dominant_colors,
        "brightness": brightness, # 0 (dark) to 255 (bright)
    }

    print("Image analysis result:", result)

    # You can save this result to another database or trigger another process
    # For now, we just print it.
    return result
