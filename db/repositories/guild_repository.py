# db/repositories/guild_repository.py

import sqlite3
from datetime import datetime, timezone
from typing import Optional


class GuildRepository:
    """
    registered_servers テーブルを操作するRepository。
    """

    def __init__(self, connection: sqlite3.Connection) -> None:
        self.connection = connection

    def register(
        self,
        guild_id: int,
        guild_name: Optional[str],
        community_name: str,
    ) -> None:
        """
        サーバーを登録する。
        既に存在する場合は情報を更新し、enabled=1 に戻す。
        """
        now = datetime.now(timezone.utc).isoformat()

        self.connection.execute(
            """
            INSERT INTO registered_servers (
                guild_id,
                guild_name,
                community_name,
                registered_at,
                updated_at,
                enabled
            )
            VALUES (?, ?, ?, ?, ?, 1)
            ON CONFLICT(guild_id) DO UPDATE SET
                guild_name = excluded.guild_name,
                community_name = excluded.community_name,
                updated_at = excluded.updated_at,
                enabled = 1;
            """,
            (
                guild_id,
                guild_name,
                community_name,
                now,
                now,
            ),
        )

    def unregister(self, guild_id: int) -> None:
        """
        サーバー登録を無効化する。
        レコード自体は削除しない。
        """
        now = datetime.now(timezone.utc).isoformat()

        self.connection.execute(
            """
            UPDATE registered_servers
            SET
                enabled = 0,
                updated_at = ?
            WHERE guild_id = ?;
            """,
            (now, guild_id),
        )

    def enable(
        self,
        guild_id: int,
    ) -> None:
        """
        登録済みサーバーを利用可能な状態に戻す。
        """
        now = datetime.now(
            timezone.utc
        ).isoformat()

        self.connection.execute(
            """
            UPDATE registered_servers
            SET
                enabled = 1,
                updated_at = ?
            WHERE guild_id = ?;
            """,
            (
                now,
                guild_id,
            ),
        )

    def is_registered(self, guild_id: int) -> bool:
        """
        サーバーが有効登録されているか確認する。
        """
        cursor = self.connection.execute(
            """
            SELECT 1
            FROM registered_servers
            WHERE guild_id = ?
              AND enabled = 1;
            """,
            (guild_id,),
        )

        return cursor.fetchone() is not None

    def get_by_guild_id(self, guild_id: int) -> Optional[sqlite3.Row]:
        """
        guild_id からサーバー情報を取得する。
        """
        cursor = self.connection.execute(
            """
            SELECT
                guild_id,
                guild_name,
                community_name,
                registered_at,
                updated_at,
                enabled
            FROM registered_servers
            WHERE guild_id = ?;
            """,
            (guild_id,),
        )

        return cursor.fetchone()

    def get_all(self) -> list[sqlite3.Row]:
        """
        登録済みサーバーをすべて取得する。
        """
        cursor = self.connection.execute(
            """
            SELECT
                guild_id,
                guild_name,
                community_name,
                registered_at,
                updated_at,
                enabled
            FROM registered_servers
            ORDER BY registered_at DESC;
            """
        )

        return cursor.fetchall()