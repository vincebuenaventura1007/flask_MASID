from flask import Flask, jsonify, request
from flask_cors import CORS
import psycopg2
import os
from inference_sdk import InferenceHTTPClient

app = Flask(__name__)
CORS(app)

# Get database details from environment variables
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:your_password@postgres.railway.internal:5432/railway")
ROBOFLOW_API_KEY = os.getenv("ROBOFLOW_API_KEY", "eWs6KSOlnWifknc0nP1U")  # Use environment variable for security

# Initialize Roboflow client
roboflow_client = InferenceHTTPClient(
    api_url="https://detect.roboflow.com",
    api_key=ROBOFLOW_API_KEY
)

# Function to connect to PostgreSQL database
def get_db_connection():
    try:
        conn = psycopg2.connect(DATABASE_URL, sslmode='require')
        return conn
    except Exception as e:
        print(f"[ERROR] Database connection failed: {e}")
        return None

# Create Inventory Table
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

with app.app_context():
    create_table()

# Root Route
@app.route('/', methods=['GET'])
def root():
    return jsonify({"message": "Welcome to the MASID Flask API!"})

# Get all inventory items
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
            print(f"[ERROR] Failed to fetch inventory: {e}")
            return jsonify({"error": "Failed to fetch inventory"}), 500
        finally:
            conn.close()
    else:
        return jsonify({"error": "Database connection error"}), 500

# Add new inventory item
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
            print(f"[ERROR] Failed to add item: {e}")
            return jsonify({"error": "Failed to add item"}), 500
        finally:
            conn.close()
    else:
        return jsonify({"error": "Database connection error"}), 500

# Edit inventory item
@app.route('/api/inventory/<int:item_id>', methods=['PUT'])
def edit_inventory(item_id):
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
                    'UPDATE inventory SET name = %s, amount = %s, unit = %s WHERE id = %s RETURNING *',
                    (name, amount, unit, item_id)
                )
                updated_item = cur.fetchone()
                conn.commit()

                if updated_item:
                    return jsonify({
                        'id': updated_item[0],
                        'name': updated_item[1],
                        'amount': float(updated_item[2]),
                        'unit': updated_item[3]
                    }), 200
                else:
                    return jsonify({"error": "Item not found"}), 404
        except Exception as e:
            print(f"[ERROR] Failed to edit item: {e}")
            return jsonify({"error": "Failed to edit item"}), 500
        finally:
            conn.close()
    else:
        return jsonify({"error": "Database connection error"}), 500

# Delete inventory item
@app.route('/api/inventory/<int:item_id>', methods=['DELETE'])
def delete_inventory(item_id):
    conn = get_db_connection()
    if conn:
        try:
            with conn.cursor() as cur:
                cur.execute('DELETE FROM inventory WHERE id = %s RETURNING id', (item_id,))
                deleted_item = cur.fetchone()
                conn.commit()

                if deleted_item:
                    return jsonify({"message": "Item deleted successfully"}), 200
                else:
                    return jsonify({"error": "Item not found"}), 404
        except Exception as e:
            print(f"[ERROR] Failed to delete item: {e}")
            return jsonify({"error": "Failed to delete item"}), 500
        finally:
            conn.close()
    else:
        return jsonify({"error": "Database connection error"}), 500

# Roboflow Image Detection API
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

# Health Check
@app.route('/api/health', methods=['GET'])
def health_check():
    return jsonify({"status": "API is running"}), 200

# Run Flask Server
if __name__ == '__main__':
    HOST = '0.0.0.0'
    PORT = int(os.getenv('PORT', 5000))
    app.run(debug=True, host=HOST, port=PORT)
