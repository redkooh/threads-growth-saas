"""Migration: add target/limits/style columns to accounts table."""
import sqlite3
db = sqlite3.connect("/home/ubuntu/saas/saas.db")
cur = db.cursor()

# Get existing columns
cur.execute("PRAGMA table_info(accounts)")
existing = {row[1] for row in cur.fetchall()}

new_cols = [
    ("target_follows", "INTEGER DEFAULT 0"),
    ("target_threads", "INTEGER DEFAULT 6"),
    ("target_replies", "INTEGER DEFAULT 10"),
    ("target_dms", "INTEGER DEFAULT 0"),
    ("max_threads", "INTEGER DEFAULT 8"),
    ("max_replies", "INTEGER DEFAULT 15"),
    ("max_follows", "INTEGER DEFAULT 5"),
    ("max_dms", "INTEGER DEFAULT 3"),
    ("content_style", "TEXT DEFAULT 'auto'"),
    ("vibe", "TEXT DEFAULT ''"),
    ("links_enabled", "BOOLEAN DEFAULT 0"),
    ("today_follows", "INTEGER DEFAULT 0"),
    ("today_dms", "INTEGER DEFAULT 0"),
]

for name, defn in new_cols:
    if name not in existing:
        cur.execute(f"ALTER TABLE accounts ADD COLUMN {name} {defn}")
        print(f"  Added: {name}")
    else:
        print(f"  Skip (exists): {name}")

db.commit()
db.close()
print("\n✅ Migration complete")
