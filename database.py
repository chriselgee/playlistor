"""
SQLite database operations for persisting the current project state.
Stores source playlist ID, anchor songs, and sequenced track order.
"""
import sqlite3
import json
from typing import Optional, List, Dict, Any


class Database:
    def __init__(self, db_path: str = "data/playlistor.db"):
        self.db_path = db_path
        self.init_db()
    
    def init_db(self):
        """Initialize database schema if it doesn't exist."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Single table for current project state
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS current_project (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                source_playlist_id TEXT,
                source_playlist_name TEXT,
                anchors TEXT,
                sequenced_tracks TEXT,
                last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        conn.commit()
        conn.close()
    
    def save_project(self, 
                     source_playlist_id: str,
                     source_playlist_name: str,
                     anchors: List[Dict[str, Any]],
                     sequenced_tracks: List[Dict[str, Any]]):
        """
        Save or update the current project state.
        
        Args:
            source_playlist_id: Spotify playlist ID
            source_playlist_name: Playlist name for display
            anchors: List of anchor specifications [{"song_name": str, "time_offset_seconds": int, "relative_to_previous": bool}]
            sequenced_tracks: List of tracks in order [{"uri": str, "name": str, "artist": str, "duration_ms": int, "is_anchor": bool}]
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Serialize lists to JSON
        anchors_json = json.dumps(anchors)
        tracks_json = json.dumps(sequenced_tracks)
        
        # Use INSERT OR REPLACE to ensure only one row exists
        cursor.execute("""
            INSERT OR REPLACE INTO current_project (id, source_playlist_id, source_playlist_name, anchors, sequenced_tracks, last_updated)
            VALUES (1, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        """, (source_playlist_id, source_playlist_name, anchors_json, tracks_json))
        
        conn.commit()
        conn.close()
    
    def load_project(self) -> Optional[Dict[str, Any]]:
        """
        Load the most recent project state.
        
        Returns:
            Dictionary with project data or None if no project exists.
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT source_playlist_id, source_playlist_name, anchors, sequenced_tracks, last_updated
            FROM current_project
            WHERE id = 1
        """)
        
        row = cursor.fetchone()
        conn.close()
        
        if row:
            return {
                "source_playlist_id": row[0],
                "source_playlist_name": row[1],
                "anchors": json.loads(row[2]) if row[2] else [],
                "sequenced_tracks": json.loads(row[3]) if row[3] else [],
                "last_updated": row[4]
            }
        return None
    
    def clear_project(self):
        """Clear the current project state."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM current_project WHERE id = 1")
        conn.commit()
        conn.close()
