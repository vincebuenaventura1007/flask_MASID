from flask import Flask, request, jsonify
import psycopg2
from flask_cors import CORS

app = Flask(__name__)
CORS(app)  # Allow requests from Flutter

# Connect to Railway PostgreSQL
DATABASE_URL = "postgresql://postgres:IaQzbHtNwdPONtDxSewYKYUXEQwhzwvb@postgres.railway.internal:5432/railway"
conn = psycopg2.connect(DATABASE_URL, sslmode='require')

# Create table if not exists
with conn.cursor() as cur:
    cur.execute("""
        CREATE TABLE IF NOT EXISTS inventory (
            id SERIAL PRIMARY KEY,
            ingredient TEXT NOT NULL,
            amount TEXT NOT NULL
        )
    """)
    conn.commit()

# Get all ingredients
@app.route('/ingredients', methods=['GET'])
def get_ingredients():
    with conn.cursor() as cur:
        cur.execute("SELECT * FROM inventory")
        rows = cur.fetchall()
        ingredients = [{"id": row[0], "ingredient": row[1], "amount": row[2]} for row in rows]
        return jsonify(ingredients)

# Add a new ingredient
@app.route('/add_ingredient', methods=['POST'])
def add_ingredient():
    data = request.json
    ingredient = data.get("ingredient")
    amount = data.get("amount")
    
    if not ingredient or not amount:
        return jsonify({"error": "Invalid data"}), 400

    with conn.cursor() as cur:
        cur.execute("INSERT INTO inventory (ingredient, amount) VALUES (%s, %s)", (ingredient, amount))
        conn.commit()
    
    return jsonify({"message": "Ingredient added successfully!"})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
