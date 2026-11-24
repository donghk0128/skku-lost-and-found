"""Run the real migration on isolated legacy tables, including DB constraints."""

from uuid import uuid4

from alembic.migration import MigrationContext
from alembic.operations import Operations
import pytest
import sqlalchemy as sa

def load_migration(name="0013_post_locations"):
    # alembic/ is a local script directory, not the installed alembic package.
    from importlib.util import module_from_spec, spec_from_file_location
    from pathlib import Path

    spec = spec_from_file_location(name, Path(__file__).parents[1] / f"alembic/versions/{name}.py")
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_backfill_constraints_cascade_and_downgrade_guard():
    migration = load_migration()
    engine = sa.create_engine("sqlite+pysqlite:///:memory:")
    with engine.begin() as connection:
        connection.exec_driver_sql("PRAGMA foreign_keys=ON")
        metadata = sa.MetaData()
        posts = sa.Table(
            "posts", metadata, sa.Column("id", sa.Uuid(), primary_key=True),
            sa.Column("location_text", sa.String(255)), sa.Column("latitude", sa.Numeric(9, 6)),
            sa.Column("longitude", sa.Numeric(9, 6)), sa.Column("deleted_at", sa.DateTime()),
        )
        metadata.create_all(connection)
        ids = [uuid4() for _ in range(5)]
        connection.execute(posts.insert(), [
            {"id": ids[0], "location_text": "학생회관", "latitude": 37.588, "longitude": 126.993},
            {"id": ids[1], "location_text": "도서관", "latitude": None, "longitude": None},
            {"id": ids[2], "location_text": None, "latitude": None, "longitude": None},
            {"id": ids[3], "location_text": " ", "latitude": 0, "longitude": 0},
            {"id": ids[4], "location_text": " ", "latitude": None, "longitude": None},
        ])
        connection.execute(posts.update().where(posts.c.id == ids[1]).values(deleted_at=sa.func.current_timestamp()))
        with Operations.context(MigrationContext.configure(connection)):
            migration.upgrade()
            locations = sa.Table(
                "post_locations", sa.MetaData(), sa.Column("post_id", sa.Uuid(), primary_key=True),
                autoload_with=connection,
            )
            rows = {row["post_id"]: row for row in connection.execute(sa.select(locations)).mappings()}
            assert set(rows) == {ids[0], ids[1], ids[3]}
            assert rows[ids[0]]["position"] == 0
            assert rows[ids[1]]["location_text"] == "도서관"
            assert rows[ids[3]]["location_text"] is None
            assert rows[ids[3]]["latitude"] == 0
            # Migration leaves all legacy posts and representative columns intact.
            assert connection.scalar(sa.select(sa.func.count()).select_from(posts)) == 5
            assert connection.scalar(sa.select(posts.c.location_text).where(posts.c.id == ids[0])) == "학생회관"
            # Already-applied revision 0013 keeps its historical policy. Revision
            # 0014 removes that upper bound so future policy changes need no DDL.
            with pytest.raises(sa.exc.IntegrityError), connection.begin_nested():
                connection.execute(locations.insert().values(post_id=ids[0], position=20, location_text="확장"))
            policy = load_migration("0014_post_location_limit_policy")
            policy.upgrade()
            connection.execute(locations.insert().values(post_id=ids[0], position=20, location_text="확장"))
            with pytest.raises(RuntimeError, match="old 20-location limit"):
                policy.downgrade()
            connection.execute(locations.delete().where(locations.c.position == 20))
            policy.downgrade()
            policy.upgrade()
            for fields in (
                {"position": -1, "location_text": "음수"},
                {"position": 1}, {"position": 1, "location_text": " "},
                {"position": 1, "latitude": 37},
                {"position": 1, "latitude": 91, "longitude": 127},
                {"position": 1, "latitude": 37, "longitude": 181},
                {"position": 0, "location_text": "중복 순서"},
            ):
                with pytest.raises(sa.exc.IntegrityError), connection.begin_nested():
                    connection.execute(locations.insert().values(post_id=ids[0], **fields))
            connection.execute(locations.insert().values(post_id=ids[0], position=1, location_text="추가 장소"))
            with pytest.raises(RuntimeError, match="lose data"):
                migration.downgrade()
            assert sa.inspect(connection).has_table("post_locations")
            connection.execute(posts.delete().where(posts.c.id == ids[0]))
            assert connection.scalar(sa.select(sa.func.count()).select_from(locations)) == 2
            migration.downgrade()
            assert not sa.inspect(connection).has_table("post_locations")
            assert connection.scalar(sa.select(posts.c.location_text).where(posts.c.id == ids[1])) == "도서관"
    engine.dispose()
