// Global state
let currentPlaylist = null;
let currentTracks = [];
let anchors = [];
let sequencedTracks = [];

// DOM Elements
const loginBtn = document.getElementById('login-btn');
const authIndicator = document.getElementById('auth-indicator');
const playlistIdInput = document.getElementById('playlist-id');
const fetchBtn = document.getElementById('fetch-btn');
const playlistInfo = document.getElementById('playlist-info');
const playlistName = document.getElementById('playlist-name');
const trackCount = document.getElementById('track-count');

const anchorSongName = document.getElementById('anchor-song-name');
const anchorHours = document.getElementById('anchor-hours');
const anchorMinutes = document.getElementById('anchor-minutes');
const anchorSeconds = document.getElementById('anchor-seconds');
const addAnchorBtn = document.getElementById('add-anchor-btn');
const anchorsList = document.getElementById('anchors-list');
const clearAnchorsBtn = document.getElementById('clear-anchors-btn');
const sequenceBtn = document.getElementById('sequence-btn');

const sequenceContainer = document.getElementById('sequence-container');
const sequencePlaceholder = document.getElementById('sequence-placeholder');
const tracksList = document.getElementById('tracks-list');
const totalDuration = document.getElementById('total-duration');
const reshuffleBtn = document.getElementById('reshuffle-btn');

const newPlaylistName = document.getElementById('new-playlist-name');
const uploadBtn = document.getElementById('upload-btn');
const uploadResult = document.getElementById('upload-result');

const errorToast = document.getElementById('error-toast');
const successToast = document.getElementById('success-toast');

// Initialize
document.addEventListener('DOMContentLoaded', () => {
    checkAuthStatus();
    loadProject();
    setupEventListeners();
});

function setupEventListeners() {
    loginBtn.addEventListener('click', () => {
        window.location.href = '/auth/login';
    });

    fetchBtn.addEventListener('click', fetchPlaylist);
    
    addAnchorBtn.addEventListener('click', addAnchor);
    clearAnchorsBtn.addEventListener('click', clearAnchors);
    sequenceBtn.addEventListener('click', generateSequence);
    reshuffleBtn.addEventListener('click', generateSequence);
    
    uploadBtn.addEventListener('click', uploadPlaylist);
}

async function checkAuthStatus() {
    try {
        const response = await fetch('/auth/status');
        const data = await response.json();
        
        if (data.authenticated) {
            authIndicator.textContent = '✓ Connected to Spotify';
            authIndicator.style.background = 'rgba(72, 187, 120, 0.8)';
            loginBtn.style.display = 'none';
        } else {
            authIndicator.textContent = '⚠ Not connected';
            authIndicator.style.background = 'rgba(252, 129, 129, 0.8)';
            loginBtn.style.display = 'inline-block';
        }
    } catch (error) {
        console.error('Auth check failed:', error);
    }
}

async function loadProject() {
    try {
        const response = await fetch('/api/load_project');
        const project = await response.json();
        
        if (project && project.source_playlist_id) {
            // Restore playlist info
            currentPlaylist = {
                id: project.source_playlist_id,
                name: project.source_playlist_name
            };
            
            playlistIdInput.value = project.source_playlist_id;
            
            // Restore anchors
            if (project.anchors && project.anchors.length > 0) {
                anchors = project.anchors;
                renderAnchors();
            }
            
            // Restore sequenced tracks
            if (project.sequenced_tracks && project.sequenced_tracks.length > 0) {
                sequencedTracks = project.sequenced_tracks;
                currentTracks = project.sequenced_tracks;
                
                // Re-fetch playlist to get all track data
                await fetchPlaylist();
                
                // Display restored sequence
                displaySequence(sequencedTracks);
            }
        }
    } catch (error) {
        console.error('Failed to load project:', error);
    }
}

async function fetchPlaylist() {
    const playlistId = playlistIdInput.value.trim();
    
    if (!playlistId) {
        showError('Please enter a playlist ID');
        return;
    }
    
    try {
        fetchBtn.disabled = true;
        fetchBtn.textContent = 'Loading...';
        
        const response = await fetch('/api/fetch_playlist', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ playlist_id: playlistId })
        });
        
        const data = await response.json();
        
        if (!response.ok) {
            throw new Error(data.error || 'Failed to fetch playlist');
        }
        
        currentPlaylist = data;
        currentTracks = data.tracks;
        
        playlistName.textContent = data.name;
        trackCount.textContent = data.total_tracks;
        playlistInfo.style.display = 'block';
        
        sequenceBtn.disabled = false;
        
        showSuccess(`Loaded ${data.total_tracks} tracks from "${data.name}"`);
    } catch (error) {
        showError(error.message);
    } finally {
        fetchBtn.disabled = false;
        fetchBtn.textContent = 'Fetch Playlist';
    }
}

