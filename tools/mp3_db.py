import sqlite3
import os

def optimize_db_connection(db_path):
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA journal_mode=WAL")  # Use Write-Ahead Logging
    conn.execute("PRAGMA synchronous=NORMAL")  # Faster writes, still safe
    conn.execute("PRAGMA cache_size=-64000")  # 64MB cache
    conn.execute("PRAGMA temp_store=MEMORY")  # Store temp tables in memory
    return conn

def create_optimized_schema(conn):
    conn.executescript("""
    CREATE TABLE IF NOT EXISTS tracks (
        id INTEGER PRIMARY KEY,
        file_path TEXT UNIQUE NOT NULL,
        title TEXT,
        artist TEXT,
        album TEXT,
        duration_ms INTEGER,
        spotify_id TEXT,
        last_checked TEXT
    );
    CREATE INDEX IF NOT EXISTS idx_file_path ON tracks(file_path);
    CREATE INDEX IF NOT EXISTS idx_spotify_id ON tracks(spotify_id);
    """)
    conn.commit()

def batch_insert_tracks(conn, tracks_data):
    conn.executemany("""
    INSERT OR REPLACE INTO tracks 
    (file_path, title, artist, album, duration_ms, spotify_id, last_checked)
    VALUES (?, ?, ?, ?, ?, ?, ?)
    """, tracks_data)
    conn.commit()

# Usage example:
# db_path = os.path.expanduser("~/Dropbox/my_large_music_db.sqlite")
# conn = optimize_db_connection(db_path)
# create_optimized_schema(conn)
# 
# # Batch insert example
# tracks_data = [
#     ("/path/to/file1.mp3", "Title1", "Artist1", "Album1", 180000, "spotify:track:123", "2023-10-05"),
#     ("/path/to/file2.mp3", "Title2", "Artist2", "Album2", 200000, "spotify:track:456", "2023-10-05"),
#     # ... more tracks ...
# ]
# batch_insert_tracks(conn, tracks_data)
# 
# conn.close()