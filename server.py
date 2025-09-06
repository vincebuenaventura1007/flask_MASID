from flask import Flask, jsonify, request
from flask_cors import CORS
import psycopg2
from psycopg2 import pool
import os
from datetime import datetime

app = Flask(__name__)
CORS(app)

# -----------------------------------------------------------------
# DATABASE CONNECTION WITH POOLING
# -----------------------------------------------------------------
from urllib.parse import urlparse
import re as _re

# Prefer the internal connection if present; fall back to public
RAW_DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://postgres:IaQzbHtWwdPOntDxSewYKYUXEQwhzwvb@postgres.railway.internal:5432/railway"
)
RAW_DATABASE_PUBLIC_URL = os.getenv("DATABASE_PUBLIC_URL")

def _dsn_and_sslmode(url: str):
    """
    Decide sslmode based on host.
    - Internal Railway host / localhost: disable SSL
    - Public/Proxy hosts: require SSL
    """
    parsed = urlparse(url)
    host = (parsed.hostname or "").lower()
    sslmode = "require"
    if host.endswith(".railway.internal") or host in ("localhost", "127.0.0.1"):
        sslmode = "disable"
    return url, sslmode, host

def _create_pool(url: str):
    dsn, sslmode, host = _dsn_and_sslmode(url)
    # Log a sanitized DSN for debugging
    safe_dsn = _re.sub(r":[^@]+@", ":***@", dsn)
    print(f"[INFO] DB connecting to {safe_dsn} (sslmode={sslmode})")
    return psycopg2.pool.ThreadedConnectionPool(
        minconn=1,
        maxconn=10,
        dsn=dsn,
        sslmode=sslmode
    )

db_pool = None
try:
    db_pool = _create_pool(RAW_DATABASE_URL)
    print("[INFO] Connection pool created successfully (primary)")
except Exception as e:
    print(f"[WARN] Primary DB pool failed: {e}")
    if RAW_DATABASE_PUBLIC_URL:
        try:
            db_pool = _create_pool(RAW_DATABASE_PUBLIC_URL)
            print("[INFO] Connection pool created successfully (public fallback)")
        except Exception as e2:
            print(f"[ERROR] Public fallback DB pool failed: {e2}")
            db_pool = None

def get_db_connection():
    """Get a connection from the pool."""
    if not db_pool:
        print("[ERROR] DB pool is not initialized")
        return None
    try:
        conn = db_pool.getconn()
        return conn
    except Exception as e:
        print(f"[ERROR] Failed to get connection from pool: {e}")
        return None

def release_db_connection(conn):
    """Release a connection back to the pool."""
    if not db_pool or not conn:
        return
    try:
        db_pool.putconn(conn)
    except Exception as e:
        print(f"[ERROR] Failed to release connection: {e}")