function addAnchor() {
    const songName = anchorSongName.value.trim();
    const hours = parseInt(anchorHours.value) || 0;
    const minutes = parseInt(anchorMinutes.value) || 0;
    const seconds = parseInt(anchorSeconds.value) || 0;
    
    if (!songName) {
        showError('Please enter a song name');
        return;
    }
    
    const totalSeconds = hours * 3600 + minutes * 60 + seconds;
    
    if (totalSeconds === 0 && anchors.length > 0) {
        showError('Anchor offset must be greater than 0');
        return;
    }
    
    anchors.push({
        song_name: songName,
        time_offset_seconds: totalSeconds
    });
    
    renderAnchors();
    
    // Clear inputs
    anchorSongName.value = '';
    anchorHours.value = '0';
    anchorMinutes.value = '0';
    anchorSeconds.value = '0';
    
    showSuccess(`Added anchor: ${songName}`);
}

function renderAnchors() {
    anchorsList.innerHTML = '';
    
    anchors.forEach((anchor, index) => {
        const div = document.createElement('div');
        div.className = 'anchor-item';
        
        const info = document.createElement('div');
        info.className = 'anchor-info';
        
        const songDiv = document.createElement('div');
        songDiv.className = 'anchor-song';
        songDiv.textContent = anchor.song_name;
        
        const timeDiv = document.createElement('div');
        timeDiv.className = 'anchor-time';
        const timeStr = formatSeconds(anchor.time_offset_seconds);
        timeDiv.textContent = index === 0 
            ? `${timeStr} from start`
            : `${timeStr} after previous anchor`;
        
        info.appendChild(songDiv);
        info.appendChild(timeDiv);
        
        const removeBtn = document.createElement('button');
        removeBtn.className = 'remove-anchor';
        removeBtn.textContent = 'Remove';
        removeBtn.onclick = () => removeAnchor(index);
        
        div.appendChild(info);
        div.appendChild(removeBtn);
        anchorsList.appendChild(div);
    });
}

function removeAnchor(index) {
    anchors.splice(index, 1);
    renderAnchors();
}

function clearAnchors() {
    if (anchors.length === 0) return;
    
    if (confirm('Clear all anchors?')) {
        anchors = [];
        renderAnchors();
    }
}

async function generateSequence() {
    if (!currentTracks || currentTracks.length === 0) {
        showError('Please load a playlist first');
        return;
    }
    
    try {
        sequenceBtn.disabled = true;
        sequenceBtn.textContent = 'Generating...';
        
        const response = await fetch('/api/sequence_playlist', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                tracks: currentTracks,
                anchors: anchors
            })
        });
        
        const data = await response.json();
        
        if (!response.ok) {
            throw new Error(data.error || 'Failed to sequence playlist');
        }
        
        sequencedTracks = data.tracks;
        displaySequence(sequencedTracks);
        
        uploadBtn.disabled = false;
        
        showSuccess('Sequence generated successfully!');
    } catch (error) {
        showError(error.message);
    } finally {
        sequenceBtn.disabled = false;
        sequenceBtn.textContent = 'Generate Sequence';
    }
}

