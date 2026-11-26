"""Check the two new migrations without touching an external database."""

from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import create_engine, inspect


def migration(name):
    path = Path(__file__).resolve().parents[1] / "alembic" / "versions" / f"{name}.py"
    spec = spec_from_file_location(name, path)
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_event_and_return_pair_migrations_roundtrip():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    events = migration("0017_event_logs")
    pairs = migration("0018_return_pairs")
    assert pairs.down_revision == events.revision
    with engine.begin() as connection:
        with Operations.context(MigrationContext.configure(connection)):
            events.upgrade()
            pairs.upgrade()
            columns = {column["name"] for column in inspect(connection).get_columns("event_logs")}
            assert {"occurred_at", "received_at", "run_id", "candidate_post_id", "visit_id"} <= columns
            assert {column["name"] for column in inspect(connection).get_columns("return_pairs")} >= {
                "room_id", "lost_post_id", "found_post_id", "proposed_by_id", "confirmed_at",
            }
            pairs.downgrade()
            events.downgrade()
            assert "event_logs" not in inspect(connection).get_table_names()
            assert "return_pairs" not in inspect(connection).get_table_names()
    engine.dispose()
