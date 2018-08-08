import sys
import json
from math import floor
import numpy as np
import spotipy
import spotipy.util as util
import pandas as pd
from collections import OrderedDict
from datetime import datetime
import calendar

class sfilt():
    def __init__(self, limit, token):
        if token:
            self.sp = spotipy.Spotify(auth=token)
            self.user_id = self.sp.me()['id']
            self.limit = limit
            self.done = False

    def get_chart_playlists(self):
        charts = self.sp.user_playlists('spotifycharts')
        print(charts)

    def get_viral_tracks(self, viral_50_playlist_ids):
        viral_tracks_ids = []
        for playlist_id in viral_50_playlist_ids:
            tracks = self.sp.user_playlist_tracks('spotifycharts', playlist_id=playlist_id)
            viral_tracks_ids += [track['track']['id'] for track in tracks['items'] if track['track']['popularity'] < 100]
            sys.stdout.write("Found {0: >3d} viral tracks.\r".format(len(viral_tracks_ids)))
            sys.stdout.flush()
        return viral_tracks_ids

    def filter_tracks(self, input_tracks, stop_tracks):
        unique_tracks = []
        for track in input_tracks:
            if track not in stop_tracks and track not in unique_tracks:
                unique_tracks.append(track)
        
        print("Found {} unique tracks".format(len(unique_tracks)))
        return unique_tracks

    def get_recommendations(self, seed_track_ids):
        rec_tracks_ids = []
        for idx in range(floor(len(seed_track_ids)/5)): # split the lists into 5 track subsets
            tracks = self.sp.recommendations(seed_tracks=seed_track_ids[idx*5:idx*5+5], limit=25)
            track_ids = [track_id['id'] for track_id in tracks['tracks']]
            filtered_track_ids = filter(lambda track_id : track_id not in rec_tracks_ids or track_id not in seed_track_ids, track_ids)
            rec_tracks_ids += filtered_track_ids
            sys.stdout.write("Added {0:d} new and unique recommended tracks...\r".format(len(rec_tracks_ids)))
            sys.stdout.flush()
            if len(rec_tracks_ids) + len(seed_track_ids) > self.limit:
                self.done = True
                print("\nTrack limit reached! [{0:d}]".format(self.limit))
                break

        print("Found total of {0:d} new and unique recommended tracks.".format(len(rec_tracks_ids) + len(seed_track_ids)))
        return rec_tracks_ids

    def order_tracks_by_features(self, track_ids):
        feature_vectors = []
        distance_list = []
        track_id_list = []
        track_artist_list = []
        track_name_list = []
        n_af_tracks = 0

        for idx in range(floor(len(track_ids)/50)):
            track_ids_set = track_ids[idx*50:idx*50+50]
            track_audio_features = self.sp.audio_features(track_ids_set)
            track_objects = self.sp.tracks(track_ids_set)['tracks']

            for af, to in zip(track_audio_features, track_objects):
                if af != None:
                    n_af_tracks += 1
                    sys.stdout.write("Found audio features for {} tracks.\r".format(n_af_tracks))
                    sys.stdout.flush()
                    fv = [af['danceability'], af['energy'], af['key']/11, 10**(af['loudness']/20), 
                        af['mode'], af['speechiness'], af['acousticness'], af['instrumentalness'], 
                        af['liveness'], af['valence']] # af['tempo']-120
                    feature_vectors.append(fv)
                    track_id_list.append(af['id'])
                    track_name_list.append(to['name'])
                    track_artist_list.append(to['album']['artists'][0]['name'])
        
        # pick track at random to start the list
        start_idx = np.random.randint(0, len(feature_vectors))

        # measure the distance 
        distances = [np.linalg.norm(np.array(feature_vectors[start_idx])-np.array(fv)) for fv in feature_vectors]

        # save output data for analysis - add in feature vector values later
        database = OrderedDict({'name' : track_name_list, 'artist' : track_artist_list, 'distance' : distances, 'id' : track_id_list})
        dataframe = pd.DataFrame(database)
        dataframe.sort_values(by=['distance'])
        dataframe.to_csv("sfilt.csv", sep=',')

        sorted_track_ids = [x for _,x in sorted(zip(distances, track_id_list))]

        return sorted_track_ids   

    def generate_playlist_name():
        t = datetime.today()
        playlist_title = 'sfilt: Top 50 Viral {} {} {}'.format(calendar.month_name[t.month], t.day, t.year)
        
        return playlist_title

    def order_tracks_by_popularity(self, track_ids):
        popularity_list = []
        track_id_list = []

        for idx in range(floor(len(track_ids)/50)):
            track_ids_set = track_ids[idx*50:idx*50+50]
            track_objects = self.sp.tracks(track_ids_set)['tracks']
            popularity_list += [track['popularity'] for track in track_objects]
            track_id_list  += [track['id'] for track in track_objects]

        sorted_track_ids = [x for _,x in sorted(zip(popularity_list, track_id_list))]
        return sorted_track_ids        
        
    def add_tracks_to_playlist(self, playlist_name, track_ids):
        # create new artist/engineer/producer playlist
        playlist_id = self.sp.user_playlist_create(self.user_id, playlist_name)['id']
        for idx in range(floor(len(track_ids)/50)+1):
            track_ids_set = track_ids[idx*50:idx*50+50]
            self.sp.user_playlist_add_tracks(self.user_id, playlist_id, track_ids_set)
        print("Saved {0:d} new tracks to an sfilt playlist.".format(len(track_ids)))

keys = json.load(open('keys.json'))
username = ''
scope = 'playlist-modify-public user-top-read'
token = util.prompt_for_user_token(username, scope, client_id=keys['client_id'], 
                                    client_secret=keys['client_secret'], redirect_uri=keys['redirect_uri'])

if __name__ == '__main__':
    sfilt = sfilt(500, token)
    viral_50 = json.load(open('viral_50.json'))
    viral_50_tracks = sfilt.get_viral_tracks(viral_50.values())
    viral_50_global = sfilt.get_viral_tracks(['37i9dQZEVXbKuaTI1Z1Afx', '37i9dQZEVXbMDoHDwVN2tF'])
    viral_50_unique = sfilt.filter_tracks(viral_50_tracks, viral_50_global)
    viral_50_unique_sorted = sfilt.order_tracks_by_features(viral_50_unique)
    playlist_name = generate_playlist_name()
    sfilt.add_tracks_to_playlist(playlist_name, viral_50_unique_sorted)


