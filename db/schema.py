# db/schema.py

import sqlite3


CREATE_TABLE_QUERIES = [
    """
    CREATE TABLE IF NOT EXISTS registered_servers (
        guild_id INTEGER PRIMARY KEY,
        guild_name TEXT,
        community_name TEXT NOT NULL,
        registered_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        enabled INTEGER NOT NULL DEFAULT 1
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY,
        user_name TEXT,
        display_name TEXT,
        updated_at TEXT NOT NULL
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS blocked_users (
        user_id INTEGER PRIMARY KEY,
        reason TEXT,
        blocked_at TEXT NOT NULL,
        blocked_by INTEGER,
        FOREIGN KEY (user_id) REFERENCES users(user_id),
        FOREIGN KEY (blocked_by) REFERENCES users(user_id)
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS command_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        command_id TEXT UNIQUE NOT NULL,
        guild_id INTEGER,
        channel_id INTEGER,
        user_id INTEGER,
        command_name TEXT NOT NULL,
        status TEXT NOT NULL,
        created_at TEXT NOT NULL,
        FOREIGN KEY (guild_id) REFERENCES registered_servers(guild_id),
        FOREIGN KEY (user_id) REFERENCES users(user_id)
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS error_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        command_id TEXT,
        guild_id INTEGER,
        user_id INTEGER,
        error_type TEXT NOT NULL,
        message TEXT,
        created_at TEXT NOT NULL,
        FOREIGN KEY (command_id) REFERENCES command_logs(command_id),
        FOREIGN KEY (guild_id) REFERENCES registered_servers(guild_id),
        FOREIGN KEY (user_id) REFERENCES users(user_id)
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS inference_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        command_id TEXT NOT NULL,
        guild_id INTEGER,
        channel_id INTEGER,
        user_id INTEGER,
        command_name TEXT,
        image_path TEXT NOT NULL,
        export_path TEXT,
        model_name TEXT NOT NULL,
        model_format TEXT NOT NULL,
        image_width INTEGER,
        image_height INTEGER,
        preprocess_ms REAL,
        inference_ms REAL,
        postprocess_ms REAL,
        total_ms REAL,
        status TEXT NOT NULL,
        created_at TEXT NOT NULL,
        FOREIGN KEY (command_id) REFERENCES command_logs(command_id),
        FOREIGN KEY (guild_id) REFERENCES registered_servers(guild_id),
        FOREIGN KEY (user_id) REFERENCES users(user_id)
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS detection_results (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        inference_log_id INTEGER NOT NULL,
        class_name TEXT NOT NULL,
        confidence REAL,
        x1 REAL NOT NULL,
        y1 REAL NOT NULL,
        x2 REAL NOT NULL,
        y2 REAL NOT NULL,
        crop_path TEXT,
        created_at TEXT NOT NULL,
        FOREIGN KEY (inference_log_id) REFERENCES inference_logs(id)
            ON DELETE CASCADE
    );
    """,
]


def create_tables(connection: sqlite3.Connection) -> None:
    """
    必要なテーブルを作成する。
    """
    for query in CREATE_TABLE_QUERIES:
        connection.execute(query)

    connection.commit()