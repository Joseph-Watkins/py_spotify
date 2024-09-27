# Utils for mp3/spotify
# expects following env vars:
# SPOTIPY_CLIENT_ID=<>
# SPOTIPY_CLIENT_SECRET=<>
# SPOTIPY_USERNAME=<>

import glob
import json
import os
import sys
import time
import traceback


from utils import Utils

from mutagen.mp3 import MP3
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


    def mp3_to_spotify(self, mp3_path, duration_tolerance=5):
        """pass path containing mp3 files to find spotify ids for, and optional duration tolerance as % (default 5)"""

        duration_tolerance = int(duration_tolerance) if duration_tolerance else 5

        output_file = os.path.join(mp3_path, "spotify.txt")
        with open(output_file, "w") as f:
            f.write("artist~track~mp3_duration~spotify_duration~uri~file\n")
            for file in glob.glob(os.path.join(mp3_path,'*.mp3') ):
                print(f"Processing {file}")
                data = self.get_mp3_data(file)
                if data:
                    # remove words with ' in them
                    mp3_track = " ".join([m for m in data["mp3_track"].split() if "'" not in m])

                    # search in spotify
                    # need highest popularity track with specified duration tolerance
                    results = self.spotify_search(data["mp3_artist"], mp3_track, 
                                                  True, duration_tolerance, data["mp3_duration"])
                    if results:
                        duration = results[0]['sp_duration']
                        uri = results[0]['sp_uri']
                    else:
                        duration = ""
                        uri = "NOT FOUND"

                    f.write(f"{data['mp3_artist']}~{data['mp3_track']}~{data['mp3_duration']}~{duration}~{uri}~{file}\n")
                else:
                    f.write(f"NOT FOUND~~~~~{file}\n")
        print(f"Data written to {output_file}")

    def get_mp3_data(self, mp3_file):
        """return data for an mp3 file (artist, track, duration in secs) """

        audio = MP3(mp3_file)
        try:
            mp3_data = {
                "mp3_artist": audio['TPE1'].text[0], 
                "mp3_track": audio["TIT2"].text[0], 
                "mp3_duration": round(audio.info.length)
            }
        except:
            mp3_data = None

        return mp3_data
        

    def spotify_search(self, artist, track, most_popular=True, duration_tolerance=0, duration=0):
        """return most popular or all match(es) from spotify for artist and track and optionaly check duration_tolerance (as %) given duration"""

        most_popular = False if most_popular in (False, 0, "0") else True
        duration_tolerance = int(duration_tolerance)/100 if duration_tolerance else 0
        duration = int(duration) if duration else 0
        search_str = "artist:{0} track:{1}".format(artist, track)
        return_results = []
        result = self.sp.search(q=search_str, type='track', market='GB')
        max_popularity = 0
        for item in result['tracks']['items']:
            sp_duration = round(item['duration_ms']/1000)
            item_data = {"sp_artist": item['album']['artists'][0]['name'],
                         "sp_album": item['album']['name'],
                         "sp_track": item['name'],
                         "sp_popularity": item['popularity'],
                         "sp_uri": item['uri'],
                         "sp_duration": sp_duration
                        }
            if duration_tolerance and (abs(duration - sp_duration) / duration > duration_tolerance):
                continue
            if most_popular and (item['popularity'] < max_popularity):
                continue
            max_popularity = item['popularity']
            return_results.append(item_data)
        return return_results

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
