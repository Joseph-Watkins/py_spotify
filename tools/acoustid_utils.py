
import acoustid
import os
import sys

from utils import Utils

class AcoustidUtils(Utils):
    """    Various MP3 utils    """
    def __init__(self):
        Utils.__init__(self)

        self.api_key = os.environ['ACOUSTID_KEY']

    def get_acoustid_and_match(self, file_path):
        """get acoustid details for an mp3 file"""
        
        # Get fingerprint and duration of the audio file
        duration, fingerprint = acoustid.fingerprint_file(file_path)

        # Look up the AcoustID for the file
        results = acoustid.lookup(self.api_key, fingerprint, duration)
        
        if not results['results']:
            print("No match found on AcoustID.")
            return

        # Get the best result from AcoustID
        acoustid_id = results['results'][0]['id']
        print(f"AcoustID: {acoustid_id}, duration: {duration}")

        rec_match = self._get_best_recording_match(results)

    def _get_best_recording_match(self, results):
        
        # Get the best AcoustID match (usually the first result)
        best_acoustid_result = results['results'][0]
        
        # Check if there are recordings associated with this AcoustID
        if best_acoustid_result['recordings']:
            # Get the first recording (best match for the recording)
            best_recording = best_acoustid_result['recordings'][0]
            
            # Extract recording details
            title = best_recording['title']
            artist = best_recording['artists'][0]['name']
            duration = best_recording['duration']
            id = best_recording['id']
            
            print(f"Best Match - Title: {title}, Artist: {artist}, Duration: {duration}, MusicbrainzId={id}")
        else:
            print("No recordings found for the best AcoustID.")


if __name__ == '__main__':
    utils = AcoustidUtils()._run(sys.argv)
