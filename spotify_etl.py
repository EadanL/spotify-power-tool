import logging

import pandas as pd
import spotipy
from dotenv import load_dotenv
from spotipy.oauth2 import SpotifyOAuth

from motherduck_loader import DataFrameLoadingBuffer

load_dotenv()


# TODO: Explicitly define table schemas (maybe in a different file tho)
# TODO: Insert all dfs into db
def spotify_etl():
    logging.info("Retrieving all tracks from users 'liked songs'...")
    liked_tracks = get_all_saved_tacks()
    logging.info("Retrieving all playlists and playlist tracks...")
    playlists, playlist_tracks = get_playlists_and_tracks()
    logging.info("Splitting playlist tracks from playlist...")
    playlist_tracks, playlist_track_junction = split_playlist_track_data(
        playlist_tracks
    )

    # Combine all tracks into master DataFrame
    tracks_master = pd.concat([liked_tracks, playlist_tracks], axis=0)
    tracks_master = tracks_master.loc[~tracks_master.index.duplicated(keep="first"), :]
    tracks_master["liked"] = tracks_master["liked"].fillna(False)
    tracks_master = tracks_master.drop(columns=["track", "episode"])
    tracks_master = tracks_master.reset_index()

    logging.info("Splitting data into tracks, albums, artists tables...")
    tracks, albums, artists = split_track_album_artist(tracks_master)

    # Load data into MotherDuck
    loader = DataFrameLoadingBuffer("spotify_power_tools_raw", "tracks")
    # loader.apply_table_schema(duck_track_schema)
    loader.insert(tracks)
    loader.table_name("playlists")
    loader.insert(playlists)
    loader.table_name("albums")
    loader.insert(albums)
    loader.table_name("artists")
    loader.insert(artists)
    loader.table_name("playlist_tracks")
    loader.insert(playlist_track_junction)
    logging.info("Completed loading data into MotherDuck")


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
    tracks_df = tracks_df.assign(liked=True)

    return tracks_df


def get_all_playlists(sp: spotipy.Spotify) -> pd.DataFrame | None:
    """
    Retrieves all playlists created/saved by user

    :return: Dataframe containing all playlists data
    :rtype: DataFrame | None
    """

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


# TODO: Fill in docstring
def get_playlists_and_tracks() -> tuple[pd.DataFrame]:
    """
    Extracts all tracks from all playlists owned by user.

    :return:
    :rtype: tuple[DataFrame]
    """
    scope = [
        "user-library-read",
        "playlist-read-collaborative",
        "playlist-read-private",
    ]
    sp = spotipy.Spotify(auth_manager=SpotifyOAuth(scope=scope))
    playlists = get_all_playlists(sp)

    # Split tracks from playlists
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

    playlists = playlists.drop(columns=["tracks", "owner", "uri"])
    playlist_tracks = pd.DataFrame(tracks)

    return playlists, playlist_tracks


# TODO: Fill in docstring
def split_playlist_track_data(playlist_tracks: pd.DataFrame) -> tuple[pd.DataFrame]:
    # Extract track_id from nested track object to top level
    playlist_tracks["track_id"] = playlist_tracks["track"].apply(
        lambda x: x.get("id") if isinstance(x, dict) else None
    )

    playlist_track_junction = playlist_tracks.drop(
        columns=["is_local", "primary_color", "track", "video_thumbnail"]
    )
    playlist_track_junction["added_by"] = playlist_track_junction["added_by"].apply(
        lambda x: x.get("id") if isinstance(x, dict) else None
    )

    # Expand playlist track data from playlist data
    playlist_tracks = playlist_tracks["track"].apply(pd.Series)
    playlist_tracks = playlist_tracks.set_index("id")
    playlist_tracks = playlist_tracks.drop(
        columns=["disc_number", "preview_url", "type", "is_local"],
        axis=1,
    )

    return playlist_tracks, playlist_track_junction


# TODO: Fill in docstring
def split_track_album_artist(tracks: pd.DataFrame) -> tuple[pd.DataFrame]:
    # Create albums DataFrame
    albums = tracks["album"].apply(pd.Series)  # flatten dictionary structure
    albums = albums.drop(
        columns=[
            "is_playable",
            "release_date_precision",
            "type",
            "images",
            "uri",
            "href",
        ]
    )
    albums = albums.drop_duplicates(subset=["id"]).reset_index(drop=True)

    # Create artists DataFrame
    artists = tracks["artists"].copy()
    artists = artists.explode("artists")  # give each list entry its own row
    artists = pd.json_normalize(artists.tolist())  # flatten dictionary structure
    artists = artists.rename(columns={"external_urls.spotify": "external_urls"})
    artists = artists.drop(columns=["type", "uri", "href"])
    artists = artists.drop_duplicates(subset=["id"]).reset_index(drop=True)

    # Clean tracks DataFrame and leave album/artist IDs
    tracks["album_id"] = tracks["album"].apply(
        lambda x: x["id"] if isinstance(x, dict) else None
    )
    tracks["artist_ids"] = tracks["artists"].apply(
        lambda x: [artist["id"] for artist in x] if isinstance(x, list) else None
    )
    tracks = tracks.drop(columns=["album", "artists", "external_ids", "uri", "href"])

    # Extract Spotify URL from external_urls object
    for df in [tracks, albums]:
        df["external_urls"] = df["external_urls"].apply(
            lambda x: x.get("spotify") if isinstance(x, dict) and pd.notna(x) else None
        )

    return tracks, albums, artists


if __name__ == "__main__":
    spotify_etl()
