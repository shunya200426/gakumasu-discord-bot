"""ImageConsentServiceの単体テスト。"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from db.repositories.user_repository import UserRepository
from db.schema import create_tables
from services.image_consent_service import (
    ImageConsentResult,
    ImageConsentService,
)


class SpyUserRepository(UserRepository):
    """同意状態の更新回数を記録するRepository。"""

    def __init__(self, connection: sqlite3.Connection) -> None:
        super().__init__(connection)
        self.set_consent_call_count = 0

    def set_image_save_consent(
        self,
        user_id: int,
        consent: bool,
    ) -> None:
        self.set_consent_call_count += 1
        super().set_image_save_consent(user_id, consent)


class FailingUserRepository(UserRepository):
    """更新SQL実行後に例外を送出するRepository。"""

    def set_image_save_consent(
        self,
        user_id: int,
        consent: bool,
    ) -> None:
        super().set_image_save_consent(user_id, consent)
        raise RuntimeError("update failed")


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


def add_user_with_consent(
    repository: UserRepository,
    connection: sqlite3.Connection,
    consent: bool | None,
) -> None:
    repository.upsert_user(
        user_id=1,
        user_name="user",
        display_name="display",
    )

    if consent is not None:
        repository.set_image_save_consent(1, consent)

    connection.commit()


@pytest.mark.parametrize(
    (
        "stored",
        "requested",
        "expected_current",
        "expected_changed",
    ),
    [
        (None, None, False, False),
        (None, True, True, True),
        (None, False, False, True),
        (True, None, True, False),
        (True, True, True, False),
        (True, False, False, True),
        (False, None, False, False),
        (False, True, True, True),
        (False, False, False, False),
    ],
)
def test_resolve_follows_consent_state_transition_table(
    connection: sqlite3.Connection,
    stored: bool | None,
    requested: bool | None,
    expected_current: bool,
    expected_changed: bool,
) -> None:
    repository = SpyUserRepository(connection)
    add_user_with_consent(repository, connection, stored)
    repository.set_consent_call_count = 0
    before = connection.execute(
        """
        SELECT image_save_consent_updated_at
        FROM users
        WHERE user_id = ?;
        """,
        (1,),
    ).fetchone()
    assert before is not None

    result = ImageConsentService(repository).resolve(
        user_id=1,
        requested=requested,
    )

    assert result == ImageConsentResult(
        previous=stored,
        current=expected_current,
        changed=expected_changed,
    )
    assert repository.set_consent_call_count == int(
        expected_changed
    )
    assert (
        repository.get_image_save_consent(1)
        is (
            requested
            if expected_changed
            else stored
        )
    )

    after = connection.execute(
        """
        SELECT image_save_consent_updated_at
        FROM users
        WHERE user_id = ?;
        """,
        (1,),
    ).fetchone()
    assert after is not None

    if not expected_changed:
        assert after[0] == before[0]


def test_resolve_commits_changed_consent(
    connection: sqlite3.Connection,
    database_path: Path,
) -> None:
    repository = UserRepository(connection)
    add_user_with_consent(repository, connection, None)

    ImageConsentService(repository).resolve(
        user_id=1,
        requested=True,
    )

    observer = sqlite3.connect(database_path)
    try:
        row = observer.execute(
            """
            SELECT image_save_consent
            FROM users
            WHERE user_id = ?;
            """,
            (1,),
        ).fetchone()
        assert row is not None
        assert row[0] == 1
    finally:
        observer.close()


def test_resolve_rolls_back_when_update_fails(
    connection: sqlite3.Connection,
) -> None:
    add_user_with_consent(
        UserRepository(connection),
        connection,
        False,
    )
    repository = FailingUserRepository(connection)
    service = ImageConsentService(repository)

    with pytest.raises(RuntimeError, match="update failed"):
        service.resolve(
            user_id=1,
            requested=True,
        )

    assert repository.get_image_save_consent(1) is False


def test_resolve_treats_missing_user_as_unselected(
    connection: sqlite3.Connection,
) -> None:
    repository = SpyUserRepository(connection)

    result = ImageConsentService(repository).resolve(
        user_id=999,
        requested=None,
    )

    assert result == ImageConsentResult(
        previous=None,
        current=False,
        changed=False,
    )
    assert repository.set_consent_call_count == 0
