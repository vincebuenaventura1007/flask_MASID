from flask import Flask, request, jsonify
from flask_cors import CORS
import requests
import os

app = Flask(__name__)
CORS(app)  # Enable CORS for Flutter

# Roboflow API Config
ROBOFLOW_API_URL = "https://detect.roboflow.com/infer/workflows/masid-nert8/detect-count-and-visualize"
ROBOFLOW_API_KEY = "eWs6KSOlnWifknc0nP1U"

@app.route("/", methods=["GET"])
def home():
    return jsonify({"message": "Flask API for MASID running successfully!"})

# Upload and Process Image
@app.route("/predict", methods=["POST"])
def predict():
    try:
        if "image" not in request.files:
            return jsonify({"error": "No image provided"}), 400

        image = request.files["image"]

        # Send image to Roboflow API
        files = {"file": image.read()}
        payload = {"api_key": ROBOFLOW_API_KEY}
        response = requests.post(ROBOFLOW_API_URL, files=files, params=payload)

        # Return API response
        return jsonify(response.json())

    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=int(os.getenv("PORT", 5000)))
