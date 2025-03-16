from flask import Flask, jsonify, request
from flask_cors import CORS
import psycopg2
import os
from datetime import datetime

app = Flask(__name__)
CORS(app)

# -----------------------------------------------------------------
# DATABASE CONNECTION
# -----------------------------------------------------------------
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    # Provide a default or your own connection string here.
    "postgresql://postgres:IaQzbHtWwdPOntDxSewYKYUXEQwhzwvb@postgres.railway.internal:5432/railway"
)

def get_db_connection():
    """Create and return a new database connection."""
    try:
        conn = psycopg2.connect(DATABASE_URL, sslmode='require')
        return conn
    except Exception as e:
        print(f"[ERROR] Failed to connect to the database: {e}")
        return None

# -----------------------------------------------------------------
# TABLE CREATION
# -----------------------------------------------------------------
def create_conversations_table():
    """
    Creates the conversations table with an 'is_saved' column if it doesn't exist.
    If your DB already has 'conversations' but no 'is_saved', run an ALTER TABLE:
      ALTER TABLE conversations ADD COLUMN is_saved BOOLEAN NOT NULL DEFAULT FALSE;
    """
    conn = get_db_connection()
    if conn:
        try:
            with conn.cursor() as cur:
                cur.execute('''
                    CREATE TABLE IF NOT EXISTS conversations (
                        id SERIAL PRIMARY KEY,
                        conversation_text TEXT NOT NULL,
                        created_at TIMESTAMP NOT NULL,
                        is_saved BOOLEAN NOT NULL DEFAULT FALSE
                    )
                ''')
                conn.commit()
        except Exception as e:
            print(f"[ERROR] Failed to create conversations table: {e}")
        finally:
            conn.close()

def create_inventory_table():
    """Creates the inventory table if it doesn't exist."""
    conn = get_db_connection()
    if conn:
        try:
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
        except Exception as e:
            print(f"[ERROR] Failed to create inventory table: {e}")
        finally:
            conn.close()

# Call table creation at startup
with app.app_context():
    create_inventory_table()
    create_conversations_table()

# -----------------------------------------------------------------
# ROOT ENDPOINT (TEST)
# -----------------------------------------------------------------
@app.route('/', methods=['GET'])
def root():
    return jsonify({"message": "Welcome to the API!"}), 200

# -----------------------------------------------------------------
# CONVERSATIONS ENDPOINTS
# -----------------------------------------------------------------
@app.route('/api/conversations', methods=['GET'])
def get_conversations():
    """Fetch all conversations, ordered by newest first."""
    conn = get_db_connection()
    if not conn:
        return jsonify({"error": "Failed to connect to the database"}), 500

    try:
        with conn.cursor() as cur:
            cur.execute('''
                SELECT id, conversation_text, created_at, is_saved
                FROM conversations
                ORDER BY created_at DESC
            ''')
            rows = cur.fetchall()

            results = []
            for row in rows:
                results.append({
                    'id': row[0],
                    'conversation': row[1],
                    'created_at': row[2].isoformat(),
                    'is_saved': row[3],
                })
            return jsonify(results), 200

    except Exception as e:
        print(f"[ERROR] Failed to fetch conversations: {e}")
        return jsonify({"error": "Failed to fetch conversations"}), 500
    finally:
        conn.close()

@app.route('/api/conversations/saved', methods=['GET'])
def get_saved_conversations():
    """Fetch only saved conversations (is_saved = TRUE), ordered by newest first."""
    conn = get_db_connection()
    if not conn:
        return jsonify({"error": "Failed to connect to the database"}), 500

    try:
        with conn.cursor() as cur:
            cur.execute('''
                SELECT id, conversation_text, created_at, is_saved
                FROM conversations
                WHERE is_saved = TRUE
                ORDER BY created_at DESC
            ''')
            rows = cur.fetchall()

            results = []
            for row in rows:
                results.append({
                    'id': row[0],
                    'conversation': row[1],
                    'created_at': row[2].isoformat(),
                    'is_saved': row[3],
                })
            return jsonify(results), 200

    except Exception as e:
        print(f"[ERROR] Failed to fetch saved conversations: {e}")
        return jsonify({"error": "Failed to fetch saved conversations"}), 500
    finally:
        conn.close()

@app.route('/api/conversations', methods=['POST'])
def add_conversation():
    """Add a new conversation to the database."""
    data = request.get_json()
    conversation_text = data.get('conversation', '').strip()

    if not conversation_text:
        return jsonify({"error": "No conversation text provided"}), 400

    conn = get_db_connection()
    if not conn:
        return jsonify({"error": "Failed to connect to the database"}), 500

    try:
        with conn.cursor() as cur:
            cur.execute('''
                INSERT INTO conversations (conversation_text, created_at, is_saved)
                VALUES (%s, %s, %s)
                RETURNING id, conversation_text, created_at, is_saved
            ''', (conversation_text, datetime.utcnow(), False))
            new_convo = cur.fetchone()
            conn.commit()

            return jsonify({
                'id': new_convo[0],
                'conversation': new_convo[1],
                'created_at': new_convo[2].isoformat(),
                'is_saved': new_convo[3]
            }), 201

    except Exception as e:
        print(f"[ERROR] Failed to add conversation: {e}")
        return jsonify({"error": "Failed to add conversation"}), 500
    finally:
        conn.close()

