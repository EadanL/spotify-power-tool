import os
import pandas as pd
from dotenv import load_dotenv
import spotipy
from spotipy.oauth2 import SpotifyOAuth

load_dotenv()


def get_all_saved_tacks():
    scope = "user-library-read"
    sp = spotipy.Spotify(auth_manager=SpotifyOAuth(scope=scope))

    results = sp.current_user_saved_tracks(limit=50)
    tracks = []

    while results["next"]:
        for item in results["items"]:
            tracks.append(item["track"])

        results = sp.next(results)

    for item in results["items"]:
        tracks.append(item["track"])

    tracks_df = pd.DataFrame(tracks)
    tracks_df.set_index("id")
    tracks_df = tracks_df.drop(["disc_number", "preview_url", "type"], axis=1)

    return tracks_df


def get_all_playlists():
    scope = [
        "user-library-read",
        "playlist-read-collaborative",
        "playlist-read-private",
    ]
    sp = spotipy.Spotify(auth_manager=SpotifyOAuth(scope=scope))

    results = sp.current_user_playlists(limit=50)
    playlists = []

    while results["next"]:
        for item in results["items"]:
            playlist = sp.playlist(item["id"])
            playlists.append(playlist)

        results = sp.next(results)

    for item in results["items"]:
        playlist = sp.playlist(item["id"])
        playlists.append(playlist)

    playlists_df = pd.DataFrame(playlists)
    playlists_df.set_index("id")
    playlists_df = playlists_df.drop(
        ["images", "primary_color", "snapshot_id", "type"], axis=1
    )

    return playlists_df


if __name__ == "__main__":
    get_all_saved_tacks()
    get_all_playlists()
