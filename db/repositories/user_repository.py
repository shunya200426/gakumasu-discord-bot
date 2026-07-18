# db/repositories/user_repository.py

import sqlite3
from datetime import datetime, timezone
from typing import Optional


class UserRepository:
    """
    users テーブルと blocked_users テーブルを操作するRepository。
    """

    def __init__(self, connection: sqlite3.Connection) -> None:
        self.connection = connection

    def upsert_user(
        self,
        user_id: int,
        user_name: Optional[str],
        display_name: Optional[str],
    ) -> None:
        """
        ユーザー情報を登録・更新する。
        既に存在する場合は、名前情報とupdated_atを更新する。
        """
        now = datetime.now(timezone.utc).isoformat()

        self.connection.execute(
            """
            INSERT INTO users (
                user_id,
                user_name,
                display_name,
                updated_at
            )
            VALUES (?, ?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                user_name = excluded.user_name,
                display_name = excluded.display_name,
                updated_at = excluded.updated_at;
            """,
            (
                user_id,
                user_name,
                display_name,
                now,
            ),
        )

    def get_by_user_id(self, user_id: int) -> Optional[sqlite3.Row]:
        """
        user_idからユーザー情報を取得する。
        """
        cursor = self.connection.execute(
            """
            SELECT
                user_id,
                user_name,
                display_name,
                updated_at
            FROM users
            WHERE user_id = ?;
            """,
            (user_id,),
        )
        return cursor.fetchone()

    def get_image_save_consent(
        self,
        user_id: int,
    ) -> bool | None:
        """
        ユーザーの画像保存同意状態を取得する。

        未選択またはユーザーが存在しない場合はNoneを返す。
        """
        cursor = self.connection.execute(
            """
            SELECT image_save_consent
            FROM users
            WHERE user_id = ?;
            """,
            (user_id,),
        )
        row = cursor.fetchone()

        if row is None or row["image_save_consent"] is None:
            return None

        return bool(row["image_save_consent"])

    def set_image_save_consent(
        self,
        user_id: int,
        consent: bool,
    ) -> None:
        """
        ユーザーの画像保存同意状態と更新日時を更新する。

        トランザクションの確定は呼び出し側が担当する。
        """
        now = datetime.now(timezone.utc).isoformat()

        self.connection.execute(
            """
            UPDATE users
            SET
                image_save_consent = ?,
                image_save_consent_updated_at = ?
            WHERE user_id = ?;
            """,
            (
                int(consent),
                now,
                user_id,
            ),
        )

    def add_block(
        self,
        user_id: int,
        reason: Optional[str] = None,
        user_message: Optional[str] = None,
        blocked_by: Optional[int] = None,
    ) -> None:
        """
        ユーザーのコマンド実行を無効化する。

        既にブロックされている場合は、
        reason、user_message、blocked_at、blocked_byを更新する。
        """
        now = datetime.now(timezone.utc).isoformat()

        self.connection.execute(
            """
            INSERT INTO blocked_users (
                user_id,
                reason,
                user_message,
                blocked_at,
                blocked_by
            )
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(user_id)
            DO UPDATE SET
                reason = excluded.reason,
                user_message = excluded.user_message,
                blocked_at = excluded.blocked_at,
                blocked_by = excluded.blocked_by;
            """,
            (
                user_id,
                reason,
                user_message,
                now,
                blocked_by,
            ),
        )

    def remove_block(self, user_id: int) -> None:
        """
        ユーザーのコマンド実行制限を解除する。
        """
        self.connection.execute(
            """
            DELETE FROM blocked_users
            WHERE user_id = ?;
            """,
            (user_id,),
        )

    def is_blocked(self, user_id: int) -> bool:
        """
        ユーザーがブロックされているか確認する。
        """
        cursor = self.connection.execute(
            """
            SELECT 1
            FROM blocked_users
            WHERE user_id = ?
            LIMIT 1;
            """,
            (user_id,),
        )

        return cursor.fetchone() is not None

    def get_block(self, user_id: int) -> Optional[sqlite3.Row]:
        """
        user_idからブロック情報を取得する。

        ブロックされていない場合はNoneを返す。
        """
        cursor = self.connection.execute(
            """
            SELECT
                user_id,
                reason,
                user_message,
                blocked_at,
                blocked_by
            FROM blocked_users
            WHERE user_id = ?;
            """,
            (user_id,),
        )

        return cursor.fetchone()
