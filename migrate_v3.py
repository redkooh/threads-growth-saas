"""Migration v3: account_tags + content_presets table"""
import sqlite3, json, sys

DB_PATH = "/home/ubuntu/saas/saas.db"
conn = sqlite3.connect(DB_PATH)
c = conn.cursor()

# 1. Add account_tags column
try:
    c.execute("ALTER TABLE accounts ADD COLUMN account_tags TEXT DEFAULT '[]'")
    print("✅ Added account_tags column")
except sqlite3.OperationalError as e:
    print(f"ℹ️ account_tags: {e}")

# 2. Create content_presets table
c.execute("""
CREATE TABLE IF NOT EXISTS content_presets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    name TEXT NOT NULL,
    settings_json TEXT NOT NULL DEFAULT '{}',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
)""")
print("✅ Created content_presets table")

conn.commit()
conn.close()
print("✅ Migration v3 complete")
