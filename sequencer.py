"""
Time-sequencing algorithm for playlist generation.
Places anchor songs at specified time offsets and fills gaps with remaining tracks.
"""
import random
from typing import List, Dict, Any, Tuple


class SequencerError(Exception):
    """Custom exception for sequencing errors."""
    pass


class PlaylistSequencer:
    TOLERANCE_SECONDS = 5  # ±5 seconds tolerance
    DEFAULT_CROSSFADE_SECONDS = 5
    
    def __init__(self, tracks: List[Dict[str, Any]], crossfade_seconds: float = None):
        """
        Initialize sequencer with source tracks.
        
        Args:
            tracks: List of track dictionaries from Spotify
            crossfade_seconds: Overlap between consecutive tracks in seconds.
                               Defaults to DEFAULT_CROSSFADE_SECONDS.
        """
        self.source_tracks = tracks.copy()
        self.available_tracks = tracks.copy()
        self.crossfade_seconds = crossfade_seconds if crossfade_seconds is not None else self.DEFAULT_CROSSFADE_SECONDS
    
    def _effective_duration_s(self, track: Dict[str, Any]) -> float:
        """Return the time a track occupies in the timeline accounting for crossfade.
        
        Every track except the very last one in the playlist starts fading out
        `crossfade_seconds` before its natural end, so the next track begins
        earlier.  For sequencing purposes each track advances the clock by
        `duration - crossfade`.
        """
        raw = track['duration_ms'] / 1000
        return max(raw - self.crossfade_seconds, 1.0)
    
    def sequence_playlist(self, anchors: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Create a sequenced playlist with anchor songs at specified time offsets.
        
        Args:
            anchors: List of anchor specifications:
                [
                    {"song_name": str, "time_offset_seconds": int},
                    ...
                ]
                First anchor time is absolute from start.
                Subsequent anchors are relative to previous anchor.
        
        Returns:
            List of tracks in sequence with metadata
            
        Raises:
            SequencerError: If anchor song not found or timing impossible
        """
        if not anchors:
            # No anchors, return shuffled tracks
            result = self.source_tracks.copy()
            random.shuffle(result)
            return self._add_metadata(result)
        
        # Reset available tracks
        self.available_tracks = self.source_tracks.copy()
        
        # Find and reserve anchor tracks
        anchor_tracks = []
        for i, anchor_spec in enumerate(anchors):
            track = self._find_and_remove_track(anchor_spec['song_name'])
            if not track:
                raise SequencerError(f"Anchor song '{anchor_spec['song_name']}' not found in playlist")
            
            # Calculate absolute time offset
            if i == 0:
                # First anchor: time from playlist start
                absolute_time = anchor_spec['time_offset_seconds']
            else:
                # Subsequent anchors: relative to previous anchor start time
                absolute_time = anchor_tracks[-1]['absolute_start_time'] + anchor_spec['time_offset_seconds']
            
            anchor_tracks.append({
                'track': track,
                'absolute_start_time': absolute_time,
                'specification': anchor_spec
            })
        
        # Build sequenced playlist
        sequenced = []
        current_time = 0
        
        for i, anchor_info in enumerate(anchor_tracks):
            target_time = anchor_info['absolute_start_time']
            anchor_track = anchor_info['track']
            
            # Fill gap before this anchor
            gap_duration = target_time - current_time
            if gap_duration < 0:
                raise SequencerError(
                    f"Impossible timing: anchor '{anchor_track['name']}' at {target_time}s "
                    f"but previous section ends at {current_time}s"
                )
            
            if gap_duration > 0:
                filler_tracks, actual_duration = self._fill_gap(gap_duration)
                sequenced.extend(filler_tracks)
                current_time += actual_duration
            
            # Check timing tolerance
            time_diff = abs(current_time - target_time)
            if time_diff > self.TOLERANCE_SECONDS:
                raise SequencerError(
                    f"Cannot place anchor '{anchor_track['name']}' at {target_time}s "
                    f"(would be at {current_time}s, exceeds ±{self.TOLERANCE_SECONDS}s tolerance)"
                )
            
            # Add anchor track
            sequenced.append(anchor_track)
            current_time = target_time + self._effective_duration_s(anchor_track)
        
        # Add remaining tracks after last anchor
        if self.available_tracks:
            random.shuffle(self.available_tracks)
            sequenced.extend(self.available_tracks)
        
        return self._add_metadata(sequenced)
    
    def _find_and_remove_track(self, song_name: str) -> Dict[str, Any]:
        """Find a track by name and remove it from available tracks."""
        song_name_lower = song_name.lower().strip()
        
        for i, track in enumerate(self.available_tracks):
            if track['name'].lower().strip() == song_name_lower:
                return self.available_tracks.pop(i)
        
        return None
    
    def _fill_gap(self, target_duration_seconds: float) -> Tuple[List[Dict[str, Any]], float]:
        """
        Fill a time gap by selecting tracks whose combined duration best matches the target.

        Uses dynamic programming (subset-sum) to find an optimal combination of tracks
        rather than random selection, so that anchors reliably land at their target times.

        Args:
            target_duration_seconds: Desired duration in seconds

        Returns:
            Tuple of (list of tracks, actual duration in seconds)
        """
        if not self.available_tracks or target_duration_seconds <= 0:
            return [], 0.0

        tolerance_s = self.TOLERANCE_SECONDS
        target_s = int(round(target_duration_seconds))

        # Track durations in whole seconds, accounting for crossfade overlap
        durations_s = [max(1, int(round(self._effective_duration_s(t)))) for t in self.available_tracks]
        n = len(durations_s)
        total_available_s = sum(durations_s)

        # If every available track combined can't reach the lower tolerance bound,
        # use them all — it's the closest we can get
        if total_available_s <= target_s - tolerance_s:
            selected = self.available_tracks[:]
            self.available_tracks = []
            random.shuffle(selected)
            return selected, sum(self._effective_duration_s(t) for t in selected)

        # DP upper bound: target + tolerance, capped by total available
        max_sum = min(target_s + tolerance_s, total_available_s)

        # Subset-sum DP: dp[s] == 1 iff sum s is achievable using a subset of tracks
        dp = bytearray(max_sum + 1)
        dp[0] = 1
        # Backtracking table: choice[s] = (track_index, previous_sum)
        choice = [None] * (max_sum + 1)

        for i in range(n):
            dur = durations_s[i]
            if dur > max_sum:
                continue
            # Iterate in reverse so each track is used at most once
            for s in range(max_sum, dur - 1, -1):
                if not dp[s] and dp[s - dur]:
                    dp[s] = 1
                    choice[s] = (i, s - dur)

        # Find the achievable sum closest to the target
        best_sum = None
        best_diff = float('inf')
        for s in range(max_sum + 1):
            if dp[s]:
                diff = abs(s - target_s)
                if diff < best_diff:
                    best_diff = diff
                    best_sum = s

        if best_sum is None or best_sum == 0:
            return [], 0.0

        # Backtrack to identify which tracks were selected
        selected_indices = set()
        s = best_sum
        while choice[s] is not None:
            idx, prev_s = choice[s]
            selected_indices.add(idx)
            s = prev_s

        # Partition into selected and remaining
        selected = []
        remaining = []
        for i, track in enumerate(self.available_tracks):
            if i in selected_indices:
                selected.append(track)
            else:
                remaining.append(track)

        self.available_tracks = remaining
        random.shuffle(selected)  # Randomise order within the filled segment

        actual_duration_s = sum(self._effective_duration_s(t) for t in selected)
        return selected, actual_duration_s
    
    def _add_metadata(self, tracks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Add cumulative time metadata to tracks, accounting for crossfade."""
        cumulative_time = 0
        result = []
        last_index = len(tracks) - 1
        
        for i, track in enumerate(tracks):
            track_with_meta = track.copy()
            track_with_meta['cumulative_start_time'] = cumulative_time
            track_with_meta['crossfade_seconds'] = self.crossfade_seconds
            if i < last_index:
                cumulative_time += self._effective_duration_s(track)
            else:
                # Last track plays its full duration (no crossfade into nothing)
                cumulative_time += track['duration_ms'] / 1000
            result.append(track_with_meta)
        
        return result
