"""Keyword condition migration preserves JSON and cascades account deletion."""

from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from uuid import uuid4

from alembic.migration import MigrationContext
from alembic.operations import Operations
import sqlalchemy as sa


def test_keyword_condition_migration_roundtrip():
    spec = spec_from_file_location("keywords_migration", Path(__file__).parents[1] / "alembic/versions/0015_keyword_conditions.py")
    migration = module_from_spec(spec)
    spec.loader.exec_module(migration)
    engine = sa.create_engine("sqlite+pysqlite:///:memory:")
    with engine.begin() as connection:
        connection.exec_driver_sql("PRAGMA foreign_keys=ON")
        metadata = sa.MetaData()
        users = sa.Table("users", metadata, sa.Column("id", sa.Uuid(), primary_key=True))
        metadata.create_all(connection)
        owner = uuid4()
        connection.execute(users.insert().values(id=owner))
        with Operations.context(MigrationContext.configure(connection)):
            migration.upgrade()
            rows = sa.Table("keyword_conditions", sa.MetaData(),
                sa.Column("id", sa.Uuid(), primary_key=True), sa.Column("user_id", sa.Uuid()), autoload_with=connection)
            conditions = {"q": "검정 에어팟", "location_terms": ["디도", "학생회관"], "event_at": None}
            connection.execute(rows.insert().values(id=uuid4(), user_id=owner, post_type="FOUND", conditions=conditions))
            saved = connection.execute(sa.select(rows)).mappings().one()
            assert saved["version"] == 1 and saved["conditions"] == conditions
            assert sa.inspect(connection).get_indexes("keyword_conditions")[0]["name"] == "ix_keyword_conditions_user_id"
            connection.execute(users.delete().where(users.c.id == owner))
            assert connection.scalar(sa.select(sa.func.count()).select_from(rows)) == 0
            migration.downgrade()
            assert not sa.inspect(connection).has_table("keyword_conditions")
    engine.dispose()
