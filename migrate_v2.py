"""Migrate DB schema: add new columns for enhanced account customization."""
import sqlite3, os

DB_PATH = os.environ.get("SAAS_DB", "/home/ubuntu/saas/saas.db")

conn = sqlite3.connect(DB_PATH)
c = conn.cursor()

# Get existing columns
c.execute("PRAGMA table_info(accounts)")
existing = {row[1] for row in c.fetchall()}

# New columns to add (type, default)
new_cols = {
    "sleep_hours_start": ("INTEGER", 2),
    "sleep_hours_end": ("INTEGER", 8),
    "post_tone": ("VARCHAR(50)", "'friendly'"),
    "post_length": ("VARCHAR(20)", "'auto'"),
    "post_format": ("VARCHAR(20)", "'text'"),
    "topic_keywords": ("TEXT", "''"),
    "avoid_topics": ("TEXT", "''"),
    "target_niche": ("VARCHAR(200)", "''"),
    "target_locations": ("TEXT", "''"),
    "reply_keywords": ("TEXT", "''"),
    "reply_tone": ("VARCHAR(50)", "'value_add'"),
    "reply_length": ("VARCHAR(20)", "'medium'"),
    "viral_threshold": ("INTEGER", 0),
}

added = 0
for col, (typ, default) in new_cols.items():
    if col not in existing:
        c.execute(f"ALTER TABLE accounts ADD COLUMN {col} {typ} DEFAULT {default}")
        added += 1
        print(f"  + {col} ({typ}, default={default})")

conn.commit()
conn.close()
print(f"\nDone. Added {added} columns to accounts table.")
