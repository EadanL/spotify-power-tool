import logging
import os

import duckdb
from dotenv import load_dotenv


class DataFrameLoadingBuffer:
    def __init__(
        self,
        duckdb_schema: str,
        database_name: str,
        table_name: str,
        chunk_size: int = 100_00,
    ):
        self.duckdb_schema = duckdb_schema
        self.database_name = database_name
        self.table_name = table_name
        self.chunk_size = chunk_size
        self.conn = self.initialize_connection(duckdb_schema)
        self.total_inserted = 0

    def initialize_connection(self, sql):
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
        conn.execute("SET GLOBAL pandas_analyze_sample=1000")
        # conn.execute(sql) // until I fix the explicit schema definition use the auto detect
        return conn

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
        create = f"CREATE TABLE IF NOT EXISTS {self.table_name} AS SELECT * FROM buffer_table WHERE 1=0"
        insert_query = f"INSERT INTO {self.table_name} SELECT * FROM buffer_table"
        self.conn.execute(create)
        self.conn.execute(insert_query)
        self.conn.unregister("buffer_table")
