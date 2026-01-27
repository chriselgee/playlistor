# Playlistor - Spotify Playlist Time Sequencer

A web application for creating Spotify playlists with songs anchored at specific time intervals.

## Setup

1. Create a Spotify app at https://developer.spotify.com/dashboard
2. Copy `.env.example` to `.env` and fill in your credentials
3. Build and run with Docker:
   ```bash
   make build
   make run
   ```
4. Open http://localhost:5000

## Docker Commands

- `make build` - Build the Docker image
- `make run` - Start the application container
- `make stop` - Stop and remove the container
- `make clean` - Stop container and remove image
- `make logs` - View container logs
- `make restart` - Restart the container

## Alternative: Local Installation

If you prefer to run without Docker:
```bash
pip install -r requirements.txt
python app.py
```

## Usage

1. Enter a Spotify playlist ID
2. Add anchor songs with relative time offsets (e.g., "1 hour after previous")
3. App sequences songs with random fills between anchors (±5s tolerance)
4. Manually reorder songs via drag-and-drop if desired
5. Upload the sequenced playlist back to Spotify

## Data Persistence

The SQLite database and Spotify cache are stored in mounted volumes, so your data persists between container restarts.
