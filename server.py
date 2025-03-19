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
# TABLE CREATION / MIGRATION
# -----------------------------------------------------------------
def create_conversations_table():
    """
    Creates/updates the 'conversations' table with fields:
      - id, conversation_text, created_at, is_saved,
      - rating_sum, rating_count, photo_base64
    """
    conn = get_db_connection()
    if not conn:
        print("[ERROR] No DB connection in create_conversations_table()")
        return

    try:
        with conn.cursor() as cur:
            # 1) Ensure main table & columns exist
            cur.execute('''
                CREATE TABLE IF NOT EXISTS conversations (
                    id SERIAL PRIMARY KEY,
                    conversation_text TEXT NOT NULL,
                    created_at TIMESTAMP NOT NULL,
                    is_saved BOOLEAN NOT NULL DEFAULT FALSE
                )
            ''')
            conn.commit()

            # 2) Check if columns exist, if not, add them
            # Check 'is_saved' (done below, but we do an extra check)
            cur.execute("""
                SELECT column_name
                  FROM information_schema.columns
                 WHERE table_name='conversations'
            """)
            existing_cols = [row[0] for row in cur.fetchall()]

            # rating_sum float default 0
            if 'rating_sum' not in existing_cols:
                print("[INFO] Adding 'rating_sum' column to 'conversations' table...")
                cur.execute("ALTER TABLE conversations ADD COLUMN rating_sum FLOAT DEFAULT 0")
                conn.commit()

            # rating_count integer default 0
            if 'rating_count' not in existing_cols:
                print("[INFO] Adding 'rating_count' column to 'conversations' table...")
                cur.execute("ALTER TABLE conversations ADD COLUMN rating_count INT DEFAULT 0")
                conn.commit()

            # photo_base64 text (nullable)
            if 'photo_base64' not in existing_cols:
                print("[INFO] Adding 'photo_base64' column to 'conversations' table...")
                cur.execute("ALTER TABLE conversations ADD COLUMN photo_base64 TEXT")
                conn.commit()

            # is_saved column if missing
            if 'is_saved' not in existing_cols:
                print("[INFO] Adding 'is_saved' column to 'conversations' table...")
                cur.execute("""
                    ALTER TABLE conversations
                    ADD COLUMN is_saved BOOLEAN NOT NULL DEFAULT FALSE
                """)
                conn.commit()

    except Exception as e:
        print(f"[ERROR] Failed to create/migrate conversations table: {e}")
    finally:
        conn.close()

def create_inventory_table():
    """
    Creates an 'inventory' table with only 'id' (SERIAL) and 'name' (TEXT NOT NULL).
    """
    conn = get_db_connection()
    if not conn:
        print("[ERROR] No DB connection in create_inventory_table()")
        return

    try:
        with conn.cursor() as cur:
            cur.execute('''
                CREATE TABLE IF NOT EXISTS inventory (
                    id SERIAL PRIMARY KEY,
                    name TEXT NOT NULL
                )
            ''')
            conn.commit()
    except Exception as e:
        print(f"[ERROR] Failed to create inventory table: {e}")
    finally:
        conn.close()

# Create tables on startup
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
    """
    Fetch all conversations, ordered by newest first,
    returning rating_sum, rating_count, average_rating, photo_base64, etc.
    """
    conn = get_db_connection()
    if not conn:
        return jsonify({"error": "Failed to connect to the database"}), 500

    try:
        with conn.cursor() as cur:
            cur.execute('''
                SELECT
                    id,
                    conversation_text,
                    created_at,
                    is_saved,
                    rating_sum,
                    rating_count,
                    photo_base64
                FROM conversations
                ORDER BY created_at DESC
            ''')
            rows = cur.fetchall()

            results = []
            for row in rows:
                conv_id         = row[0]
                conversation    = row[1]
                created_at      = row[2].isoformat()
                is_saved        = row[3]
                rating_sum      = float(row[4])
                rating_count    = int(row[5])
                photo_base64    = row[6]

                avg_rating = 0.0
                if rating_count > 0:
                    avg_rating = rating_sum / rating_count

                results.append({
                    'id': conv_id,
                    'conversation': conversation,
                    'created_at': created_at,
                    'is_saved': is_saved,
                    'rating_sum': rating_sum,
                    'rating_count': rating_count,
                    'average_rating': avg_rating,
                    'photo_base64': photo_base64
                })

            return jsonify(results), 200
    except Exception as e:
        print(f"[ERROR] Failed to fetch conversations: {e}")
        return jsonify({"error": "Failed to fetch conversations"}), 500
    finally:
        conn.close()

