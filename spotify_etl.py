import logging

import pandas as pd
import spotipy
from dotenv import load_dotenv
from spotipy.oauth2 import SpotifyOAuth

from motherduck_loader import DataFrameLoadingBuffer

load_dotenv()


def spotify_etl():
    """
    Main ETL pipeline for extracting Spotify data and loading it into MotherDuck.

    This function orchestrates the entire ETL process:
    1. Retrieves all saved tracks from user's "liked songs"
    2. Fetches all user-created playlists and their tracks
    3. Combines and deduplicates track data
    4. Splits normalized data into separate tables (tracks, albums, artists, playlist_tracks)
    5. Loads all data into MotherDuck database

    :raises ValueError: If MOTHERDUCK_TOKEN environment variable is not set
    :raises spotipy.SpotifyException: If Spotify API calls fail
    """
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
    Retrieves all tracks from user's "liked songs" library.

    Fetches tracks in batches of 50 and continues paginating through all results.
    Removes unnecessary columns like disc_number, preview_url, type, is_local, and is_playable.
    Adds a 'liked' column set to True for all retrieved tracks.

    :return: DataFrame with track data indexed by track ID, or None if retrieval fails
    :rtype: pd.DataFrame | None
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
    Retrieves all playlists created by the authenticated user.

    Filters playlists to only include those owned by the current user (excludes followed playlists).
    Fetches playlists in batches of 50 and paginates through all results.
    Removes unnecessary columns like images, primary_color, snapshot_id, and type.

    :param sp: Authenticated Spotify client instance
    :type sp: spotipy.Spotify
    :return: DataFrame with playlist data indexed by playlist ID, or None if retrieval fails
    :rtype: pd.DataFrame | None
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


def get_playlists_and_tracks() -> tuple[pd.DataFrame]:
    """
    Extracts all playlists and their associated tracks for the authenticated user.

    Creates a new Spotify client with playlist read scopes and retrieves all playlists
    created by the user. For each playlist, fetches all tracks in batches of 100,
    associating each track with its playlist_id. Cleans playlist data by removing
    unnecessary columns (tracks, owner, uri).

    :return: Tuple containing (playlists_df, playlist_tracks_df) where:
             - playlists_df: DataFrame of playlist metadata indexed by playlist ID
             - playlist_tracks_df: DataFrame of raw track data with playlist_id associations
    :rtype: tuple[pd.DataFrame, pd.DataFrame]
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


def split_playlist_track_data(playlist_tracks: pd.DataFrame) -> tuple[pd.DataFrame]:
    """
    Separates playlist track data into junction table and normalized track data.

    Extracts track IDs from nested track objects and creates a junction table
    mapping playlists to tracks (with added_at and added_by metadata).
    Expands nested track objects into flat track records and removes unnecessary columns.

    :param playlist_tracks: Raw DataFrame containing nested track objects and playlist metadata
    :type playlist_tracks: pd.DataFrame
    :return: Tuple containing (playlist_tracks_df, playlist_track_junction_df) where:
             - playlist_tracks_df: Normalized track data indexed by track ID
             - playlist_track_junction_df: Many-to-many relationship between playlists and tracks
    :rtype: tuple[pd.DataFrame, pd.DataFrame]
    """
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


def split_track_album_artist(tracks: pd.DataFrame) -> tuple[pd.DataFrame]:
    """
    Normalizes track data by splitting into separate tracks, albums, and artists tables.

    Creates three normalized DataFrames:
    1. Albums: Extracts and deduplicates album information from tracks
    2. Artists: Explodes artist arrays and deduplicates artist information
    3. Tracks: Keeps track metadata with foreign keys to albums (album_id) and artists (artist_ids array)

    Also extracts Spotify URLs from external_urls objects for tracks and albums.

    :param tracks: Combined DataFrame containing all track data with nested album and artist objects
    :type tracks: pd.DataFrame
    :return: Tuple containing (tracks_df, albums_df, artists_df) with normalized data
    :rtype: tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]
    """
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
