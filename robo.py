from flask import Flask, request, jsonify
from flask_cors import CORS
import os
import base64
import requests
from werkzeug.utils import secure_filename

app = Flask(__name__)
CORS(app)

# Roboflow API Config
ROBOFLOW_API_URL = "https://detect.roboflow.com/infer/workflows/masid-nert8/detect-count-and-visualize"
ROBOFLOW_API_KEY = "eWs6KSOlnWifknc0nP1U"

# Upload folder (to temporarily store images)
UPLOAD_FOLDER = "uploads"
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

@app.route("/", methods=["GET"])
def home():
    return jsonify({"message": "Welcome to the Flask Image Processing API"}), 200

@app.route("/api/detect", methods=["POST"])
def detect_image():
    if "image" not in request.files:
        return jsonify({"error": "No image file provided"}), 400

    image_file = request.files["image"]

    # Save the image temporarily
    filename = secure_filename(image_file.filename)
    image_path = os.path.join(app.config["UPLOAD_FOLDER"], filename)
    image_file.save(image_path)

    # Convert image to Base64
    with open(image_path, "rb") as image_file:
        base64_image = base64.b64encode(image_file.read()).decode("utf-8")

    # Send the image to Roboflow API
    payload = {
        "api_key": ROBOFLOW_API_KEY,
        "inputs": {
            "image": {"type": "base64", "value": base64_image}
        }
    }

    response = requests.post(ROBOFLOW_API_URL, json=payload)

    if response.status_code == 200:
        result = response.json()
        return jsonify({"success": True, "data": result}), 200
    else:
        return jsonify({"error": "Failed to get response from Roboflow"}), 500

# Run the Flask app
if __name__ == "__main__":
    HOST = "0.0.0.0"
    PORT = int(os.getenv("PORT", 5000))
    app.run(debug=True, host=HOST, port=PORT)