# -----------------------------------------------------------------
# TABLE CREATION / MIGRATION
# -----------------------------------------------------------------
def create_conversations_table():
    """
    Creates or updates the 'conversations' table with fields:
      - id SERIAL PRIMARY KEY
      - conversation_text TEXT NOT NULL
      - created_at TIMESTAMP NOT NULL
      - is_saved BOOLEAN NOT NULL DEFAULT FALSE
      - is_shared BOOLEAN NOT NULL DEFAULT FALSE
      - rating_sum FLOAT DEFAULT 0
      - rating_count INT DEFAULT 0
      - photo_base64 TEXT
      - title TEXT (optional short name)
    """
    conn = get_db_connection()
    if not conn:
        print("[ERROR] No DB connection in create_conversations_table()")
        return

    try:
        with conn.cursor() as cur:
            cur.execute('''
                CREATE TABLE IF NOT EXISTS conversations (
                    id SERIAL PRIMARY KEY,
                    conversation_text TEXT NOT NULL,
                    created_at TIMESTAMP NOT NULL,
                    is_saved BOOLEAN NOT NULL DEFAULT FALSE,
                    is_shared BOOLEAN NOT NULL DEFAULT FALSE
                )
            ''')
            conn.commit()

            cur.execute("""
                SELECT column_name
                  FROM information_schema.columns
                 WHERE table_name='conversations'
            """)
            existing_cols = [row[0] for row in cur.fetchall()]

            if 'rating_sum' not in existing_cols:
                print("[INFO] Adding 'rating_sum' column to 'conversations' table...")
                cur.execute("ALTER TABLE conversations ADD COLUMN rating_sum FLOAT DEFAULT 0")
                conn.commit()

            if 'rating_count' not in existing_cols:
                print("[INFO] Adding 'rating_count' column to 'conversations' table...")
                cur.execute("ALTER TABLE conversations ADD COLUMN rating_count INT DEFAULT 0")
                conn.commit()

            if 'photo_base64' not in existing_cols:
                print("[INFO] Adding 'photo_base64' column to 'conversations' table...")
                cur.execute("ALTER TABLE conversations ADD COLUMN photo_base64 TEXT")
                conn.commit()

            if 'is_saved' not in existing_cols:
                print("[INFO] Adding 'is_saved' column to 'conversations' table...")
                cur.execute("""
                    ALTER TABLE conversations
                    ADD COLUMN is_saved BOOLEAN NOT NULL DEFAULT FALSE
                """)
                conn.commit()

            if 'title' not in existing_cols:
                print("[INFO] Adding 'title' column to 'conversations' table...")
                cur.execute("ALTER TABLE conversations ADD COLUMN title TEXT")
                conn.commit()

            if 'is_shared' not in existing_cols:
                print("[INFO] Adding 'is_shared' column to 'conversations' table...")
                cur.execute("ALTER TABLE conversations ADD COLUMN is_shared BOOLEAN NOT NULL DEFAULT FALSE")
                conn.commit()

    except Exception as e:
        print(f"[ERROR] Failed to create/migrate conversations table: {e}")
    finally:
        release_db_connection(conn)

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
        release_db_connection(conn)

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
                    is_shared,
                    COALESCE(rating_sum, 0),
                    COALESCE(rating_count, 0),
                    photo_base64,
                    title
                FROM conversations
                ORDER BY created_at DESC
            ''')
            rows = cur.fetchall()
            results = []
            for row in rows:
                conv_id      = row[0]
                conversation = row[1]
                created_at   = row[2]
                is_saved     = row[3]
                is_shared    = row[4]
                rating_sum   = float(row[5])
                rating_count = int(row[6])
                photo_base64 = row[7]
                title        = row[8] if row[8] else None

                avg_rating = 0.0
                if rating_count > 0:
                    avg_rating = rating_sum / rating_count

                results.append({
                    'id': conv_id,
                    'conversation': conversation,
                    'created_at': created_at,
                    'is_saved': is_saved,
                    'is_shared': is_shared,
                    'rating_sum': rating_sum,
                    'rating_count': rating_count,
                    'average_rating': avg_rating,
                    'photo_base64': photo_base64,
                    'title': title
                })
            return jsonify(results), 200
    except Exception as e:
        print(f"[ERROR] Failed to fetch conversations: {e}")
        return jsonify({"error": "Failed to fetch conversations"}), 500
    finally:
        release_db_connection(conn)

@app.route('/api/conversations/saved', methods=['GET'])
def get_saved_conversations():
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
                    is_shared,
                    COALESCE(rating_sum, 0),
                    COALESCE(rating_count, 0),
                    photo_base64,
                    title
                FROM conversations
                WHERE is_saved = TRUE
                ORDER BY created_at DESC
            ''')
            rows = cur.fetchall()
            results = []
            for row in rows:
                conv_id      = row[0]
                conversation = row[1]
                created_at   = row[2]
                is_saved     = row[3]
                is_shared    = row[4]
                rating_sum   = float(row[5])
                rating_count = int(row[6])
                photo_base64 = row[7]
                title        = row[8] if row[8] else None

                avg_rating = 0.0
                if rating_count > 0:
                    avg_rating = rating_sum / rating_count

                results.append({
                    'id': conv_id,
                    'conversation': conversation,
                    'created_at': created_at,
                    'is_saved': is_saved,
                    'is_shared': is_shared,
                    'rating_sum': rating_sum,
                    'rating_count': rating_count,
                    'average_rating': avg_rating,
                    'photo_base64': photo_base64,
                    'title': title
                })
            return jsonify(results), 200
    except Exception as e:
        print(f"[ERROR] Failed to fetch saved conversations: {e}")
        return jsonify({"error": "Failed to fetch saved conversations"}), 500
    finally:
        release_db_connection(conn)

