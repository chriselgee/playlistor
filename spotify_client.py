"""
Spotify API client wrapper using spotipy.
Handles OAuth, playlist fetching, and playlist creation.
Supports cookie-based and direct token auth as alternatives to OAuth.
"""
import os
import logging
from typing import List, Dict, Any, Optional
import spotipy
from spotipy.oauth2 import SpotifyOAuth

logger = logging.getLogger(__name__)


class SpotifyClient:
    def __init__(self):
        self.scope = "playlist-read-private playlist-modify-public playlist-modify-private"
        self.client_id = os.getenv("SPOTIFY_CLIENT_ID")
        self.client_secret = os.getenv("SPOTIFY_CLIENT_SECRET")
        self.redirect_uri = os.getenv("SPOTIFY_REDIRECT_URI")
        
        # OAuth credentials are optional — cookie/token auth can be used instead
        self.oauth_available = all([self.client_id, self.client_secret, self.redirect_uri])
    
    def get_auth_manager(self, cache_path: str = ".spotify_cache") -> SpotifyOAuth:
        """Create SpotifyOAuth manager for authentication."""
        if not self.oauth_available:
            raise ValueError("Missing Spotify OAuth credentials in environment variables")
        return SpotifyOAuth(
            client_id=self.client_id,
            client_secret=self.client_secret,
            redirect_uri=self.redirect_uri,
            scope=self.scope,
            cache_path=cache_path
        )
    
    def get_client(self, auth_manager: SpotifyOAuth) -> spotipy.Spotify:
        """Create authenticated Spotify client via OAuth auth_manager."""
        return spotipy.Spotify(auth_manager=auth_manager)

    def get_client_from_token(self, access_token: str) -> spotipy.Spotify:
        """Create authenticated Spotify client from a raw access token."""
        return spotipy.Spotify(auth=access_token)

    def get_token_from_cookie(self, sp_dc: str) -> str:
        """
        Exchange an sp_dc cookie for a Spotify access token.
        
        The sp_dc cookie can be obtained from open.spotify.com via browser DevTools
        (Application > Cookies > sp_dc). The resulting token is valid for ~1 hour.
        
        Args:
            sp_dc: The sp_dc cookie value from open.spotify.com
            
        Returns:
            Access token string
            
        Raises:
            ValueError: If the cookie is invalid or the exchange fails
        """
        url = "https://open.spotify.com/get_access_token?reason=transport&productType=web-player"
        
        # Spotify's CDN (Fastly/Varnish) uses JA3/JA4 TLS fingerprinting to block
        # non-browser clients. curl_cffi impersonates real browser TLS fingerprints.
        # We try multiple browser impersonation targets since some may work better
        # depending on the network environment (Docker, proxies, etc.).
        from curl_cffi import requests as cffi_requests
        
        headers = {
            "Accept": "application/json",
            "Accept-Language": "en-US,en;q=0.9",
            "Referer": "https://open.spotify.com/",
            "app-platform": "WebPlayer",
        }
        cookies = {"sp_dc": sp_dc}
        
        # Try multiple impersonation targets — some work better in Docker
        impersonate_targets = ["chrome110", "chrome116", "chrome120", "chrome", "safari15_5"]
        last_error = None
        
        for target in impersonate_targets:
            logger.debug(f"Trying token exchange with impersonate={target}")
            try:
                resp = cffi_requests.get(
                    url,
                    headers=headers,
                    cookies=cookies,
                    impersonate=target,
                    timeout=10,
                )
                logger.debug(f"  -> status={resp.status_code} (impersonate={target})")
                
                if resp.status_code == 200:
                    try:
                        data = resp.json()
                    except Exception:
                        last_error = f"Invalid JSON response: {resp.text[:200]}"
                        continue
                    
                    if data.get("isAnonymous", False):
                        raise ValueError("Cookie was not accepted - sp_dc may be expired or invalid")
                    
                    access_token = data.get("accessToken")
                    if access_token:
                        logger.info(f"Token exchange succeeded with impersonate={target}")
                        return access_token
                    
                    last_error = "No accessToken in response"
                    continue
                else:
                    last_error = f"HTTP {resp.status_code}"
                    continue
                    
            except ValueError:
                raise  # Re-raise cookie-expired errors immediately
            except Exception as e:
                last_error = str(e)
                logger.debug(f"  -> failed: {e}")
                continue
        
        raise ValueError(
            f"Cookie exchange failed after trying all methods ({last_error}). "
            f"Use the Bearer Token option instead: visit "
            f"open.spotify.com/get_access_token in your browser and copy the accessToken value."
        )
    
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
