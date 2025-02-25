from flask import Flask, jsonify, request
from flask_cors import CORS
import psycopg2
import os
from psycopg2 import sql

app = Flask(__name__)
CORS(app)

# Get DATABASE_URL from Railway Environment Variables
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:IaQzbHtNwdPONtDxSewYKYUXEQwhzwvb@switchyard.proxy.rlwy.net:28891/railway")

# Function to get a new database connection
def get_db_connection():
    try:
        conn = psycopg2.connect(DATABASE_URL, sslmode='require')
        return conn
    except Exception as e:
        print(f"❌ Failed to connect to the database: {e}")
        return None

# Get all inventory items
@app.route('/api/inventory', methods=['GET'])
def get_inventory():
    conn = get_db_connection()
    if conn:
        with conn.cursor() as cur:
            cur.execute('SELECT * FROM food_inventory ORDER BY created_at DESC')
            items = cur.fetchall()
            inventory_list = [
                {
                    'id': item[0],
                    'name': item[1],
                    'amount': float(item[2]),
                    'unit': item[3],
                    'created_at': item[4].isoformat()
                }
                for item in items
            ]
            conn.close()
            return jsonify(inventory_list)
    else:
        return jsonify({"error": "Failed to connect to the database"}), 500

# Add a new inventory item
@app.route('/api/inventory', methods=['POST'])
def add_inventory():
    data = request.get_json()
    name = data['name']
    amount = data['amount']
    unit = data['unit']

    conn = get_db_connection()
    if conn:
        with conn.cursor() as cur:
            cur.execute(
                'INSERT INTO food_inventory (name, amount, unit) VALUES (%s, %s, %s) RETURNING *',
                (name, amount, unit)
            )
            new_item = cur.fetchone()
            conn.commit()
            conn.close()

            return jsonify({
                'id': new_item[0],
                'name': new_item[1],
                'amount': float(new_item[2]),
                'unit': new_item[3],
                'created_at': new_item[4].isoformat()
            }), 201
    else:
        return jsonify({"error": "Failed to connect to the database"}), 500

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