@app.route('/api/conversations/saved', methods=['GET'])
def get_saved_conversations():
    """
    Fetch only saved conversations (is_saved = TRUE), ordered by newest first,
    returning rating_sum, rating_count, average_rating, photo_base64, etc.
    """
    conn = get_db_connection()
    if not conn:
        return jsonify({"error": "Failed to connect to the database"}), 500

    try:
        with conn.cursor() as cur:
            cur.execute('''
                SELECT
                    id,
                    conversation_text,
                    created_at,
                    is_saved,
                    rating_sum,
                    rating_count,
                    photo_base64
                FROM conversations
                WHERE is_saved = TRUE
                ORDER BY created_at DESC
            ''')
            rows = cur.fetchall()

            results = []
            for row in rows:
                conv_id         = row[0]
                conversation    = row[1]
                created_at      = row[2].isoformat()
                is_saved        = row[3]
                rating_sum      = float(row[4])
                rating_count    = int(row[5])
                photo_base64    = row[6]

                avg_rating = 0.0
                if rating_count > 0:
                    avg_rating = rating_sum / rating_count

                results.append({
                    'id': conv_id,
                    'conversation': conversation,
                    'created_at': created_at,
                    'is_saved': is_saved,
                    'rating_sum': rating_sum,
                    'rating_count': rating_count,
                    'average_rating': avg_rating,
                    'photo_base64': photo_base64
                })
            return jsonify(results), 200
    except Exception as e:
        print(f"[ERROR] Failed to fetch saved conversations: {e}")
        return jsonify({"error": "Failed to fetch saved conversations"}), 500
    finally:
        conn.close()

