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

playlist_schema = (
    "collaborative BOOLEAN, "
    "description VARCHAR, "
    "external_urls VARCHAR, "
    "name VARCHAR, "
    "public BOOLEAN, "
)

playlist_track_junction = (
    "playlist_id VARCHAR, track_id VARCHAR, added_at DATE, added_by VARCHAR"
)


albums_schema = (
    "id VARCHAR PRIMARY KEY, "
    "name VARCHAR, "
    "artists VARCHAR[], "
    "available_markets VARCHAR[], "
    "external_urls VARCHAR, "
    "release_date DATE, "
    "total_tracks INTEGER,"
)

artists_schema = "id VARCHAR PRIMARY KEY, name VARCHAR, external_urls VARCHAR,"
