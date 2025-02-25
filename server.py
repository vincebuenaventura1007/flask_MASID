from flask import Flask, request, jsonify
import psycopg2
from flask_cors import CORS
import os

app = Flask(__name__)
CORS(app)  # Allow requests from Flutter

# Get DATABASE_URL from Railway Environment Variables
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:IaQzbHtNwdPONtDxSewYKYUXEQwhzwvb@postgres.railway.internal:5432/railway")

# Function to get a new connection
def get_db_connection():
    try:
        conn = psycopg2.connect(DATABASE_URL, sslmode='require')
        return conn
    except Exception as e:
        print(f"❌ Failed to connect to the database: {e}")
        return None

# Create table if not exists
@app.before_first_request
def create_table():
    conn = get_db_connection()
    if conn:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS inventory (
                    id SERIAL PRIMARY KEY,
                    ingredient TEXT NOT NULL,
                    amount TEXT NOT NULL
                )
            """)
            conn.commit()
        conn.close()

# Get all ingredients
@app.route('/ingredients', methods=['GET'])
def get_ingredients():
    conn = get_db_connection()
    if conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM inventory")
            rows = cur.fetchall()
            ingredients = [{"id": row[0], "ingredient": row[1], "amount": row[2]} for row in rows]
            conn.close()
            return jsonify(ingredients)
    else:
        return jsonify({"error": "Failed to connect to the database"}), 500

# Add a new ingredient
@app.route('/add_ingredient', methods=['POST'])
def add_ingredient():
    data = request.json
    ingredient = data.get("ingredient")
    amount = data.get("amount")
    
    if not ingredient or not amount:
        return jsonify({"error": "Invalid data"}), 400

    conn = get_db_connection()
    if conn:
        with conn.cursor() as cur:
            cur.execute("INSERT INTO inventory (ingredient, amount) VALUES (%s, %s)", (ingredient, amount))
            conn.commit()
        conn.close()
        return jsonify({"message": "Ingredient added successfully!"})
    else:
        return jsonify({"error": "Failed to connect to the database"}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
