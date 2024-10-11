
import os
import sys
from mutagen.mp3 import MP3
from utils import Utils

class Mp3Utils(Utils):
    """    Various MP3 utils    """
    def __init__(self):
        Utils.__init__(self)

        self.mp3_tags = {
                         "TIT2": "title",
                         "TPE1": "artist",
                         "TALB": "album",
                         "TRCK": "track",
                         "TCON": "genre"
                        }

    def get_mp3_data_per_dir(self, directory, recurse=0):
        """return all mp3 data for a given directory"""
        
        mp3_data = []
        for files in self.list_mp3_files(directory, recurse):
            mp3_data.append(self.get_mp3_data(files[0], files[1]))
            
        return mp3_data


    def list_mp3_files(self, directory, recurse=0):
        """return all mp3 files, as list of tuples of (filename,directory)"""
        mp3_files = []

        # allow for command line string passed
        recurse = int(recurse)

        if recurse:
            for root, dirs, files in os.walk(directory):
                for file in files:
                    if file.lower().endswith('.mp3'):
                        mp3_files.append((file, root))
        else:
            for file in os.listdir(directory):
                if file.lower().endswith('.mp3'):
                    mp3_files.append((file, directory))

        return mp3_files


    def get_mp3_data(self, mp3_file, directory):
        """return data for an mp3 file (artist, track, duration in secs) """
    
        audio = MP3(os.path.join(directory, mp3_file))
        mp3_data = {}
        for tag in self.mp3_tags:
            mp3_data[self.mp3_tags[tag]] = audio.get(tag, ["UNK"])[0]
        
        # special processing for date (TDRC is newer and might contain datetime data, TYER is just year)
        mp3_data["year"] = str(audio.get("TDRC", audio.get("TYER", ["UNK"]))[0]).split("-")[0]


        mp3_data["duration"] = round(audio.info.length)
        mp3_data["file"] = mp3_file
        mp3_data["dir"] = directory

        return mp3_data



if __name__ == '__main__':
    utils = Mp3Utils()._run(sys.argv)
