"""Consistent SQLite backup, including committed WAL content."""
from pathlib import Path
import argparse
import sqlite3

ROOT = Path(__file__).resolve().parent.parent

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Create a consistent Life World SQLite backup')
    parser.add_argument('destination', type=Path)
    parser.add_argument('--source', type=Path, default=ROOT / 'data' / 'lifeworld.sqlite3')
    args = parser.parse_args()
    if not args.source.is_file():
        parser.error('Source database does not exist')
    if args.destination.exists():
        parser.error('Destination already exists; refusing to overwrite')
    args.destination.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(args.source.resolve().as_uri() + '?mode=ro', uri=True) as source:
        with sqlite3.connect(args.destination) as destination:
            source.backup(destination)
    args.destination.chmod(0o600)
    print('Backup created:', args.destination)
