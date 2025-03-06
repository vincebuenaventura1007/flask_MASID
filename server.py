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
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:IaQzbHtWwdPOntDxSewYKYUXEQwhzwvb@postgres.railway.internal:5432/railway")

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
    return jsonify({"message": "Flask API is running!"}), 200

# ✅ Image Detection Endpoint (Roboflow)
@app.route("/api/detect", methods=["POST"])
def detect_image():
    if "image" not in request.files:
        logging.info("❌ No image received")
        return jsonify({"error": "No image file provided"}), 400

    image_file = request.files["image"]

    # ✅ Save the Uploaded Image
    filename = secure_filename(image_file.filename)
    image_path = os.path.join(app.config["UPLOAD_FOLDER"], filename)
    image_file.save(image_path)

    logging.info(f"✅ Received Image: {filename}")
    logging.info(f"📂 Saved Image Path: {image_path}")

    # ✅ Convert Image to Base64
    with open(image_path, "rb") as img:
        base64_image = base64.b64encode(img.read()).decode("utf-8")

    logging.info("🔄 Converting Image to Base64...")

    # ✅ Send Request to Roboflow API
    payload = {
        "api_key": ROBOFLOW_API_KEY,
        "inputs": {
            "image": {"type": "base64", "value": base64_image}
        }
    }

    logging.info("📤 Sending image to Roboflow...")
    response = requests.post(ROBOFLOW_API_URL, json=payload)

    logging.info(f"🔍 Roboflow Response Status: {response.status_code}")
    logging.info(f"📊 Roboflow Response: {response.text}")

    if response.status_code == 200:
        data = response.json()

        # ✅ Extract Count & Classes
        count_objects = data.get("outputs", [{}])[0].get("count_objects", 0)
        predictions = data.get("outputs", [{}])[0].get("predictions", [])

        logging.info(f"🛠️ Extracted Objects: {count_objects}")
        logging.info(f"📋 Raw Predictions: {predictions}")

        # ✅ Count Occurrences of Each Class
        class_counts = {}
        for obj in predictions:
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
        return jsonify({"error": "Failed to get response from Roboflow", "response": response.text}), 500

# ✅ Get All Inventory Items
@app.route('/api/inventory', methods=['GET'])
def get_inventory():
    conn = get_db_connection()
    if conn:
        try:
            with conn.cursor() as cur:
                cur.execute('SELECT * FROM inventory ORDER BY id DESC')
                items = cur.fetchall()
                inventory_list = [
                    {
                        'id': item[0],
                        'name': item[1],
                        'amount': float(item[2]),
                        'unit': item[3]
                    }
                    for item in items
                ]
                return jsonify(inventory_list)
        except Exception as e:
            logging.error(f"❌ Failed to fetch inventory: {e}")
            return jsonify({"error": "Failed to fetch inventory"}), 500
        finally:
            conn.close()
    else:
        return jsonify({"error": "Failed to connect to the database"}), 500

# ✅ Add New Inventory Item
@app.route('/api/inventory', methods=['POST'])
def add_inventory():
    data = request.get_json()
    name = data.get('name')
    amount = data.get('amount')
    unit = data.get('unit')

    if not name or not amount or not unit:
        return jsonify({"error": "Invalid input"}), 400

    conn = get_db_connection()
    if conn:
        try:
            with conn.cursor() as cur:
                cur.execute(
                    'INSERT INTO inventory (name, amount, unit) VALUES (%s, %s, %s) RETURNING *',
                    (name, amount, unit)
                )
                new_item = cur.fetchone()
                conn.commit()
                return jsonify({
                    'id': new_item[0],
                    'name': new_item[1],
                    'amount': float(new_item[2]),
                    'unit': new_item[3]
                }), 201
        except Exception as e:
            logging.error(f"❌ Failed to add inventory item: {e}")
            return jsonify({"error": "Failed to add inventory item"}), 500
        finally:
            conn.close()
    else:
        return jsonify({"error": "Failed to connect to the database"}), 500

# ✅ Health Check Endpoint
@app.route('/api/health', methods=['GET'])
def health_check():
    return jsonify({"status": "API is running"}), 200

# ✅ Get Railway-assigned Port
PORT = int(os.environ.get("PORT", 5000))

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=PORT)
