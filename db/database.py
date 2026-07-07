# db/database.py

import sqlite3

from config.paths import REQUIRED_DIRECTORIES, DATABASE_PATH
from db.connection import SQLiteConnection
from db.schema import create_tables


class DatabaseManager:
    """
    SQLiteデータベース全体を管理するクラス。

    起動時の初期化、必要ディレクトリの作成、
    テーブル作成、接続管理を担当する。
    """

    def __init__(self) -> None:
        self.connection_manager = SQLiteConnection(DATABASE_PATH)
        self.connection: sqlite3.Connection | None = None

    def initialize(self) -> None:
        """
        DB利用に必要な環境を初期化する。

        - 必要ディレクトリの作成
        - SQLite接続
        - テーブル作成
        """
        self._ensure_directories()

        self.connection = self.connection_manager.connect()

        create_tables(self.connection)

    def close(self) -> None:
        """
        SQLite接続を閉じる。
        """
        self.connection_manager.close()
        self.connection = None

    def _ensure_directories(self) -> None:
        """
        Botの運用に必要なディレクトリを作成する。
        """
        for directory in REQUIRED_DIRECTORIES:
            directory.mkdir(parents=True, exist_ok=True)