from flask import Flask, jsonify, request
from flask_cors import CORS
import os
from inference_sdk import InferenceHTTPClient

app = Flask(__name__)
CORS(app)

# Load Roboflow API key from environment variables
ROBOFLOW_API_KEY = os.getenv("ROBOFLOW_API_KEY", "eWs6KSOlnWifknc0nP1U")

# Initialize Roboflow client
roboflow_client = InferenceHTTPClient(
    api_url="https://detect.roboflow.com",
    api_key=ROBOFLOW_API_KEY
)

# Endpoint for object detection
@app.route('/api/detect', methods=['POST'])
def detect_objects():
    try:
        data = request.get_json()
        image_url = data.get("image_url")

        if not image_url:
            return jsonify({"error": "Image URL is required"}), 400

        result = roboflow_client.run_workflow(
            workspace_name="masid-nert8",
            workflow_id="detect-count-and-visualize",
            images={"image": image_url},
            use_cache=True  # Cache workflow definition for 15 minutes
        )

        return jsonify(result), 200
    except Exception as e:
        print(f"[ERROR] Roboflow detection failed: {e}")
        return jsonify({"error": "Object detection failed"}), 500

# Run Flask server
if __name__ == '__main__':
    HOST = '0.0.0.0'
    PORT = int(os.getenv('PORT', 5001))  # Use a different port if running separately
    app.run(debug=True, host=HOST, port=PORT)
