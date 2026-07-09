# db/repositories/user_repository.py

import sqlite3
from datetime import datetime, timezone
from typing import Optional


class UserRepository:
    """
    users テーブルを操作するRepository。
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
        user_id からユーザー情報を取得する。
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