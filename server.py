import sys
import os
import base64
import requests
import logging
import psycopg2
from flask import Flask, request, jsonify
from flask_cors import CORS
from werkzeug.utils import secure_filename

# ✅ Fix Unicode issues for Windows terminals
sys.stdout.reconfigure(encoding="utf-8")

# ✅ Configure Logging
logging.basicConfig(level=logging.INFO)

app = Flask(__name__)
CORS(app)  # Enable CORS for Flutter API calls

# ✅ Database Configuration (Railway PostgreSQL)
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://postgres:IaQzbHtWwdPOntDxSewYKYUXEQwhzwvb@postgres.railway.internal:5432/railway"
)

# ✅ Roboflow API Configuration
ROBOFLOW_API_URL = "https://detect.roboflow.com/infer/workflows/masid-nert8/detect-count-and-visualize"
ROBOFLOW_API_KEY = "eWs6KSOlnWifknc0nP1U"

# ✅ Upload folder (temporarily stores images)
UPLOAD_FOLDER = "uploads"
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

# ✅ Function to Get Database Connection
def get_db_connection():
    try:
        conn = psycopg2.connect(DATABASE_URL, sslmode='require')
        return conn
    except Exception as e:
        logging.error(f"❌ Failed to connect to the database: {e}")
        return None

# ✅ Create Table if it Doesn't Exist
def create_table():
    conn = get_db_connection()
    if conn:
        with conn.cursor() as cur:
            cur.execute('''
                CREATE TABLE IF NOT EXISTS inventory (
                    id SERIAL PRIMARY KEY,
                    name TEXT NOT NULL,
                    amount FLOAT NOT NULL,
                    unit TEXT NOT NULL
                )
            ''')
            conn.commit()
        conn.close()

# ✅ Initialize Database on Startup
with app.app_context():
    create_table()

# ✅ Root Route (for Testing)
@app.route("/", methods=["GET"])
def home():
    return jsonify({"message": "Flask API for Inventory & Roboflow is running!"}), 200

# ✅ Image Detection Endpoint (Roboflow)
@app.route("/api/detect", methods=["POST"])
def detect_image():
    logging.info("📥 Received a request!")

    if "image" not in request.files:
        logging.error("❌ No image received")
        return jsonify({"error": "No image file provided"}), 400

    image_file = request.files["image"]

    # ✅ Save the Uploaded Image
    filename = secure_filename(image_file.filename)
    image_path = os.path.join(app.config["UPLOAD_FOLDER"], filename)
    image_file.save(image_path)

    logging.info(f"✅ Received Image: {filename}")
    logging.info(f"📂 Saved Image Path: {image_path}")

    # ✅ Convert Image to Base64
    try:
        with open(image_path, "rb") as img:
            base64_image = base64.b64encode(img.read()).decode("utf-8")
        logging.info("🔄 Image converted to Base64 successfully.")
    except Exception as e:
        logging.error(f"❌ Error converting image to Base64: {e}")
        return jsonify({"error": "Failed to convert image to Base64"}), 500

    # ✅ Send Request to Roboflow API
    payload = {
        "api_key": ROBOFLOW_API_KEY,
        "image": base64_image
    }

    headers = {"Content-Type": "application/json"}

    try:
        logging.info("📤 Sending image to Roboflow...")
        response = requests.post(ROBOFLOW_API_URL, json=payload, headers=headers)
        response.raise_for_status()  # Raise an exception for HTTP errors
        logging.info(f"🔍 Roboflow Response Status: {response.status_code}")
        logging.info(f"📊 Roboflow Response: {response.text}")

        data = response.json()

        # ✅ Extract Count & Classes Safely
        outputs = data.get("outputs", [])
        if isinstance(outputs, list) and len(outputs) > 0:
            output_data = outputs[0]
            count_objects = output_data.get("count_objects", 0)
            predictions = output_data.get("predictions", [])

            # ✅ Ensure predictions is a list
            class_counts = {}
            if isinstance(predictions, list):
                for obj in predictions:
                    if isinstance(obj, dict):  # Ensure obj is a dictionary
                        class_name = obj.get("class", "Unknown")
                        class_counts[class_name] = class_counts.get(class_name, 0) + 1

            # ✅ Format the Output
            formatted_result = {
                "ingredients": count_objects,
                "details": [{"count": count, "class": c} for c, count in class_counts.items()]
            }

            logging.info(f"✅ Final Response: {formatted_result}")
            return jsonify(formatted_result), 200

        else:
            logging.error("❌ Unexpected Roboflow API response format")
            return jsonify({"error": "Invalid response from Roboflow", "response": data}), 500

    except requests.exceptions.RequestException as e:
        logging.error(f"❌ Error communicating with Roboflow: {e}")
        return jsonify({"error": "Failed to connect to Roboflow API"}), 500

# ✅ Health Check Endpoint
@app.route('/api/health', methods=['GET'])
def health_check():
    return jsonify({"status": "API is running"}), 200

# ✅ Get Railway-assigned Port
PORT = int(os.environ.get("PORT", 5000))

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=PORT)
