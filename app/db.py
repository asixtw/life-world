"""One connection per operation and serialized, atomic writes."""
from contextlib import contextmanager
from pathlib import Path
import sqlite3


class Database:
    def __init__(self, data_dir):
        self.directory = Path(data_dir).resolve()
        self.directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.path = self.directory / 'lifeworld.sqlite3'
        connection = sqlite3.connect(str(self.path), isolation_level=None, timeout=20)
        try:
            connection.execute('PRAGMA journal_mode=WAL')
            connection.execute('CREATE TABLE IF NOT EXISTS schema_migrations (version TEXT PRIMARY KEY)')
            for path in sorted((Path(__file__).parent / 'migrations').glob('*.sql')):
                if not connection.execute('SELECT 1 FROM schema_migrations WHERE version=?', (path.name,)).fetchone():
                    connection.executescript('BEGIN IMMEDIATE;\n' + path.read_text() +
                                             "\nINSERT INTO schema_migrations VALUES ('" + path.name + "');\nCOMMIT;")
        finally:
            connection.close()
        self.path.chmod(0o600)

    @contextmanager
    def connect(self, write=False):
        connection = sqlite3.connect(str(self.path), isolation_level=None, timeout=20)
        connection.row_factory = sqlite3.Row
        connection.execute('PRAGMA foreign_keys=ON')
        connection.execute('PRAGMA busy_timeout=20000')
        try:
            connection.execute('BEGIN IMMEDIATE' if write else 'BEGIN')
            yield connection
            connection.commit()
        except BaseException:
            connection.rollback()
            raise
        finally:
            connection.close()
