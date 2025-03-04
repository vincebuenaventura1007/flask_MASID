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

# Roboflow Image Detection API
@app.route('/api/detect', methods=['POST'])
def detect_objects():
    try:
        if 'image' not in request.files:
            return jsonify({"error": "No image uploaded"}), 400
        
        image = request.files['image']
        image_path = f"temp/{image.filename}"
        image.save(image_path)  # Save the uploaded image temporarily

        result = roboflow_client.run_workflow(
            workspace_name="masid-nert8",
            workflow_id="detect-count-and-visualize",
            images={"image": image_path},
            use_cache=True
        )

        os.remove(image_path)  # Delete the image after processing
        return jsonify(result), 200

    except Exception as e:
        print(f"[ERROR] Roboflow detection failed: {e}")
        return jsonify({"error": "Object detection failed"}), 500

# Run Flask Server
if __name__ == '__main__':
    HOST = '0.0.0.0'
    PORT = int(os.getenv('PORT', 5001))  # Runs on a separate port
    app.run(debug=True, host=HOST, port=PORT)
