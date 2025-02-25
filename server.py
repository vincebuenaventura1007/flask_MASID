from flask import Flask, jsonify, request
from flask_cors import CORS
import psycopg2
import os
from psycopg2 import sql

app = Flask(__name__)
CORS(app)

# Load Environment Variables
DB_HOST = os.getenv('DB_HOST', 'postgres.railway.internal')
DB_NAME = os.getenv('DB_NAME', 'railway')
DB_USER = os.getenv('DB_USER', 'postgres')
DB_PASSWORD = os.getenv('DB_PASSWORD', 'IaQzbHtWwdPOntDxSewYKYUXEQwhzwvb')
DB_PORT = os.getenv('DB_PORT', '5432')

def get_db_connection():
    conn = psycopg2.connect(
        host=DB_HOST,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD,
        port=DB_PORT
    )
    return conn

# Get all inventory items
@app.route('/api/inventory', methods=['GET'])
def get_inventory():
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute('SELECT * FROM food_inventory ORDER BY created_at DESC')
    items = cur.fetchall()
    cur.close()
    conn.close()

    inventory_list = []
    for item in items:
        inventory_list.append({
            'id': item[0],
            'name': item[1],
            'amount': float(item[2]),
            'unit': item[3],
            'created_at': item[4].isoformat()
        })

    return jsonify(inventory_list)

# Add a new inventory item
@app.route('/api/inventory', methods=['POST'])
def add_inventory():
    data = request.get_json()
    name = data['name']
    amount = data['amount']
    unit = data['unit']

    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        'INSERT INTO food_inventory (name, amount, unit) VALUES (%s, %s, %s) RETURNING *',
        (name, amount, unit)
    )
    new_item = cur.fetchone()
    conn.commit()
    cur.close()
    conn.close()

    return jsonify({
        'id': new_item[0],
        'name': new_item[1],
        'amount': float(new_item[2]),
        'unit': new_item[3],
        'created_at': new_item[4].isoformat()
    }), 201

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
