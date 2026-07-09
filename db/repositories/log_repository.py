# db/repositories/log_repository.py

import sqlite3
from datetime import datetime, timezone
from typing import Optional


class LogRepository:
    """
    command_logs / error_logs テーブルを操作するRepository。
    """

    def __init__(self, connection: sqlite3.Connection) -> None:
        self.connection = connection

    def add_command_log(
        self,
        request_id: str,
        guild_id: Optional[int],
        channel_id: Optional[int],
        user_id: Optional[int],
        command_name: str,
        status: str,
    ) -> None:
        """
        コマンド実行ログを保存する。
        """
        now = datetime.now(timezone.utc).isoformat()

        self.connection.execute(
            """
            INSERT INTO command_logs (
                request_id,
                guild_id,
                channel_id,
                user_id,
                command_name,
                status,
                created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?);
            """,
            (
                request_id,
                guild_id,
                channel_id,
                user_id,
                command_name,
                status,
                now,
            ),
        )

    def add_error_log(
        self,
        request_id: Optional[str],
        guild_id: Optional[int],
        user_id: Optional[int],
        error_type: str,
        message: Optional[str],
    ) -> None:
        """
        エラーログを保存する。
        """
        now = datetime.now(timezone.utc).isoformat()

        self.connection.execute(
            """
            INSERT INTO error_logs (
                request_id,
                guild_id,
                user_id,
                error_type,
                message,
                created_at
            )
            VALUES (?, ?, ?, ?, ?, ?);
            """,
            (
                request_id,
                guild_id,
                user_id,
                error_type,
                message,
                now,
            ),
        )

    def get_recent_commands(self, limit: int = 20) -> list[sqlite3.Row]:
        """
        直近のコマンドログを取得する。
        """
        cursor = self.connection.execute(
            """
            SELECT
                command_logs.id,
                command_logs.request_id,
                command_logs.guild_id,
                registered_servers.guild_name,
                registered_servers.community_name,
                command_logs.channel_id,
                command_logs.user_id,
                users.user_name,
                users.display_name,
                command_logs.command_name,
                command_logs.status,
                command_logs.created_at
            FROM command_logs
            LEFT JOIN registered_servers
                ON command_logs.guild_id = registered_servers.guild_id
            LEFT JOIN users
                ON command_logs.user_id = users.user_id
            ORDER BY command_logs.created_at DESC
            LIMIT ?;
            """,
            (limit,),
        )

        return cursor.fetchall()

    def get_recent_errors(self, limit: int = 20) -> list[sqlite3.Row]:
        """
        直近のエラーログを取得する。
        """
        cursor = self.connection.execute(
            """
            SELECT
                error_logs.id,
                error_logs.request_id,
                error_logs.guild_id,
                registered_servers.guild_name,
                registered_servers.community_name,
                error_logs.user_id,
                users.user_name,
                users.display_name,
                error_logs.error_type,
                error_logs.message,
                error_logs.created_at
            FROM error_logs
            LEFT JOIN registered_servers
                ON error_logs.guild_id = registered_servers.guild_id
            LEFT JOIN users
                ON error_logs.user_id = users.user_id
            ORDER BY error_logs.created_at DESC
            LIMIT ?;
            """,
            (limit,),
        )

        return cursor.fetchall()