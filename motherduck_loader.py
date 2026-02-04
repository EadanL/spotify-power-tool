import logging
import os

import duckdb
from dotenv import load_dotenv


class DataFrameLoadingBuffer:
    def __init__(
        self,
        database_name: str,
        table_name: str,
        chunk_size: int = 100_00,
    ):
        self.database_name = database_name
        self.table_name = table_name
        self.chunk_size = chunk_size
        self.conn = self.initialize_connection()
        self.total_inserted = 0

    def initialize_connection(self):
        logging.info("Connecting to MotherDuck...")
        motherduck_token = os.environ.get("MOTHERDUCK_TOKEN")
        if not motherduck_token:
            raise ValueError(
                "MotherDuck token required. Set the environment variable 'MOTHERDUCK_TOKEN'"
            )
        conn = duckdb.connect("md:")
        logging.info(f"Creating database {self.database_name} if it doesn't exist")
        conn.execute(f"CREATE DATABASE IF NOT EXISTS {self.database_name}")
        conn.execute(f"USE {self.database_name}")
        return conn

    def apply_table_schema(self, schema_sql):
        self.conn.execute(schema_sql)

    def insert(self, table):
        total_rows = len(table)
        for batch_start in range(0, total_rows, self.chunk_size):
            batch_end = min(batch_start + self.chunk_size, total_rows)
            chunk = table[batch_start : (batch_end - batch_start)]
            self.insert_chunk(chunk)
            logging.info(f"Inserted chunk {batch_start} to {batch_end}")
        self.total_inserted += total_rows
        logging.info(f"Total inserted: {self.total_inserted} rows")

    def insert_chunk(self, chunk):
        self.conn.register("buffer_table", chunk)
        # Get column names from the buffer table to match with target table
        columns = ", ".join(chunk.columns)

        # Determine conflict handling based on table type
        if self.table_name in ["tracks", "albums", "artists", "playlists"]:
            # Tables with id PRIMARY KEY - ignore on duplicate id
            insert_query = f"INSERT OR IGNORE INTO {self.table_name} ({columns}) SELECT {columns} FROM buffer_table"
        elif self.table_name == "playlist_track_junction":
            # Junction table with composite PRIMARY KEY (playlist_id, track_id)
            update_cols = ", ".join(
                [
                    f"{col} = EXCLUDED.{col}"
                    for col in chunk.columns
                    if col not in ["playlist_id", "track_id"]
                ]
            )
            insert_query = f"INSERT INTO {self.table_name} ({columns}) SELECT {columns} FROM buffer_table ON CONFLICT (playlist_id, track_id) DO UPDATE SET {update_cols}"
        else:
            # Default case - just insert
            insert_query = f"INSERT INTO {self.table_name} ({columns}) SELECT {columns} FROM buffer_table"

        self.conn.execute(insert_query)
        self.conn.unregister("buffer_table")

    def set_table_name(self, table_name):
        self.table_name = table_name