@app.route('/api/conversations/<int:conversation_id>', methods=['PUT'])
def update_conversation(conversation_id):
    """
    Update conversation fields, specifically is_saved.
    Example request body: { "is_saved": true }
    """
    data = request.get_json()
    is_saved = data.get('is_saved')  # can be True or False

    # Validate that is_saved was provided
    if is_saved is None:
        return jsonify({"error": "Missing 'is_saved' field in request body"}), 400

    conn = get_db_connection()
    if not conn:
        return jsonify({"error": "Failed to connect to the database"}), 500

    try:
        with conn.cursor() as cur:
            cur.execute('''
                UPDATE conversations
                SET is_saved = %s
                WHERE id = %s
                RETURNING id, conversation_text, created_at, is_saved
            ''', (is_saved, conversation_id))
            updated_row = cur.fetchone()
            conn.commit()

            if updated_row:
                return jsonify({
                    'id': updated_row[0],
                    'conversation': updated_row[1],
                    'created_at': updated_row[2].isoformat(),
                    'is_saved': updated_row[3]
                }), 200
            else:
                return jsonify({"error": "Conversation not found"}), 404

    except Exception as e:
        print(f"[ERROR] Failed to update conversation: {e}")
        return jsonify({"error": "Failed to update conversation"}), 500
    finally:
        conn.close()

@app.route('/api/conversations/<int:conversation_id>', methods=['DELETE'])
def delete_conversation(conversation_id):
    """Delete a conversation by ID."""
    conn = get_db_connection()
    if not conn:
        return jsonify({"error": "Failed to connect to the database"}), 500

    try:
        with conn.cursor() as cur:
            cur.execute('DELETE FROM conversations WHERE id = %s RETURNING id', (conversation_id,))
            deleted_id = cur.fetchone()
            conn.commit()

            if deleted_id:
                return jsonify({"message": "Conversation deleted successfully"}), 200
            else:
                return jsonify({"error": "Conversation not found"}), 404

    except Exception as e:
        print(f"[ERROR] Failed to delete conversation: {e}")
        return jsonify({"error": "Failed to delete conversation"}), 500
    finally:
        conn.close()

# -----------------------------------------------------------------
# INVENTORY ENDPOINTS (UNCHANGED)
# -----------------------------------------------------------------
@app.route('/api/inventory', methods=['GET'])
def get_inventory():
    conn = get_db_connection()
    if not conn:
        return jsonify({"error": "Failed to connect to the database"}), 500
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
            return jsonify(inventory_list), 200
    except Exception as e:
        print(f"[ERROR] Failed to fetch inventory: {e}")
        return jsonify({"error": "Failed to fetch inventory"}), 500
    finally:
        conn.close()

@app.route('/api/inventory', methods=['POST'])
def add_inventory():
    data = request.get_json()
    name = data.get('name')
    amount = data.get('amount')
    unit = data.get('unit')

    if not name or amount is None or not unit:
        return jsonify({"error": "Invalid input"}), 400

    conn = get_db_connection()
    if not conn:
        return jsonify({"error": "Failed to connect to the database"}), 500

    try:
        with conn.cursor() as cur:
            cur.execute('''
                INSERT INTO inventory (name, amount, unit)
                VALUES (%s, %s, %s)
                RETURNING id, name, amount, unit
            ''', (name, amount, unit))
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
        return jsonify({"error": f"Failed to add inventory item: {str(e)}"}), 500
    finally:
        conn.close()

@app.route('/api/inventory/<int:item_id>', methods=['PUT'])
def edit_inventory(item_id):
    data = request.get_json()
    name = data.get('name')
    amount = data.get('amount')
    unit = data.get('unit')

    if not name or amount is None or not unit:
        return jsonify({"error": "Invalid input"}), 400

    conn = get_db_connection()
    if not conn:
        return jsonify({"error": "Failed to connect to the database"}), 500

    try:
        with conn.cursor() as cur:
            cur.execute('''
                UPDATE inventory
                SET name = %s, amount = %s, unit = %s
                WHERE id = %s
                RETURNING id, name, amount, unit
            ''', (name, amount, unit, item_id))
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
        print(f"[ERROR] Failed to edit inventory item: {e}")
        return jsonify({"error": "Failed to edit inventory item"}), 500
    finally:
        conn.close()

@app.route('/api/inventory/<int:item_id>', methods=['DELETE'])
def delete_inventory(item_id):
    conn = get_db_connection()
    if not conn:
        return jsonify({"error": "Failed to connect to the database"}), 500

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

# -----------------------------------------------------------------
# HEALTH CHECK
# -----------------------------------------------------------------
@app.route('/api/health', methods=['GET'])
def health_check():
    """Simple health check endpoint."""
    return jsonify({"status": "API is running"}), 200

# -----------------------------------------------------------------
# MAIN
# -----------------------------------------------------------------
if __name__ == '__main__':
    HOST = '0.0.0.0'
    PORT = int(os.getenv('PORT', 5000))
    app.run(debug=True, host=HOST, port=PORT)
