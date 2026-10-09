"""Build the production analytical snapshot using only DuckDB and the standard library."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path

import duckdb


def build_snapshot(source: Path, database: Path) -> dict:
    manifest = json.loads((source / 'manifest.json').read_text(encoding='utf-8'))
    if manifest['format_version'] != 1 or not manifest['tables']:
        raise ValueError('Unsupported or empty CMob data manifest')
    identifier = re.compile(r'^[a-z][a-z0-9_]*$')
    allowed_types = {'DATE', 'BIGINT', 'INTEGER', 'DOUBLE', 'VARCHAR', 'BOOLEAN'}
    database.parent.mkdir(parents=True, exist_ok=True)
    temporary = database.with_suffix('.building.duckdb')
    temporary.unlink(missing_ok=True)
    connection = duckdb.connect(str(temporary))
    try:
        for name, table in manifest['tables'].items():
            if not identifier.fullmatch(name):
                raise ValueError('Invalid table identifier')
            path = (source / table['file']).resolve()
            if path.parent != source.resolve() or path.suffix != '.csv':
                raise ValueError('CSV path escapes snapshot directory')
            if hashlib.sha256(path.read_bytes()).hexdigest() != table['sha256']:
                raise ValueError(f'Checksum mismatch: {name}')
            columns = {column['name']: column['type'] for column in table['columns']}
            if not all(identifier.fullmatch(key) and kind in allowed_types for key, kind in columns.items()):
                raise ValueError('Unsupported column or data type')
            connection.execute(f'CREATE TABLE "{name}" AS SELECT * FROM read_csv(?, header=true, columns=?, auto_detect=false, delim=\',\')', [str(path), columns])
            count, start, end = connection.execute(f'SELECT count(*), min(service_date), max(service_date) FROM "{name}"').fetchone()
            if count != table['row_count'] or str(start) != table['start'] or str(end) != table['end']:
                raise ValueError(f'Coverage or row count mismatch: {name}')
        connection.execute('CREATE TABLE snapshot_metadata (data_version VARCHAR)')
        connection.execute('INSERT INTO snapshot_metadata VALUES (?)', [manifest['data_version']])
    except Exception:
        connection.close()
        temporary.unlink(missing_ok=True)
        raise
    connection.close()
    temporary.replace(database)
    return manifest


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--source', type=Path, default=Path('data/public'))
    parser.add_argument('--database', type=Path, default=Path('data/database/semob.duckdb'))
    args = parser.parse_args()
    manifest = build_snapshot(args.source, args.database)
    print(f"CMob snapshot ready: {manifest['data_version']}, {len(manifest['tables'])} tables")


if __name__ == '__main__':
    main()