@app.route('/api/conversations/shared', methods=['GET'])
def get_shared_conversations():
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
                    is_shared,
                    COALESCE(rating_sum, 0),
                    COALESCE(rating_count, 0),
                    photo_base64,
                    title
                FROM conversations
                WHERE is_shared = TRUE
                ORDER BY created_at DESC
            ''')
            rows = cur.fetchall()
            results = []
            for row in rows:
                conv_id      = row[0]
                conversation = row[1]
                created_at   = row[2]
                is_saved     = row[3]
                is_shared    = row[4]
                rating_sum   = float(row[5])
                rating_count = int(row[6])
                photo_base64 = row[7]
                title        = row[8] if row[8] else None

                avg_rating = 0.0
                if rating_count > 0:
                    avg_rating = rating_sum / rating_count

                results.append({
                    'id': conv_id,
                    'conversation': conversation,
                    'created_at': created_at,
                    'is_saved': is_saved,
                    'is_shared': is_shared,
                    'rating_sum': rating_sum,
                    'rating_count': rating_count,
                    'average_rating': avg_rating,
                    'photo_base64': photo_base64,
                    'title': title
                })
            return jsonify(results), 200
    except Exception as e:
        print(f"[ERROR] Failed to fetch shared conversations: {e}")
        return jsonify({"error": "Failed to fetch shared conversations"}), 500
    finally:
        release_db_connection(conn)

@app.route('/api/conversations', methods=['POST'])
def add_conversation():
    data = request.get_json()
    conversation_text = data.get('conversation', '').strip()
    title = data.get('title', '').strip()
    if not conversation_text:
        return jsonify({"error": "No conversation text provided"}), 400
    conn = get_db_connection()
    if not conn:
        return jsonify({"error": "Failed to connect to the database"}), 500
    try:
        with conn.cursor() as cur:
            cur.execute('''
                INSERT INTO conversations (
                    conversation_text,
                    created_at,
                    is_saved,
                    is_shared,
                    rating_sum,
                    rating_count,
                    photo_base64,
                    title
                )
                VALUES (%s, %s, %s, %s, 0, 0, %s, %s)
                RETURNING
                    id,
                    conversation_text,
                    created_at,
                    is_saved,
                    is_shared,
                    rating_sum,
                    rating_count,
                    photo_base64,
                    title
            ''', (
                conversation_text,
                datetime.utcnow(),
                False,
                False,
                data.get('photo_base64'),
                title if title else None
            ))
            new_conv = cur.fetchone()
            conn.commit()
            return jsonify({
                'id': new_conv[0],
                'conversation': new_conv[1],
                'created_at': new_conv[2].isoformat(),
                'is_saved': new_conv[3],
                'is_shared': new_conv[4],
                'rating_sum': float(new_conv[5]),
                'rating_count': int(new_conv[6]),
                'average_rating': (float(new_conv[5]) / int(new_conv[6])) if int(new_conv[6]) > 0 else 0.0,
                'photo_base64': new_conv[7],
                'title': new_conv[8]
            }), 201
    except Exception as e:
        print(f"[ERROR] Failed to add conversation: {e}")
        return jsonify({"error": "Failed to add conversation"}), 500
    finally:
        release_db_connection(conn)

@app.route('/api/conversations/<int:conversation_id>', methods=['PUT'])
def update_conversation(conversation_id):
    data = request.get_json()
    is_saved = data.get('is_saved')
    new_is_shared = data.get('is_shared')
    new_rating = data.get('rating')
    photo_b64 = data.get('photo_base64')
    new_title = data.get('title', '').strip()
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
                    is_shared,
                    COALESCE(rating_sum, 0),
                    COALESCE(rating_count, 0),
                    photo_base64,
                    title
                FROM conversations
                WHERE id = %s
            ''', (conversation_id,))
            row = cur.fetchone()
            if not row:
                return jsonify({"error": "Conversation not found"}), 404

            current_is_saved = row[3]
            current_is_shared = row[4]
            current_rating_sum = float(row[5])
            current_rating_cnt = int(row[6])
            current_photo_b64 = row[7]
            current_title = row[8] if row[8] else None

            if isinstance(is_saved, bool):
                current_is_saved = is_saved
            if isinstance(new_is_shared, bool):
                current_is_shared = new_is_shared
            if isinstance(new_rating, (int, float)):
                current_rating_sum += float(new_rating)
                current_rating_cnt += 1
            if isinstance(photo_b64, str):
                current_photo_b64 = photo_b64 if photo_b64 else None
            if isinstance(new_title, str):
                current_title = new_title if new_title else None

            cur.execute('''
                UPDATE conversations
                   SET is_saved     = %s,
                       is_shared    = %s,
                       rating_sum   = %s,
                       rating_count = %s,
                       photo_base64 = %s,
                       title        = %s
                 WHERE id = %s
             RETURNING
                id,
                conversation_text,
                created_at,
                is_saved,
                is_shared,
                rating_sum,
                rating_count,
                photo_base64,
                title
            ''', (
                current_is_saved,
                current_is_shared,
                current_rating_sum,
                current_rating_cnt,
                current_photo_b64,
                current_title,
                conversation_id
            ))
            updated = cur.fetchone()
            conn.commit()
            if updated:
                sum_val   = float(updated[5])
                count_val = int(updated[6])
                avg_rating = 0.0
                if count_val > 0:
                    avg_rating = sum_val / count_val
                return jsonify({
                    'id': updated[0],
                    'conversation': updated[1],
                    'created_at': updated[2].isoformat(),
                    'is_saved': updated[3],
                    'is_shared': updated[4],
                    'rating_sum': sum_val,
                    'rating_count': count_val,
                    'average_rating': avg_rating,
                    'photo_base64': updated[7],
                    'title': updated[8]
                }), 200
            else:
                return jsonify({"error": "Conversation not found"}), 404
    except Exception as e:
        print(f"[ERROR] Failed to update conversation: {e}")
        return jsonify({"error": "Failed to update conversation"}), 500
    finally:
        release_db_connection(conn)

