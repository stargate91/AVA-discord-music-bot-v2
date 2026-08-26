import sqlite3
import os
from datetime import datetime
from typing import Optional, Dict, Any, List
from core.models import Song
from utils.logger import log

class Database:
    def __init__(self, db_path: str = "data/radio.db"):
        self.db_path = db_path
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        """Returns a configured SQLite connection with WAL mode and memory temp store."""
        conn = sqlite3.connect(self.db_path)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        conn.execute("PRAGMA temp_store=MEMORY")
        return conn

    def _init_db(self):
        """Initializes the database, creates tables and performance indices."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            # 1. Song Metadata Cache
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS song_cache (
                    url TEXT PRIMARY KEY,
                    title TEXT,
                    uploader TEXT,
                    duration INTEGER,
                    thumbnail_url TEXT,
                    local_path TEXT,
                    last_updated TIMESTAMP
                )
            """)
            
            # Migration for local_path if it doesn't exist
            try:
                cursor.execute("ALTER TABLE song_cache ADD COLUMN local_path TEXT")
            except Exception:
                pass
            
            # 2. Playback History (with user stats)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT,
                    path TEXT,
                    uploader TEXT,
                    duration INTEGER,
                    thumbnail_url TEXT,
                    is_external BOOLEAN,
                    requested_by TEXT,
                    user_id TEXT,
                    played_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # 3. User Settings
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS user_settings (
                    user_id TEXT PRIMARY KEY,
                    language TEXT,
                    volume FLOAT,
                    ui_mode TEXT
                )
            """)

            # 4. Global Stats
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS system_stats (
                    key TEXT PRIMARY KEY,
                    value INTEGER DEFAULT 0
                )
            """)
            
            # 5. User Favorites
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS favorites (
                    user_id TEXT,
                    path TEXT,
                    title TEXT,
                    uploader TEXT,
                    duration INTEGER,
                    thumbnail_url TEXT,
                    is_external BOOLEAN,
                    PRIMARY KEY (user_id, path)
                )
            """)

            # 6. Performance Indices (to prevent Full Table Scans)
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_history_id_desc ON history (id DESC)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_history_user ON history (user_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_history_played ON history (played_at DESC)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_song_cache_updated ON song_cache (last_updated DESC)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_fav_user ON favorites (user_id)")
            
            conn.commit()

            # Migrations for existing history schemas
            try:
                cursor.execute("ALTER TABLE history ADD COLUMN requested_by TEXT")
            except Exception:
                pass
            try:
                cursor.execute("ALTER TABLE history ADD COLUMN user_id TEXT")
            except Exception:
                pass
            conn.commit()

    # --- Cache Methods ---
    def get_cache(self, url: str) -> Optional[Dict[str, Any]]:
        try:
            with self._get_connection() as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM song_cache WHERE url = ?", (url,))
                row = cursor.fetchone()
                if row:
                    data = dict(row)
                    data["duration"] = int(data["duration"])
                    return data
        except Exception as e:
            log.debug(f"Cache get error: {url}: {e}")
        return None

    def set_cache(self, url: str, title: str, uploader: str, duration: int, thumbnail_url: str, local_path: Optional[str] = None):
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT OR REPLACE INTO song_cache 
                    (url, title, uploader, duration, thumbnail_url, local_path, last_updated)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (url, title, uploader, duration, thumbnail_url, local_path, datetime.now()))
                conn.commit()
        except Exception as e:
            log.error(f"Cache set error: {e}")

    def set_cache_batch(self, songs_data: List[Dict[str, Any]]):
        """Atomically inserts or replaces a batch of song metadata in a single transaction."""
        if not songs_data:
            return
        try:
            now = datetime.now()
            rows = [
                (
                    d.get("url") or d.get("path"),
                    d.get("title", ""),
                    d.get("uploader", "Unknown"),
                    int(d.get("duration", 0)),
                    d.get("thumbnail_url", ""),
                    d.get("local_path"),
                    now
                )
                for d in songs_data
                if (d.get("url") or d.get("path"))
            ]
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.executemany("""
                    INSERT OR REPLACE INTO song_cache 
                    (url, title, uploader, duration, thumbnail_url, local_path, last_updated)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, rows)
                conn.commit()
        except Exception as e:
            log.error(f"Error in set_cache_batch: {e}")

    def clear_cache(self):
        """Resets the local_path for all cached songs, effectively clearing the physical cache reference."""
        try:
            with self._get_connection() as conn:
                conn.execute("UPDATE song_cache SET local_path = NULL")
                conn.commit()
        except Exception as e:
            log.error(f"Error resetting local_path in cache DB: {e}")

    # --- History Methods ---
    def add_history(self, song: Song):
        """Saves a song to the history table."""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO history 
                    (title, path, uploader, duration, thumbnail_url, is_external, requested_by, user_id)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    song.title, song.path, song.uploader, song.duration, 
                    song.thumbnail_url, song.is_external, song.requested_by, str(song.user_id) if song.user_id else None
                ))
                conn.commit()
        except Exception as e:
            log.error(f"Error adding to history DB: {e}")

    def increment_stat(self, key: str):
        """Increments a global counter for analytics."""
        try:
            with self._get_connection() as conn:
                conn.execute("""
                    INSERT INTO system_stats (key, value) VALUES (?, 1)
                    ON CONFLICT(key) DO UPDATE SET value = value + 1
                """, (key,))
                conn.commit()
        except Exception:
            pass

    def get_history_latest(self, offset: int = 0) -> Optional[Song]:
        """Returns the history entry at the given offset (0 = latest) without deleting."""
        try:
            with self._get_connection() as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM history ORDER BY id DESC LIMIT 1 OFFSET ?", (offset,))
                row = cursor.fetchone()
                if row:
                    return Song.from_dict(dict(row))
                return None
        except Exception as e:
            log.error(f"Error getting history item from DB: {e}")
            return None

    def pop_history_latest(self) -> Optional[Song]:
        """Fetches and deletes the most recent history entry."""
        try:
            with self._get_connection() as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM history ORDER BY id DESC LIMIT 1")
                row = cursor.fetchone()
                if row:
                    song = Song.from_dict(dict(row))
                    cursor.execute("DELETE FROM history WHERE id = ?", (row["id"],))
                    conn.commit()
                    return song
                return None
        except Exception as e:
            log.error(f"Error popping history from DB: {e}")
            return None

    def get_history(self, limit: Optional[int] = None) -> List[Song]:
        """Retrieves history entries, using index for fast retrieval."""
        try:
            with self._get_connection() as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                if limit:
                    cursor.execute("SELECT * FROM history ORDER BY id DESC LIMIT ?", (limit,))
                else:
                    cursor.execute("SELECT * FROM history ORDER BY id DESC")
                rows = cursor.fetchall()
                return [Song.from_dict(dict(row)) for row in rows]
        except Exception as e:
            log.error(f"Error getting history from DB: {e}")
            return []

    def clear_history(self):
        try:
            with self._get_connection() as conn:
                conn.execute("DELETE FROM history")
                conn.commit()
        except Exception as e:
            log.error(f"Error clearing history DB: {e}")

    # --- Favorites Methods ---
    def add_favorite(self, user_id: str, song: Song):
        if not song or not song.path:
            return
            
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT OR REPLACE INTO favorites 
                    (user_id, path, title, uploader, duration, thumbnail_url, is_external)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (
                    str(user_id), song.path, song.title, song.uploader, 
                    song.duration, song.thumbnail_url, song.is_external
                ))
                conn.commit()
        except Exception as e:
            log.error(f"Error adding favorite to DB: {e}")

    def remove_favorite(self, user_id: str, path: str):
        try:
            with self._get_connection() as conn:
                conn.execute("DELETE FROM favorites WHERE user_id = ? AND path = ?", (str(user_id), path))
                conn.commit()
        except Exception as e:
            log.error(f"Error removing favorite from DB: {e}")

    def is_favorite(self, user_id: str, path: str) -> bool:
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT 1 FROM favorites WHERE user_id = ? AND path = ?", (str(user_id), path))
                return cursor.fetchone() is not None
        except Exception:
            return False

    def get_favorites(self, user_id: str) -> List[Song]:
        try:
            with self._get_connection() as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM favorites WHERE user_id = ?", (str(user_id),))
                rows = cursor.fetchall()
                return [Song.from_dict(dict(row)) for row in rows]
        except Exception as e:
            log.error(f"Error getting favorites from DB: {e}")
            return []

    def clear_favorites(self, user_id: str):
        try:
            with self._get_connection() as conn:
                conn.execute("DELETE FROM favorites WHERE user_id = ?", (str(user_id),))
                conn.commit()
        except Exception as e:
            log.error(f"Error clearing favorites DB: {e}")
