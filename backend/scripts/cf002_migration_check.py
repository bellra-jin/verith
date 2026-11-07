"""Migration regression on a pre-attested disposable connection, never an app URL."""

from __future__ import annotations
import asyncio
import os
from pathlib import Path
import sys
from uuid import uuid4

from dotenv import dotenv_values
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
from alembic import command
from alembic.config import Config

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tests.db_safety import preflight_database, attest_engine_connection


async def main():
    app_url = os.getenv("DATABASE_URL") or dotenv_values(".env").get("DATABASE_URL")
    approval = await preflight_database(os.environ, app_url)
    engine = create_async_engine(
        approval.url, connect_args=approval.connection_parameters()
    )
    try:
        async with engine.connect() as connection:
            await attest_engine_connection(connection, approval)

            def migrate(sync, action, target=None):
                config = Config("alembic.ini")
                config.attributes.update(connection=sync, verified_test_mode=True)
                if target is None:
                    getattr(command, action)(config)
                else:
                    getattr(command, action)(config, target)

            await connection.run_sync(migrate, "upgrade", "head")
            await connection.commit()
            await connection.run_sync(migrate, "check")
            await connection.commit()
            await connection.run_sync(migrate, "downgrade", "b1e9d4a7c2f1")
            await connection.commit()
            legacy_id, external_owner, external_session, index_id = (
                uuid4(),
                uuid4(),
                uuid4(),
                uuid4(),
            )
            await connection.execute(
                text(
                    "INSERT INTO stocks(stock_code,stock_name) VALUES('999992','CF002 legacy')"
                )
            )
            await connection.execute(
                text(
                    "INSERT INTO flow_reports(id,stock_code,ticker,signals) VALUES(:id,'999992','999992',CAST(:payload AS jsonb))"
                ),
                {"id": legacy_id, "payload": '{"zero":0,"missing":null}'},
            )
            await connection.execute(
                text(
                    "INSERT INTO agent_reports(id,agent_type,agent_report_id,owner_user_id,owner_session_id,summary) VALUES(:id,'flow',:root,:owner,:session,CAST(:summary AS jsonb))"
                ),
                {
                    "id": index_id,
                    "root": legacy_id,
                    "owner": external_owner,
                    "session": external_session,
                    "summary": '{"legacy":true}',
                },
            )
            await connection.commit()
            before = (
                await connection.execute(text("SELECT id,signals FROM flow_reports"))
            ).all()
            old_indexes = (
                await connection.execute(
                    text(
                        "SELECT id,owner_user_id,owner_session_id,summary FROM agent_reports"
                    )
                )
            ).all()
            await connection.rollback()
            await connection.run_sync(migrate, "upgrade", "head")
            await connection.commit()
            assert (
                await connection.execute(text("SELECT id,signals FROM flow_reports"))
            ).all() == before
            assert (
                await connection.execute(
                    text(
                        "SELECT id,owner_user_id,owner_session_id,summary FROM agent_reports"
                    )
                )
            ).all() == old_indexes
            assert (
                await connection.scalar(
                    text(
                        "SELECT count(*) FROM flow_reports WHERE owner_user_id IS NOT NULL"
                    )
                )
                == 0
            )
            await connection.commit()
            # Guard rejects, and leaves revision/schema/data intact.
            user_id = uuid4()
            await connection.execute(
                text("INSERT INTO auth_users(id) VALUES(:id)"), {"id": user_id}
            )
            await connection.commit()
            try:
                await connection.run_sync(migrate, "downgrade", "b1e9d4a7c2f1")
            except RuntimeError as exc:
                assert "Refusing destructive" in str(exc)
                await connection.rollback()
            else:
                raise AssertionError("Destructive downgrade was not rejected")
            await connection.execute(
                text("DELETE FROM auth_users WHERE id=:id"), {"id": user_id}
            )
            await connection.commit()
            await connection.run_sync(migrate, "downgrade", "b1e9d4a7c2f1")
            await connection.commit()
            await connection.run_sync(migrate, "upgrade", "head")
            await connection.commit()
            await connection.run_sync(migrate, "check")
            await connection.commit()
            # Only this harness's known synthetic legacy is removed; no shared app DB.
            await connection.execute(
                text("DELETE FROM agent_reports WHERE id=:id"), {"id": index_id}
            )
            await connection.execute(
                text("DELETE FROM flow_reports WHERE id=:id"), {"id": legacy_id}
            )
            await connection.execute(
                text("DELETE FROM stocks WHERE stock_code='999992'")
            )
            await connection.commit()
            print(
                "Same verified connection: legacy preservation, guarded downgrade, empty-auth downgrade/reupgrade, metadata check passed",
                flush=True,
            )
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