@app.route('/api/conversations', methods=['POST'])
def add_conversation():
    """
    Add a new conversation (recipe text). 
    POST body: { "conversation": "<text>" }
    """
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
                INSERT INTO conversations (conversation_text, created_at, is_saved, rating_sum, rating_count, photo_base64)
                VALUES (%s, %s, %s, %s, %s, %s)
                RETURNING id, conversation_text, created_at, is_saved, rating_sum, rating_count, photo_base64
            ''', (conversation_text, datetime.utcnow(), False, 0, 0, None))
            new_convo = cur.fetchone()
            conn.commit()

            return jsonify({
                'id': new_convo[0],
                'conversation': new_convo[1],
                'created_at': new_convo[2].isoformat(),
                'is_saved': new_convo[3],
                'rating_sum': float(new_convo[4]),
                'rating_count': int(new_convo[5]),
                'photo_base64': new_convo[6],
                'average_rating': 0.0
            }), 201
    except Exception as e:
        print(f"[ERROR] Failed to add conversation: {e}")
        return jsonify({"error": "Failed to add conversation"}), 500
    finally:
        conn.close()

@app.route('/api/conversations/<int:conversation_id>', methods=['PUT'])
def update_conversation(conversation_id):
    """
    Update a conversation row with any of these fields:
      - is_saved (bool)
      - rating (a single rating to add to rating_sum, rating_count)
      - photo_base64 (attach dish image)
    Example body:
      {
        "is_saved": true,
        "rating": 4,
        "photo_base64": "<base64 string>"
      }
    We'll re-compute average rating on the fly in the response.
    """
    data = request.get_json()
    # rating is optional, is_saved is optional, photo_base64 is optional
    is_saved = data.get('is_saved')
    new_rating = data.get('rating')   # user rating from 1..5 
    photo_b64 = data.get('photo_base64')

    conn = get_db_connection()
    if not conn:
        return jsonify({"error": "Failed to connect to the database"}), 500

    try:
        with conn.cursor() as cur:
            # First fetch existing row
            cur.execute('''
                SELECT id, conversation_text, created_at, is_saved, rating_sum, rating_count, photo_base64
                  FROM conversations
                 WHERE id = %s
            ''', (conversation_id,))
            existing = cur.fetchone()
            if not existing:
                return jsonify({"error": "Conversation not found"}), 404

            current_is_saved   = existing[3]
            current_rating_sum = float(existing[4])
            current_rating_cnt = int(existing[5])
            current_photo_b64  = existing[6]

            # Update is_saved if provided
            if is_saved is not None:
                current_is_saved = bool(is_saved)

            # If rating is provided, update rating_sum & rating_count
            if new_rating is not None:
                # e.g. new_rating=4 => rating_sum+=4 => rating_count+=1
                # you can clamp rating to 1..5 if needed
                rating_value = float(new_rating)
                current_rating_sum += rating_value
                current_rating_cnt += 1

            # If photo_base64 is provided, store it
            if photo_b64 is not None:
                current_photo_b64 = photo_b64

            # Now write back
            cur.execute('''
                UPDATE conversations
                   SET is_saved = %s,
                       rating_sum = %s,
                       rating_count = %s,
                       photo_base64 = %s
                 WHERE id = %s
             RETURNING 
                id, conversation_text, created_at, is_saved, rating_sum, rating_count, photo_base64
            ''', (
                current_is_saved,
                current_rating_sum,
                current_rating_cnt,
                current_photo_b64,
                conversation_id
            ))
            updated = cur.fetchone()
            conn.commit()

            if updated:
                # Calculate average rating
                sum_val = float(updated[4])
                count_val = int(updated[5])
                avg_rating = 0.0
                if count_val > 0:
                    avg_rating = sum_val / count_val

                return jsonify({
                    'id': updated[0],
                    'conversation': updated[1],
                    'created_at': updated[2].isoformat(),
                    'is_saved': updated[3],
                    'rating_sum': sum_val,
                    'rating_count': count_val,
                    'average_rating': avg_rating,
                    'photo_base64': updated[6]
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
            cur.execute(
                'DELETE FROM conversations WHERE id = %s RETURNING id',
                (conversation_id,)
            )
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
# INVENTORY ENDPOINTS
# -----------------------------------------------------------------
@app.route('/api/inventory', methods=['GET'])
def get_inventory():
    """Return items from the 'inventory' table: (id SERIAL, name TEXT NOT NULL)."""
    conn = get_db_connection()
    if not conn:
        return jsonify({"error": "Failed to connect to the database"}), 500

    try:
        with conn.cursor() as cur:
            cur.execute('SELECT id, name FROM inventory ORDER BY id DESC')
            rows = cur.fetchall()

            inventory_list = []
            for row in rows:
                inventory_list.append({
                    'id': row[0],
                    'name': row[1],
                })

            return jsonify(inventory_list), 200
    except Exception as e:
        print(f"[ERROR] Failed to fetch inventory: {e}")
        return jsonify({"error": "Failed to fetch inventory"}), 500
    finally:
        conn.close()

@app.route('/api/inventory', methods=['POST'])
def add_inventory():
    """
    Only requires 'name'.
    POST body: { "name": "<ingredient>" }
    """
    data = request.get_json()
    name = data.get('name', '').strip()

    if not name:
        return jsonify({"error": "Invalid input: 'name' is required"}), 400

    conn = get_db_connection()
    if not conn:
        return jsonify({"error": "Failed to connect to the database"}), 500

    try:
        with conn.cursor() as cur:
            cur.execute('''
                INSERT INTO inventory (name)
                VALUES (%s)
                RETURNING id, name
            ''', (name,))
            new_item = cur.fetchone()
            conn.commit()

            return jsonify({
                'id': new_item[0],
                'name': new_item[1]
            }), 201
    except Exception as e:
        print(f"[ERROR] Failed to add inventory item: {e}")
        return jsonify({"error": f"Failed to add inventory item: {str(e)}"}), 500
    finally:
        conn.close()

@app.route('/api/inventory/<int:item_id>', methods=['PUT'])
def edit_inventory(item_id):
    """
    Update only the 'name' field.
    PUT body: { "name": "<updated name>" }
    """
    data = request.get_json()
    name = data.get('name', '').strip()

    if not name:
        return jsonify({"error": "Invalid input: 'name' is required"}), 400

    conn = get_db_connection()
    if not conn:
        return jsonify({"error": "Failed to connect to the database"}), 500

    try:
        with conn.cursor() as cur:
            cur.execute('''
                UPDATE inventory
                   SET name = %s
                 WHERE id = %s
             RETURNING id, name
            ''', (name, item_id))
            updated_item = cur.fetchone()
            conn.commit()

            if updated_item:
                return jsonify({
                    'id': updated_item[0],
                    'name': updated_item[1],
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
    """Delete an inventory item by ID."""
    conn = get_db_connection()
    if not conn:
        return jsonify({"error": "Failed to connect to the database"}), 500

    try:
        with conn.cursor() as cur:
            cur.execute(
                'DELETE FROM inventory WHERE id = %s RETURNING id',
                (item_id,)
            )
            deleted_id = cur.fetchone()
            conn.commit()

            if deleted_id:
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
