"""UserRepositoryの単体テスト。"""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path

import pytest

from db.repositories.user_repository import UserRepository
from db.schema import create_tables


@pytest.fixture
def database_path(tmp_path: Path) -> Path:
    return tmp_path / "test.db"


@pytest.fixture
def connection(database_path: Path) -> sqlite3.Connection:
    connection = sqlite3.connect(database_path)
    connection.row_factory = sqlite3.Row
    create_tables(connection)

    try:
        yield connection
    finally:
        connection.close()


@pytest.fixture
def repository(
    connection: sqlite3.Connection,
) -> UserRepository:
    return UserRepository(connection)


def add_user(
    repository: UserRepository,
    connection: sqlite3.Connection,
    *,
    user_id: int = 1,
) -> None:
    repository.upsert_user(
        user_id=user_id,
        user_name="user",
        display_name="display",
    )
    connection.commit()


def get_raw_consent(
    connection: sqlite3.Connection,
    user_id: int = 1,
) -> sqlite3.Row:
    row = connection.execute(
        """
        SELECT
            image_save_consent,
            image_save_consent_updated_at
        FROM users
        WHERE user_id = ?;
        """,
        (user_id,),
    ).fetchone()

    assert row is not None
    return row


def test_get_image_save_consent_returns_none_when_unselected(
    repository: UserRepository,
    connection: sqlite3.Connection,
) -> None:
    add_user(repository, connection)

    assert repository.get_image_save_consent(1) is None


@pytest.mark.parametrize(
    ("database_value", "expected"),
    [
        (1, True),
        (0, False),
    ],
)
def test_get_image_save_consent_converts_database_value(
    repository: UserRepository,
    connection: sqlite3.Connection,
    database_value: int,
    expected: bool,
) -> None:
    add_user(repository, connection)
    connection.execute(
        """
        UPDATE users
        SET image_save_consent = ?
        WHERE user_id = ?;
        """,
        (database_value, 1),
    )
    connection.commit()

    assert repository.get_image_save_consent(1) is expected


def test_get_image_save_consent_returns_none_for_missing_user(
    repository: UserRepository,
) -> None:
    assert repository.get_image_save_consent(999) is None


@pytest.mark.parametrize(
    ("consent", "expected"),
    [
        (True, 1),
        (False, 0),
    ],
)
def test_set_image_save_consent_stores_integer_and_timestamp(
    repository: UserRepository,
    connection: sqlite3.Connection,
    consent: bool,
    expected: int,
) -> None:
    add_user(repository, connection)

    repository.set_image_save_consent(1, consent)
    row = get_raw_consent(connection)

    assert row["image_save_consent"] == expected

    updated_at = datetime.fromisoformat(
        row["image_save_consent_updated_at"]
    )
    assert updated_at.tzinfo == timezone.utc


def test_upsert_user_preserves_image_save_consent_and_timestamp(
    repository: UserRepository,
    connection: sqlite3.Connection,
) -> None:
    add_user(repository, connection)
    repository.set_image_save_consent(1, True)
    connection.commit()
    before = get_raw_consent(connection)

    repository.upsert_user(
        user_id=1,
        user_name="updated-user",
        display_name="updated-display",
    )
    connection.commit()
    after = get_raw_consent(connection)

    assert after["image_save_consent"] == 1
    assert (
        after["image_save_consent_updated_at"]
        == before["image_save_consent_updated_at"]
    )


def test_set_image_save_consent_requires_caller_commit(
    repository: UserRepository,
    connection: sqlite3.Connection,
    database_path: Path,
) -> None:
    add_user(repository, connection)
    observer = sqlite3.connect(database_path)

    try:
        repository.set_image_save_consent(1, True)

        before_commit = observer.execute(
            """
            SELECT image_save_consent
            FROM users
            WHERE user_id = ?;
            """,
            (1,),
        ).fetchone()
        assert before_commit is not None
        assert before_commit[0] is None

        connection.commit()

        after_commit = observer.execute(
            """
            SELECT image_save_consent
            FROM users
            WHERE user_id = ?;
            """,
            (1,),
        ).fetchone()
        assert after_commit is not None
        assert after_commit[0] == 1
    finally:
        observer.close()


def test_users_schema_has_nullable_consent_columns(
    connection: sqlite3.Connection,
    repository: UserRepository,
) -> None:
    table_names = {
        row["name"]
        for row in connection.execute(
            """
            SELECT name
            FROM sqlite_master
            WHERE type = 'table';
            """
        ).fetchall()
    }
    assert {
        "registered_servers",
        "users",
        "blocked_users",
        "command_logs",
        "error_logs",
        "inference_logs",
        "detection_results",
    } <= table_names

    columns = {
        row["name"]: row
        for row in connection.execute(
            "PRAGMA table_info(users);"
        ).fetchall()
    }

    assert columns["image_save_consent"]["notnull"] == 0
    assert columns["image_save_consent"]["dflt_value"] is None
    assert columns["image_save_consent_updated_at"]["notnull"] == 0
    assert (
        columns["image_save_consent_updated_at"]["dflt_value"]
        is None
    )

    add_user(repository, connection)
    row = get_raw_consent(connection)
    assert row["image_save_consent"] is None
    assert row["image_save_consent_updated_at"] is None


def test_image_save_consent_check_constraint_is_enabled(
    repository: UserRepository,
    connection: sqlite3.Connection,
) -> None:
    add_user(repository, connection)

    with pytest.raises(sqlite3.IntegrityError):
        connection.execute(
            """
            UPDATE users
            SET image_save_consent = 2
            WHERE user_id = ?;
            """,
            (1,),
        )
