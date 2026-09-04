import sqlite3
import os
import sys

def test_db():
    db_path = "history.db"
    
    # Check schema
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    c.execute("PRAGMA table_info(history)")
    columns = [row[1] for row in c.fetchall()]
    print(f"History Columns: {columns}")
    assert "cover_url" in columns, "cover_url column missing!"
    
    # Read last entry
    c.execute("SELECT title, cover_url FROM history ORDER BY id DESC LIMIT 1")
    row = c.fetchone()
    print(f"Last entry: {row}")
    
    # Read local_media
    c.execute("PRAGMA table_info(local_media)")
    columns = [row[1] for row in c.fetchall()]
    print(f"Local Media Columns: {columns}")
    assert "cover_url" in columns, "cover_url column missing in local_media!"

if __name__ == "__main__":
    test_db()
