"""
Flask web application for Spotify playlist time sequencing.
"""
import os
import logging
from flask import Flask, render_template, request, jsonify, session, redirect, url_for
from dotenv import load_dotenv
from spotify_client import SpotifyClient
from database import Database
from sequencer import PlaylistSequencer, SequencerError

# Load environment variables
load_dotenv()

# Configure logging so spotify_client warnings show up
logging.basicConfig(level=logging.DEBUG)

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "dev-secret-key-change-in-production")

# Initialize components
db = Database()
spotify_client = SpotifyClient()


def get_spotify_client():
    """
    Create an authenticated Spotify client from whichever auth method is available.
    Priority: cookie/token auth > OAuth.
    Returns (spotipy.Spotify, auth_method) or (None, None).
    """
    # Check cookie/token auth first
    access_token = session.get('spotify_access_token')
    if access_token:
        method = session.get('auth_method', 'token')
        return spotify_client.get_client_from_token(access_token), method

    # Fall back to OAuth
    token_info = session.get('token_info')
    if token_info and spotify_client.oauth_available:
        auth_manager = spotify_client.get_auth_manager()
        token_info = auth_manager.validate_token(token_info)
        if token_info:
            session['token_info'] = token_info
            return spotify_client.get_client(auth_manager), 'oauth'

    return None, None


@app.route('/')
def index():
    """Main application page."""
    return render_template('index.html')


@app.route('/auth/login')
def auth_login():
    """Initiate Spotify OAuth flow."""
    if not spotify_client.oauth_available:
        return "OAuth not configured. Use cookie or token auth instead.", 400
    auth_manager = spotify_client.get_auth_manager()
    auth_url = auth_manager.get_authorize_url()
    return redirect(auth_url)


@app.route('/callback')
def callback():
    """Handle Spotify OAuth callback."""
    auth_manager = spotify_client.get_auth_manager()
    
    # Get authorization code from query params
    code = request.args.get('code')
    if code:
        token_info = auth_manager.get_access_token(code)
        session['token_info'] = token_info
        return redirect(url_for('index'))
    
    return "Authorization failed", 400


@app.route('/auth/cookie', methods=['POST'])
def auth_cookie():
    """Authenticate using an sp_dc cookie from open.spotify.com."""
    data = request.json
    sp_dc = data.get('sp_dc', '').strip()
    
    if not sp_dc:
        return jsonify({'error': 'sp_dc cookie value is required'}), 400
    
    try:
        access_token = spotify_client.get_token_from_cookie(sp_dc)
        session['spotify_access_token'] = access_token
        session['auth_method'] = 'cookie'
        # Store the sp_dc so we can re-exchange if the token expires
        session['sp_dc'] = sp_dc
        return jsonify({'authenticated': True, 'method': 'cookie'})
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        return jsonify({'error': f'Cookie auth failed: {str(e)}'}), 500


@app.route('/auth/token', methods=['POST'])
def auth_token():
    """Authenticate using a raw Spotify access token."""
    data = request.json
    access_token = data.get('access_token', '').strip()
    
    if not access_token:
        return jsonify({'error': 'Access token is required'}), 400
    
    session['spotify_access_token'] = access_token
    session['auth_method'] = 'token'
    return jsonify({'authenticated': True, 'method': 'token'})


@app.route('/auth/logout', methods=['POST'])
def auth_logout():
    """Clear all auth state."""
    session.pop('token_info', None)
    session.pop('spotify_access_token', None)
    session.pop('auth_method', None)
    session.pop('sp_dc', None)
    return jsonify({'authenticated': False})


