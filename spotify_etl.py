import os
import pandas as pd
from dotenv import load_dotenv
import spotipy
from spotipy.oauth2 import SpotifyOAuth

load_dotenv()


def spotify_etl():
    liked_tracks = get_all_saved_tacks()
    playlists = get_all_playlists()
    playlist_tracks, playlists_cleaned, playlist_track_junction = (
        get_all_playlist_songs(playlists)
    )
    tracks_master = pd.concat([liked_tracks, playlist_tracks], axis=0)
    tracks_master = tracks_master.loc[~tracks_master.index.duplicated(keep="first"), :]
    print("done")


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
    tracks_df = tracks_df.set_index("id")
    tracks_df = tracks_df.drop(
        columns=["disc_number", "preview_url", "type", "is_local", "is_playable"],
        axis=1,
    )

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

    # Get current user's ID
    current_user = sp.current_user()
    user_id = current_user["id"]

    results = sp.current_user_playlists(limit=50)
    if results is None:
        print("Error retrieving all playlists")
        return None
    playlists = []

    while results["next"]:
        for item in results["items"]:
            # Only include playlists created by the current user
            if item["owner"]["id"] == user_id:
                playlists.append(item)

        results = sp.next(results)

    for item in results["items"]:
        # Only include playlists created by the current user
        if item["owner"]["id"] == user_id:
            playlists.append(item)

    playlists_df = pd.DataFrame(playlists)
    playlists_df = playlists_df.set_index("id")
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
        results = sp.playlist_tracks(row.Index, limit=100)
        while results:
            # Add track to master track list with playlist_id
            tracks.extend(
                [{**item, "playlist_id": row.Index} for item in results["items"]]
            )

            if results["next"]:
                results = sp.next(results)
            else:
                break

    playlist_tracks = pd.DataFrame(tracks)

    # Extract track_id from nested track object to top level
    playlist_tracks["track_id"] = playlist_tracks["track"].apply(
        lambda x: x.get("id") if isinstance(x, dict) else None
    )

    playlist_track_junction = playlist_tracks.drop(
        columns=["is_local", "primary_color", "track", "video_thumbnail"]
    )

    playlist_tracks = playlist_tracks["track"].apply(pd.Series)
    playlist_tracks = playlist_tracks.set_index("id")
    playlist_tracks = playlist_tracks.drop(
        columns=["disc_number", "preview_url", "type", "is_local"],
        axis=1,
    )

    playlists = playlists.drop(columns=["tracks"])

    return playlist_tracks, playlists, playlist_track_junction


if __name__ == "__main__":
    spotify_etl()
