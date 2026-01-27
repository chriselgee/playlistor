"""
Spotify API client wrapper using spotipy.
Handles OAuth, playlist fetching, and playlist creation.
"""
import os
from typing import List, Dict, Any, Optional
import spotipy
from spotipy.oauth2 import SpotifyOAuth


class SpotifyClient:
    def __init__(self):
        self.scope = "playlist-read-private playlist-modify-public playlist-modify-private"
        self.client_id = os.getenv("SPOTIFY_CLIENT_ID")
        self.client_secret = os.getenv("SPOTIFY_CLIENT_SECRET")
        self.redirect_uri = os.getenv("SPOTIFY_REDIRECT_URI")
        
        if not all([self.client_id, self.client_secret, self.redirect_uri]):
            raise ValueError("Missing Spotify credentials in environment variables")
    
    def get_auth_manager(self, cache_path: str = ".spotify_cache") -> SpotifyOAuth:
        """Create SpotifyOAuth manager for authentication."""
        return SpotifyOAuth(
            client_id=self.client_id,
            client_secret=self.client_secret,
            redirect_uri=self.redirect_uri,
            scope=self.scope,
            cache_path=cache_path
        )
    
    def get_client(self, auth_manager: SpotifyOAuth) -> spotipy.Spotify:
        """Create authenticated Spotify client."""
        return spotipy.Spotify(auth_manager=auth_manager)
    
    def fetch_playlist_tracks(self, sp: spotipy.Spotify, playlist_id: str) -> Dict[str, Any]:
        """
        Fetch all tracks from a playlist.
        
        Args:
            sp: Authenticated Spotify client
            playlist_id: Spotify playlist ID
            
        Returns:
            Dictionary with playlist metadata and tracks
        """
        # Get playlist details
        playlist = sp.playlist(playlist_id)
        
        # Fetch all tracks (handle pagination)
        tracks = []
        results = sp.playlist_tracks(playlist_id)
        
        while results:
            for item in results['items']:
                if item['track'] and item['track']['id']:  # Skip None/local tracks
                    track = item['track']
                    tracks.append({
                        'uri': track['uri'],
                        'id': track['id'],
                        'name': track['name'],
                        'artist': ', '.join([artist['name'] for artist in track['artists']]),
                        'duration_ms': track['duration_ms'],
                        'album': track['album']['name']
                    })
            
            # Check for more tracks
            if results['next']:
                results = sp.next(results)
            else:
                break
        
        return {
            'id': playlist['id'],
            'name': playlist['name'],
            'description': playlist.get('description', ''),
            'tracks': tracks,
            'total_tracks': len(tracks)
        }
    
    def validate_anchor_song(self, tracks: List[Dict[str, Any]], song_name: str) -> Optional[Dict[str, Any]]:
        """
        Check if a song exists in the track list.
        
        Args:
            tracks: List of track dictionaries
            song_name: Name of the song to find
            
        Returns:
            Track dictionary if found, None otherwise
        """
        song_name_lower = song_name.lower().strip()
        
        for track in tracks:
            if track['name'].lower().strip() == song_name_lower:
                return track
        
        return None
    
    def create_playlist(self, 
                       sp: spotipy.Spotify, 
                       name: str, 
                       track_uris: List[str],
                       description: str = "Created with Playlistor") -> Dict[str, Any]:
        """
        Create a new playlist with the given tracks.
        
        Args:
            sp: Authenticated Spotify client
            name: Name for the new playlist
            track_uris: List of Spotify track URIs in order
            description: Playlist description
            
        Returns:
            Dictionary with playlist info including URL
        """
        # Get current user
        user = sp.current_user()
        user_id = user['id']
        
        # Create playlist
        playlist = sp.user_playlist_create(
            user=user_id,
            name=name,
            public=True,
            description=description
        )
        
        # Add tracks in batches (Spotify API limit: 100 tracks per request)
        batch_size = 100
        for i in range(0, len(track_uris), batch_size):
            batch = track_uris[i:i + batch_size]
            sp.playlist_add_items(playlist['id'], batch)
        
        return {
            'id': playlist['id'],
            'name': playlist['name'],
            'url': playlist['external_urls']['spotify'],
            'uri': playlist['uri']
        }
