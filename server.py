from flask import Flask, jsonify, request
from flask_cors import CORS
import psycopg2
import os

app = Flask(__name__)
CORS(app)

# Get DATABASE_URL from Railway Environment Variables or use default
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:IaQzbHtWwdPOntDxSewYKYUXEQwhzwvb@switchyard.proxy.rlwy.net:28891/railway")

# Function to get a new database connection
def get_db_connection():
    try:
        conn = psycopg2.connect(DATABASE_URL, sslmode='require')
        return conn
    except Exception as e:
        print(f"[ERROR] Failed to connect to the database: {e}")
        return None

# Create Table if it doesn't exist
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

# Initialize the Database on Startup
with app.app_context():
    create_table()

# Root Route (for testing)
@app.route('/', methods=['GET'])
def root():
    return jsonify({"message": "Welcome to the Inventory API!"})

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
        return jsonify({"error": "Failed to connect to the database"}), 500

# Add a new inventory item
@app.route('/api/inventory', methods=['POST'])
def add_inventory():
    data = request.get_json()
    name = data.get('name')
    amount = data.get('amount')
    unit = data.get('unit')

    # Input Validation
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
            print(f"[ERROR] Failed to add inventory item: {e}")
            return jsonify({"error": "Failed to add inventory item"}), 500
        finally:
            conn.close()
    else:
        return jsonify({"error": "Failed to connect to the database"}), 500

# Delete an inventory item by ID
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
            print(f"[ERROR] Failed to delete inventory item: {e}")
            return jsonify({"error": "Failed to delete inventory item"}), 500
        finally:
            conn.close()
    else:
        return jsonify({"error": "Failed to connect to the database"}), 500

# Health Check Endpoint
@app.route('/api/health', methods=['GET'])
def health_check():
    return jsonify({"status": "API is running"}), 200

# Run the Flask app
if __name__ == '__main__':
    # Use Railway-assigned PORT if available, otherwise default to 5000
    HOST = '0.0.0.0'
    PORT = int(os.getenv('PORT', 5000))
    app.run(debug=True, host=HOST, port=PORT)
