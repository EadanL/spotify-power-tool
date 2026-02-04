track_schema = (
    "CREATE TABLE IF NOT EXISTS tracks "
    "("
    "id VARCHAR PRIMARY KEY, "
    "name VARCHAR, "
    "artist_ids VARCHAR[], "
    "album_id VARCHAR, "
    "track_number INTEGER, "
    "duration_ms INTEGER, "
    "popularity INTEGER, "
    "explicit BOOLEAN, "
    "available_markets VARCHAR[], "
    "external_urls VARCHAR, "
    "liked BOOLEAN,"
    ")"
)

playlists_schema = (
    "CREATE TABLE IF NOT EXISTS playlists "
    "("
    "id VARCHAR PRIMARY KEY, "
    "collaborative BOOLEAN, "
    "description VARCHAR, "
    "external_urls VARCHAR, "
    "name VARCHAR, "
    "public BOOLEAN"
    ")"
)

playlist_track_junction_schema = (
    "CREATE TABLE IF NOT EXISTS playlist_track_junction "
    "("
    "playlist_id VARCHAR, "
    "track_id VARCHAR, "
    "added_at DATE, "
    "added_by VARCHAR, "
    "PRIMARY KEY (playlist_id, track_id)"
    ")"
)

albums_schema = (
    "CREATE TABLE IF NOT EXISTS albums "
    "("
    "id VARCHAR PRIMARY KEY, "
    "name VARCHAR, "
    "artists VARCHAR[], "
    "available_markets VARCHAR[], "
    "external_urls VARCHAR, "
    "release_date VARCHAR, "
    "total_tracks INTEGER,"
    ")"
)

artists_schema = (
    "CREATE TABLE IF NOT EXISTS artists"
    "("
    "id VARCHAR PRIMARY KEY, name VARCHAR, external_urls VARCHAR,"
    ")"
)
