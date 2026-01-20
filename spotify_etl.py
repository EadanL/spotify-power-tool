import os
import pandas as pd
from dotenv import load_dotenv
import spotipy
from spotipy.oauth2 import SpotifyOAuth

load_dotenv()


def get_all_saved_tacks() -> pd.DataFrame | None:
    """
    Retrieves all tracks from users "liked songs"

    :return: DataFrame containing all saved tracks data
    :rtype: DataFrame | None
    """
    scope = "user-library-read"
    sp = spotipy.Spotify(auth_manager=SpotifyOAuth(scope=scope))

    results = sp.current_user_saved_tracks(limit=50)
    if results is None:
        print("Error retrieving all saved tracks")
        return None
    tracks = []

    while results and results["next"]:
        for item in results["items"]:
            tracks.append(item["track"])

        results = sp.next(results)

    for item in results["items"]:
        tracks.append(item["track"])

    tracks_df = pd.DataFrame(tracks)
    tracks_df.set_index("id")
    tracks_df = tracks_df.drop(["disc_number", "preview_url", "type"], axis=1)

    return tracks_df


def get_all_playlists() -> pd.DataFrame | None:
    """
    Retrieves all playlists created/saved by user

    :return: Dataframe containing all playlists data
    :rtype: DataFrame | None
    """
    scope = [
        "user-library-read",
        "playlist-read-collaborative",
        "playlist-read-private",
    ]
    sp = spotipy.Spotify(auth_manager=SpotifyOAuth(scope=scope))

    results = sp.current_user_playlists(limit=50)
    if results is None:
        print("Error retrieving all playlists")
        return None
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


def get_all_playlist_songs(playlists: pd.DataFrame) -> pd.DataFrame | None:
    scope = [
        "user-library-read",
        "playlist-read-collaborative",
        "playlist-read-private",
    ]
    sp = spotipy.Spotify(auth_manager=SpotifyOAuth(scope=scope))
    tracks = []
    for row in playlists.itertuples():
        results = sp.playlist_tracks(row.id, limit=100)
        while results:
            tracks.extend(results["items"])
            if results["next"]:
                results = sp.next(results)
            else:
                break

    tracks_df = pd.DataFrame(tracks)
    return tracks_df


if __name__ == "__main__":
    # get_all_saved_tacks()
    playlists = get_all_playlists()
    get_all_playlist_songs(playlists)
