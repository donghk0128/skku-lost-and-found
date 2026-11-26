"""Chat push tables apply and roll back on a disposable schema."""

from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

from alembic.migration import MigrationContext
from alembic.operations import Operations
import sqlalchemy as sa


def test_chat_push_migration_roundtrip():
    engine = sa.create_engine("sqlite+pysqlite:///:memory:")
    with engine.begin() as connection:
        metadata = sa.MetaData()
        for name in ("users", "chat_rooms", "chat_messages", "push_devices"):
            sa.Table(name, metadata, sa.Column("id", sa.Uuid(), primary_key=True))
        metadata.create_all(connection)
        path = Path(__file__).parents[1] / "alembic/versions/0019_chat_push_notifications.py"
        spec = spec_from_file_location("chat_push_migration", path)
        module = module_from_spec(spec)
        spec.loader.exec_module(module)
        with Operations.context(MigrationContext.configure(connection)):
            module.upgrade()
            assert sa.inspect(connection).has_table("chat_push_notifications")
            assert sa.inspect(connection).has_table("chat_push_deliveries")
            module.downgrade()
            assert not sa.inspect(connection).has_table("chat_push_notifications")
            assert not sa.inspect(connection).has_table("chat_push_deliveries")
    engine.dispose()
