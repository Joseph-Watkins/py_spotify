# Utils for mp3/spotify
# expects following env vars:
# SPOTIPY_CLIENT_ID=<>
# SPOTIPY_CLIENT_SECRET=<>
# SPOTIPY_USERNAME=<>

from difflib import SequenceMatcher
import glob
import json
import os
import sys
import time
import traceback

from utils import Utils
from mp3_utils import Mp3Utils

from spotipy.oauth2 import SpotifyClientCredentials
from spotipy.oauth2 import SpotifyOAuth
import spotipy


class MP3SpotifyUtils(Utils):
    """    Various MP3 utils    """
    def __init__(self):
        Utils.__init__(self)

        self.username = os.environ['SPOTIPY_USERNAME']
        
        scope = ['user-library-read', 'playlist-modify-public', 'playlist-modify-public']
        self.sp = spotipy.Spotify(auth_manager=SpotifyOAuth(client_id=os.environ['SPOTIPY_CLIENT_ID'],
                                               client_secret=os.environ['SPOTIPY_CLIENT_SECRET'],
                                               redirect_uri=os.environ.get('SPOTIPY_REDIRECT_URI', 'http://127.0.0.1:8888/callback'),
                                               scope=scope,
                                               open_browser=False))
                                               
        self.mp3_utils = Mp3Utils()


    def mp3_to_spotify(self, mp3_path, duration_tolerance=5):
        """pass path containing mp3 files to find spotify ids for, and optional duration tolerance as % (default 5)"""

        duration_tolerance = int(duration_tolerance) if duration_tolerance else 5

        output_file = os.path.join(mp3_path, "spotify.txt")
        with open(output_file, "w") as f:
            f.write("artist~title~mp3_duration~spotify_duration~sp_id~sp_id2~score~file~dir\n")
            all_data = self.mp3_utils.get_mp3_data_per_dir(mp3_path)
            for data in all_data:
                # remove words with ' in them
                title = " ".join([m for m in data["title"].split() if "'" not in m])

                # search in spotify
                # need highest popularity track with specified duration tolerance
                result = self.spotify_search(data["artist"], title, 
                                              True, duration_tolerance, data["duration"])
                if result:
                    print(f"result={result}")
                    duration = result['sp_duration']
                    id = result['sp_id']
                    id2 = result['sp_id2']
                    score = result['score']
                else:
                    duration = uri = id2 = score = "UNK"

                f.write(f"{data['artist']}~{data['title']}~{data['duration']}~{duration}~{id}~{id2}~{score}~{data['file']}~{data['dir']}\n")
        print(f"Data written to {output_file}")


    def spotify_search(self, artist, title, most_popular=True, duration_tolerance=0, duration=0):
        """return most popular or all match(es) from spotify for artist and title and optionaly check duration_tolerance (as %) given duration"""

        most_popular = False if most_popular in (False, 0, "0") else True
        duration_tolerance = int(duration_tolerance)/100 if duration_tolerance else 0
        duration = int(duration) if duration else 0
        search_str = "artist:{0} track:{1}".format(artist, title)
        result = self.sp.search(q=search_str, type='track', market='GB')
        max_popularity = 0

        return_result = {}
        for item in result['tracks']['items']:
            sp_duration = round(item['duration_ms']/1000)
            item_data = {"sp_artist": item['album']['artists'][0]['name'],
                         "sp_album": item['album']['name'],
                         "sp_track": item['name'],
                         "sp_popularity": item['popularity'],
                         "sp_id": item['id'],
                         "sp_duration": sp_duration
                        }
            if duration_tolerance and (abs(duration - sp_duration) / duration > duration_tolerance):
                continue
            if most_popular and (item['popularity'] < max_popularity):
                continue
            max_popularity = item['popularity']
            return_result = item_data

        if result:
            match_data = self.matching(title, artist, duration, result)
            if match_data:
                return_result['sp_id2'] = match_data['match_id']
                return_result['score'] = match_data['score']
            else:
                return_result['sp_id2'] = return_result['score'] = "UNK"
        
        return return_result
        
    def matching(self, title, artist, duration, results):
        """from claude"""
        
        duration_ms = duration * 1000
        
        # Score and rank the results
        scored_results = []
        for track in results['tracks']['items']:
            score = 0
            # Title similarity (0-1)
            title_similarity = SequenceMatcher(None, title.lower(), track['name'].lower()).ratio()
            score += title_similarity * 0.4  # 40% weight

            # Artist similarity (0-1)
            artist_similarity = SequenceMatcher(None, artist.lower(), track['artists'][0]['name'].lower()).ratio()
            score += artist_similarity * 0.3  # 30% weight

            # Duration similarity (0-1)
            duration_diff = abs(duration_ms - track['duration_ms'])
            duration_similarity = max(0, 1 - (duration_diff / duration_ms))
            score += duration_similarity * 0.2  # 20% weight

            # Popularity (0-1)
            popularity = track['popularity'] / 100
            score += popularity * 0.1  # 10% weight

            scored_results.append((score, track))

        # Sort by score (highest first)
        scored_results.sort(reverse=True, key=lambda x: x[0])

        # Return the best match
        best_match = scored_results[0][1]
        return {"match_id": best_match['id'], "score": round(scored_results[0][0],1)}


    def get_playlists(self):
        """return ids of all user playlists"""

        playlists = self.sp.user_playlists(self.username)

        for playlist in playlists['items']:
            print("{0}~{1}".format(playlist['name'], playlist['uri']))
            
    def get_playlist_tracks(self, playlist_id): 
        """ get all tracks in a playlist"""
        
        print("artist~track~duration(s)~uri")
        results = self.sp.playlist(playlist_id)
        for track in results['tracks']['items']:
            artist = track['track']['artists'][0]['name']
            track_name = track['track']['name'] 
            duration = int(track['track']['duration_ms']/1000)
            uri = track['track']['uri']
            print(f"{artist}~{track_name}~{duration}~{uri}")
            
    def get_liked_tracks(self): 
        """ get all liked tracks"""

        offset = 0
        limit = 50  # Adjust the limit based on your needs

        all_tracks = []
        while True:
            results = self.sp.current_user_saved_tracks(limit=limit, offset=offset)

            if not results['items']:
                break  # No more tracks

            all_tracks.extend(results['items'])
            offset += limit
            time.sleep(0.1)

        print("artist~track~duration(s)~uri")
        for item in all_tracks:
            track = item['track']
            artist = track['artists'][0]['name']
            track_name = track['name'] 
            duration = int(track['duration_ms']/1000)
            uri = track['uri']
            
            print(f"{artist}~{track_name}~{duration}~{uri}")

    def add_to_playlist(self, playlist_id, track_id):
        """ add track to playlist"""
        
        self.sp.playlist_add_items(playlist_id, [track_id])


if __name__ == '__main__':
    utils = MP3SpotifyUtils()._run(sys.argv)