@app.route('/api/conversations/<int:conversation_id>', methods=['DELETE'])
def delete_conversation(conversation_id):
    conn = get_db_connection()
    if not conn:
        return jsonify({"error": "Failed to connect to the database"}), 500
    try:
        with conn.cursor() as cur:
            cur.execute('DELETE FROM conversations WHERE id = %s RETURNING id', (conversation_id,))
            deleted = cur.fetchone()
            conn.commit()
            if deleted:
                return jsonify({"deleted_id": deleted[0]}), 200
            else:
                return jsonify({"error": "Conversation not found"}), 404
    except Exception as e:
        print(f"[ERROR] Failed to delete conversation: {e}")
        return jsonify({"error": "Failed to delete conversation"}), 500
    finally:
        release_db_connection(conn)

# -----------------------------------------------------------------
# INVENTORY ENDPOINTS
# -----------------------------------------------------------------
@app.route('/api/inventory', methods=['GET'])
def get_inventory():
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
        release_db_connection(conn)

@app.route('/api/inventory', methods=['POST'])
def add_inventory():
    data = request.get_json()
    name = data.get('name', '').strip()
    if not name:
        return jsonify({"error": "Name cannot be empty"}), 400
    conn = get_db_connection()
    if not conn:
        return jsonify({"error": "Failed to connect to the database"}), 500
    try:
        with conn.cursor() as cur:
            cur.execute('INSERT INTO inventory (name) VALUES (%s) RETURNING id, name', (name,))
            new_item = cur.fetchone()
            conn.commit()
            return jsonify({
                'id': new_item[0],
                'name': new_item[1],
            }), 201
    except Exception as e:
        print(f"[ERROR] Failed to add to inventory: {e}")
        return jsonify({"error": "Failed to add to inventory"}), 500
    finally:
        release_db_connection(conn)

@app.route('/api/inventory/<int:item_id>', methods=['PUT'])
def edit_inventory(item_id):
    data = request.get_json()
    name = data.get('name', '').strip()
    if not name:
        return jsonify({"error": "Name cannot be empty"}), 400
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
        release_db_connection(conn)

@app.route('/api/inventory/<int:item_id>', methods=['DELETE'])
def delete_inventory(item_id):
    conn = get_db_connection()
    if not conn:
        return jsonify({"error": "Failed to connect to the database"}), 500
    try:
        with conn.cursor() as cur:
            cur.execute('DELETE FROM inventory WHERE id = %s RETURNING id', (item_id,))
            deleted = cur.fetchone()
            conn.commit()
            if deleted:
                return jsonify({"deleted_id": deleted[0]}), 200
            else:
                return jsonify({"error": "Item not found"}), 404
    except Exception as e:
        print(f"[ERROR] Failed to delete inventory item: {e}")
        return jsonify({"error": "Failed to delete inventory item"}), 500
    finally:
        release_db_connection(conn)

# -----------------------------------------------------------------
# HEALTH CHECK
# -----------------------------------------------------------------
@app.route('/api/health', methods=['GET'])
def health_check():
    return jsonify({"status": "API is running"}), 200

@app.route('/api/health/db', methods=['GET'])
def health_check_db():
    conn = get_db_connection()
    if not conn:
        return jsonify({"status": "db: down"}), 500
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT 1")
            cur.fetchone()
        return jsonify({"status": "db: up"}), 200
    except Exception as e:
        print(f"[ERROR] DB health check failed: {e}")
        return jsonify({"status": "db: error"}), 500
    finally:
        release_db_connection(conn)

# -----------------------------------------------------------------
# MAIN
# -----------------------------------------------------------------
if __name__ == '__main__':
    HOST = '0.0.0.0'
    PORT = int(os.getenv('PORT', 5000))
    app.run(debug=True, host=HOST, port=PORT)
