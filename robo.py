import sys
import os
import base64
import requests
from flask import Flask, request, jsonify
from flask_cors import CORS
from werkzeug.utils import secure_filename

# ✅ Fix Unicode issues for Windows terminals
sys.stdout.reconfigure(encoding='utf-8')

app = Flask(__name__)
CORS(app)  # Enable CORS for Flutter API calls

# Roboflow API Configuration
ROBOFLOW_API_URL = "https://detect.roboflow.com/infer/workflows/masid-nert8/detect-count-and-visualize"
ROBOFLOW_API_KEY = "eWs6KSOlnWifknc0nP1U"

# Upload folder (temporarily stores images)
UPLOAD_FOLDER = "uploads"
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

@app.route("/", methods=["GET"])
def home():
    return jsonify({"message": "Flask Roboflow API is running!"}), 200

@app.route("/api/detect", methods=["POST"])
def detect_image():
    if "image" not in request.files:
        print("❌ No image received")
        return jsonify({"error": "No image file provided"}), 400

    image_file = request.files["image"]

    # Save the uploaded image
    filename = secure_filename(image_file.filename)
    image_path = os.path.join(app.config["UPLOAD_FOLDER"], filename)
    image_file.save(image_path)

    print(f"✅ Received Image: {filename}")
    print(f"📂 Saved Image Path: {image_path}")

    # Convert image to Base64
    with open(image_path, "rb") as img:
        base64_image = base64.b64encode(img.read()).decode("utf-8")

    print("🔄 Converting Image to Base64...")

    # Send request to Roboflow API
    payload = {
        "api_key": ROBOFLOW_API_KEY,
        "inputs": {
            "image": {"type": "base64", "value": base64_image}
        }
    }

    print("📤 Sending image to Roboflow...")
    response = requests.post(ROBOFLOW_API_URL, json=payload)

    print(f"🔍 Roboflow Response Status: {response.status_code}")
    print(f"📊 Roboflow Response: {response.text}")

    if response.status_code == 200:
        data = response.json()

        # Extract count_objects and class names
        count_objects = data.get("outputs", [{}])[0].get("count_objects", 0)
        predictions = data.get("outputs", [{}])[0].get("predictions", [])

        print(f"🛠️ Extracted Objects: {count_objects}")
        print(f"📋 Raw Predictions: {predictions}")

        # Count occurrences of each class
        class_counts = {}
        for obj in predictions:
            class_name = obj.get("class", "Unknown")
            class_counts[class_name] = class_counts.get(class_name, 0) + 1

        # Format the output
        formatted_result = {
            "ingredients": count_objects,
            "details": [{"count": count, "class": c} for c, count in class_counts.items()]
        }

        print(f"✅ Final Response: {formatted_result}")
        return jsonify(formatted_result), 200
    else:
        return jsonify({"error": "Failed to get response from Roboflow", "response": response.text}), 500

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
