"""Migration defaults, cascades and reversible schema on a disposable database."""

from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from uuid import uuid4

from alembic.migration import MigrationContext
from alembic.operations import Operations
import sqlalchemy as sa


def test_push_migration_roundtrip():
    engine = sa.create_engine("sqlite+pysqlite:///:memory:")
    with engine.begin() as connection:
        connection.exec_driver_sql("PRAGMA foreign_keys=ON")
        metadata = sa.MetaData()
        for name in ("users", "user_sessions", "posts"):
            sa.Table(name, metadata, sa.Column("id", sa.Uuid(), primary_key=True))
        metadata.create_all(connection)
        modules = []
        for name in ("0015_keyword_conditions", "0016_push_notifications"):
            spec = spec_from_file_location(name, Path(__file__).parents[1] / f"alembic/versions/{name}.py")
            module = module_from_spec(spec)
            spec.loader.exec_module(module)
            modules.append(module)
        with Operations.context(MigrationContext.configure(connection)):
            modules[0].upgrade()
            keywords = sa.Table("keyword_conditions", sa.MetaData(), sa.Column("id", sa.Uuid(), primary_key=True),
                sa.Column("user_id", sa.Uuid()), autoload_with=connection)
            owner = uuid4()
            connection.execute(metadata.tables["users"].insert().values(id=owner))
            connection.execute(keywords.insert().values(id=uuid4(), user_id=owner, post_type="FOUND", conditions={"q": "에어팟"}))
            modules[1].upgrade()
            keywords = sa.Table("keyword_conditions", sa.MetaData(), autoload_with=connection)
            saved = connection.execute(sa.select(keywords)).mappings().one()
            assert saved["notification_enabled"] is False
            assert saved["notification_enabled_at"] is None
            assert saved["conditions"] == {"q": "에어팟"}
            assert sa.inspect(connection).has_table("push_deliveries")
            modules[1].downgrade()
            assert not sa.inspect(connection).has_table("push_deliveries")
            assert "notification_enabled" not in {column["name"] for column in sa.inspect(connection).get_columns("keyword_conditions")}
            modules[0].downgrade()
    engine.dispose()
