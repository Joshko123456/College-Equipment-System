"""Create tables only. Never drops tables or imports demo accounts."""
from pathlib import Path
from pg_database import raw_connect
if __name__=='__main__':
    with raw_connect() as conn:
        # DDL file contains schema only, with no user input or database selection.
        conn.execute(Path(__file__).with_name('schema_postgresql.sql').read_text(),prepare=False)
    print('PostgreSQL schema initialized. Existing data was not deleted.')
