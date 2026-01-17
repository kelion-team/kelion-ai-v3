
import sqlite3
import uuid
import datetime
import os

DB_PATH = os.path.join("data", "k1.db")

def notify():
    if not os.path.exists(DB_PATH):
        # Create DB and dir if not exists
        os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
        print("Database file not found, creating new one...")

    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Ensure table exists
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS broadcasts (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                body TEXT NOT NULL,
                priority TEXT DEFAULT 'info',
                require_confirmation INTEGER DEFAULT 1,
                target TEXT DEFAULT 'all',
                target_user_id TEXT,
                created_at TEXT NOT NULL,
                confirmations_json TEXT DEFAULT '[]'
            )
        """)
        
        # Check if archive exists
        files = [f for f in os.listdir(".") if f.startswith("KELION_PROJECT_FULL") and f.endswith(".zip")]
        if not files:
            msg = "Archive generation failed or not found."
            prio = "warning"
        else:
            latest = max(files, key=os.path.getmtime)
            size_gb = os.path.getsize(latest) / (1024*1024*1024)
            msg = f"ARCHIVE READY. File: {latest} ({size_gb:.2f} GB). Go to SECURITY PANEL to download."
            prio = "info"

        broadcast_id = str(uuid.uuid4())
        now = datetime.datetime.now(datetime.timezone.utc).isoformat()
        
        print(f"Injecting broadcast: {msg}")
        
        cursor.execute("""
            INSERT INTO broadcasts (id, title, body, priority, require_confirmation, target, created_at, confirmations_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (broadcast_id, "ADMIN: SYSTEM BACKUP READY", msg, prio, 1, 'all', now, '[]'))
        
        conn.commit()
        conn.close()
        print("✅ Notification sent to KELION Interface.")
        
    except Exception as e:
        print(f"❌ Error injecting notification: {e}")

if __name__ == "__main__":
    notify()