@app.route('/auth/status')
def auth_status():
    """Check if user is authenticated via any method."""
    # Check cookie/token auth
    access_token = session.get('spotify_access_token')
    if access_token:
        method = session.get('auth_method', 'token')
        return jsonify({'authenticated': True, 'method': method, 'oauth_available': spotify_client.oauth_available})

    # Check OAuth auth
    token_info = session.get('token_info')
    if token_info and spotify_client.oauth_available:
        auth_manager = spotify_client.get_auth_manager()
        token_info = auth_manager.validate_token(token_info)
        if token_info:
            session['token_info'] = token_info
            return jsonify({'authenticated': True, 'method': 'oauth', 'oauth_available': spotify_client.oauth_available})
    
    return jsonify({'authenticated': False, 'oauth_available': spotify_client.oauth_available})


@app.route('/api/load_project', methods=['GET'])
def load_project():
    """Load the most recent project from database."""
    project = db.load_project()
    if project:
        return jsonify(project)
    return jsonify(None)


@app.route('/api/fetch_playlist', methods=['POST'])
def fetch_playlist():
    """Fetch playlist from Spotify."""
    data = request.json
    playlist_id = data.get('playlist_id')
    
    if not playlist_id:
        return jsonify({'error': 'Playlist ID required'}), 400
    
    sp, method = get_spotify_client()
    if not sp:
        return jsonify({'error': 'Not authenticated'}), 401
    
    try:
        playlist_data = spotify_client.fetch_playlist_tracks(sp, playlist_id)
        
        # Save to database
        db.save_project(
            source_playlist_id=playlist_data['id'],
            source_playlist_name=playlist_data['name'],
            anchors=[],
            sequenced_tracks=[]
        )
        
        return jsonify(playlist_data)
    
    except Exception as e:
        return jsonify({'error': str(e)}), 400


@app.route('/api/sequence_playlist', methods=['POST'])
def sequence_playlist():
    """Generate sequenced playlist based on anchors."""
    data = request.json
    tracks = data.get('tracks', [])
    anchors = data.get('anchors', [])
    crossfade_seconds = data.get('crossfade_seconds', PlaylistSequencer.DEFAULT_CROSSFADE_SECONDS)
    
    if not tracks:
        return jsonify({'error': 'No tracks provided'}), 400
    
    try:
        sequencer = PlaylistSequencer(tracks, crossfade_seconds=crossfade_seconds)
        sequenced_tracks = sequencer.sequence_playlist(anchors)
        
        # Save to database
        project = db.load_project()
        if project:
            db.save_project(
                source_playlist_id=project['source_playlist_id'],
                source_playlist_name=project['source_playlist_name'],
                anchors=anchors,
                sequenced_tracks=sequenced_tracks
            )
        
        return jsonify({'tracks': sequenced_tracks})
    
    except SequencerError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        return jsonify({'error': f'Sequencing failed: {str(e)}'}), 500


@app.route('/api/save_manual_order', methods=['POST'])
def save_manual_order():
    """Save manually reordered tracks."""
    data = request.json
    tracks = data.get('tracks', [])
    anchors = data.get('anchors', [])
    
    project = db.load_project()
    if project:
        db.save_project(
            source_playlist_id=project['source_playlist_id'],
            source_playlist_name=project['source_playlist_name'],
            anchors=anchors,
            sequenced_tracks=tracks
        )
        return jsonify({'success': True})
    
    return jsonify({'error': 'No project loaded'}), 400


@app.route('/api/create_playlist', methods=['POST'])
def create_playlist():
    """Create new Spotify playlist with sequenced tracks."""
    data = request.json
    playlist_name = data.get('name')
    tracks = data.get('tracks', [])
    
    if not playlist_name:
        return jsonify({'error': 'Playlist name required'}), 400
    
    if not tracks:
        return jsonify({'error': 'No tracks to upload'}), 400
    
    sp, method = get_spotify_client()
    if not sp:
        return jsonify({'error': 'Not authenticated'}), 401
    
    try:
        # Extract URIs in order
        track_uris = [track['uri'] for track in tracks]
        
        playlist_info = spotify_client.create_playlist(
            sp=sp,
            name=playlist_name,
            track_uris=track_uris,
            description="Created with Playlistor - Time-sequenced playlist"
        )
        
        return jsonify(playlist_info)
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
