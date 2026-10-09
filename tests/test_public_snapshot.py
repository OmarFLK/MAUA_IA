import json
from pathlib import Path

import duckdb
import pytest

from scripts.build_cmob_data import build_snapshot
from scripts.publish_cmob_data import publish


def test_public_csv_roundtrip_preserves_text_and_excludes_driver(tmp_path: Path):
    database = tmp_path / 'input.duckdb'
    with duckdb.connect(str(database)) as con:
        con.execute('CREATE TABLE trip_exceptions(service_date DATE, line_code VARCHAR, driver VARCHAR)')
        con.execute("INSERT INTO trip_exceptions VALUES ('2026-08-01','001','Private Name')")
    output = tmp_path / 'public'
    manifest = publish(database, output, tmp_path / 'knowledge', tmp_path / 'metadata')
    assert 'Private Name' not in (output / 'trip_exceptions.csv').read_text()
    assert 'driver' not in [column['name'] for column in manifest['tables']['trip_exceptions']['columns']]
    target = tmp_path / 'rebuilt.duckdb'
    build_snapshot(output, target)
    with duckdb.connect(str(target), read_only=True) as con:
        assert con.execute('SELECT line_code FROM trip_exceptions').fetchone() == ('001',)
    (output / 'trip_exceptions.csv').write_text('tampered')
    with pytest.raises(ValueError, match='Checksum'):
        build_snapshot(output, target)
    with duckdb.connect(str(target), read_only=True) as con:
        assert con.execute('SELECT count(*) FROM trip_exceptions').fetchone() == (1,)


def test_snapshot_rejects_escape_path(tmp_path: Path):
    (tmp_path / 'manifest.json').write_text(json.dumps({'format_version': 1, 'tables': {
        'trips': {'file': '../secret.csv'}}}))
    with pytest.raises(ValueError, match='escapes'):
        build_snapshot(tmp_path, tmp_path / 'output.duckdb')