function displaySequence(tracks) {
    sequencePlaceholder.style.display = 'none';
    sequenceContainer.style.display = 'block';
    
    // Calculate total duration
    const total = tracks.reduce((sum, t) => sum + t.duration_ms, 0);
    totalDuration.textContent = formatMilliseconds(total);
    
    // Render tracks
    tracksList.innerHTML = '';
    
    tracks.forEach((track, index) => {
        const div = document.createElement('div');
        div.className = 'track-item';
        div.draggable = true;
        div.dataset.index = index;
        
        // Check if this is an anchor track
        const isAnchor = anchors.some(a => a.song_name.toLowerCase() === track.name.toLowerCase());
        if (isAnchor) {
            div.classList.add('anchor-track');
        }
        
        const number = document.createElement('div');
        number.className = 'track-number';
        number.textContent = `${index + 1}.`;
        
        const info = document.createElement('div');
        info.className = 'track-info';
        
        const name = document.createElement('div');
        name.className = 'track-name';
        name.textContent = track.name;
        
        const artist = document.createElement('div');
        artist.className = 'track-artist';
        artist.textContent = track.artist;
        
        info.appendChild(name);
        info.appendChild(artist);
        
        const time = document.createElement('div');
        time.className = 'track-time';
        time.textContent = formatSeconds(track.cumulative_start_time || 0);
        
        div.appendChild(number);
        div.appendChild(info);
        div.appendChild(time);
        
        // Drag and drop
        div.addEventListener('dragstart', handleDragStart);
        div.addEventListener('dragover', handleDragOver);
        div.addEventListener('drop', handleDrop);
        div.addEventListener('dragend', handleDragEnd);
        
        tracksList.appendChild(div);
    });
}

let draggedElement = null;

function handleDragStart(e) {
    draggedElement = this;
    this.classList.add('dragging');
    e.dataTransfer.effectAllowed = 'move';
}

function handleDragOver(e) {
    if (e.preventDefault) {
        e.preventDefault();
    }
    e.dataTransfer.dropEffect = 'move';
    return false;
}

function handleDrop(e) {
    if (e.stopPropagation) {
        e.stopPropagation();
    }
    
    if (draggedElement !== this) {
        const fromIndex = parseInt(draggedElement.dataset.index);
        const toIndex = parseInt(this.dataset.index);
        
        // Reorder array
        const item = sequencedTracks.splice(fromIndex, 1)[0];
        sequencedTracks.splice(toIndex, 0, item);
        
        // Update cumulative times
        updateCumulativeTimes();
        
        // Re-render
        displaySequence(sequencedTracks);
        
        // Save to database
        saveManualOrder();
    }
    
    return false;
}

function handleDragEnd() {
    this.classList.remove('dragging');
}

function updateCumulativeTimes() {
    let cumulative = 0;
    sequencedTracks.forEach(track => {
        track.cumulative_start_time = cumulative;
        cumulative += track.duration_ms / 1000;
    });
}

async function saveManualOrder() {
    try {
        await fetch('/api/save_manual_order', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                tracks: sequencedTracks,
                anchors: anchors
            })
        });
    } catch (error) {
        console.error('Failed to save order:', error);
    }
}

async function uploadPlaylist() {
    const name = newPlaylistName.value.trim();
    
    if (!name) {
        showError('Please enter a playlist name');
        return;
    }
    
    if (!sequencedTracks || sequencedTracks.length === 0) {
        showError('No tracks to upload');
        return;
    }
    
    try {
        uploadBtn.disabled = true;
        uploadBtn.textContent = 'Creating...';
        
        const response = await fetch('/api/create_playlist', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                name: name,
                tracks: sequencedTracks
            })
        });
        
        const data = await response.json();
        
        if (!response.ok) {
            throw new Error(data.error || 'Failed to create playlist');
        }
        
        uploadResult.className = 'upload-result success';
        uploadResult.innerHTML = `
            ✓ Playlist created successfully!<br>
            <a href="${data.url}" target="_blank">Open in Spotify</a>
        `;
        uploadResult.style.display = 'block';
        
        showSuccess('Playlist uploaded to Spotify!');
    } catch (error) {
        showError(error.message);
    } finally {
        uploadBtn.disabled = false;
        uploadBtn.textContent = 'Create Playlist';
    }
}

// Utility functions
function formatSeconds(seconds) {
    const h = Math.floor(seconds / 3600);
    const m = Math.floor((seconds % 3600) / 60);
    const s = Math.floor(seconds % 60);
    
    if (h > 0) {
        return `${h}:${m.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')}`;
    }
    return `${m}:${s.toString().padStart(2, '0')}`;
}

function formatMilliseconds(ms) {
    return formatSeconds(Math.floor(ms / 1000));
}

function showError(message) {
    errorToast.textContent = '✗ ' + message;
    errorToast.style.display = 'block';
    setTimeout(() => {
        errorToast.style.display = 'none';
    }, 4000);
}

function showSuccess(message) {
    successToast.textContent = '✓ ' + message;
    successToast.style.display = 'block';
    setTimeout(() => {
        successToast.style.display = 'none';
    }, 3000);
}
