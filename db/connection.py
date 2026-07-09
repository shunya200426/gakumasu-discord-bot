import sqlite3
from pathlib import Path
from types import TracebackType
from typing import Optional, Type

class SQLiteConnection:
    """
    SQLite接続を管理するクラス。

    SQLの実行内容はRepository側に任せ、
    このクラスでは接続・終了・トランザクション管理のみを担当する。
    """

    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        self.connection: Optional[sqlite3.Connection] = None

    def connect(self) -> sqlite3.Connection:
        """
        SQLiteへ接続する。
        すでに接続済みの場合は既存の接続を返す。
        """
        if self.connection is None:
            self.db_path.parent.mkdir(parents=True, exist_ok=True)

            self.connection = sqlite3.connect(self.db_path)
            self.connection.row_factory = sqlite3.Row

            # 外部キー制約を有効化
            self.connection.execute("PRAGMA foreign_keys = ON;")

        return self.connection

    def close(self) -> None:
        """
        SQLite接続を閉じる。
        """
        if self.connection is not None:
            self.connection.close()
            self.connection = None

    def commit(self) -> None:
        """
        現在のトランザクションを確定する。
        """
        if self.connection is not None:
            self.connection.commit()

    def rollback(self) -> None:
        """
        現在のトランザクションを取り消す。
        """
        if self.connection is not None:
            self.connection.rollback()

    def __enter__(self) -> sqlite3.Connection:
        """
        with文で利用できるようにする。
        """
        return self.connect()

    def __exit__(
        self,
        exc_type: Optional[Type[BaseException]],
        exc_value: Optional[BaseException],
        traceback: Optional[TracebackType],
    ) -> None:
        """
        with文終了時の処理。

        例外がなければcommit、
        例外があればrollbackする。

        接続自体は維持し、
        Bot終了時にclose()する。
        """
        if self.connection is None:
            return

        if exc_type is None:
            self.connection.commit()
        else:
            self.connection.rollback()