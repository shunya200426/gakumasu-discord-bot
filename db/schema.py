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
        updated_at TEXT NOT NULL,
        image_save_consent INTEGER
            CHECK (image_save_consent IN (0, 1)),
        image_save_consent_updated_at TEXT
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS blocked_users (
        user_id INTEGER PRIMARY KEY,
        reason TEXT,
        user_message TEXT,
        blocked_at TEXT NOT NULL,
        blocked_by INTEGER,
        FOREIGN KEY (user_id) REFERENCES users(user_id),
        FOREIGN KEY (blocked_by) REFERENCES users(user_id)
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS command_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        request_id TEXT UNIQUE NOT NULL,
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
        request_id TEXT,
        guild_id INTEGER,
        user_id INTEGER,
        error_type TEXT NOT NULL,
        message TEXT,
        created_at TEXT NOT NULL,
        FOREIGN KEY (request_id) REFERENCES command_logs(request_id),
        FOREIGN KEY (guild_id) REFERENCES registered_servers(guild_id),
        FOREIGN KEY (user_id) REFERENCES users(user_id)
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS inference_logs (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        request_id      TEXT NOT NULL,
        guild_id        INTEGER,
        channel_id      INTEGER,
        user_id         INTEGER,
        command_name    TEXT NOT NULL,

        image_role      TEXT NOT NULL
            CHECK (
                image_role IN (
                    'schedule',
                    'party',
                    'score',
                    'mid_exam_score',
                    'final_exam_score'
                )
            ),

        image_path      TEXT,
        export_path     TEXT,

        model_name      TEXT NOT NULL,
        model_format    TEXT NOT NULL,

        image_width     INTEGER,
        image_height    INTEGER,

        preprocess_ms   REAL,
        inference_ms    REAL,
        postprocess_ms  REAL,
        total_ms        REAL,

        status          TEXT NOT NULL
            CHECK (
                status IN (
                    'SUCCESS',
                    'OCR_FAILED',
                    'ERROR'
                )
            ),

        created_at      TEXT NOT NULL,

        FOREIGN KEY (guild_id)
            REFERENCES registered_servers(guild_id),

        FOREIGN KEY (user_id)
            REFERENCES users(user_id)
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS detection_results (
        id                INTEGER PRIMARY KEY AUTOINCREMENT,
        inference_log_id  INTEGER NOT NULL,
        class_name        TEXT NOT NULL,
        confidence        REAL,
        x1                REAL NOT NULL,
        y1                REAL NOT NULL,
        x2                REAL NOT NULL,
        y2                REAL NOT NULL,
        crop_path         TEXT,
        created_at        TEXT NOT NULL,

        FOREIGN KEY (inference_log_id)
            REFERENCES inference_logs(id)
            ON DELETE CASCADE
    );
    """,
    """
    CREATE INDEX IF NOT EXISTS
        idx_inference_logs_request_id
    ON inference_logs(request_id);
    """,
    """
    CREATE INDEX IF NOT EXISTS
        idx_inference_logs_created_at
    ON inference_logs(created_at);
    """,
    """
    CREATE INDEX IF NOT EXISTS
        idx_inference_logs_status
    ON inference_logs(status);
    """,
    """
    CREATE INDEX IF NOT EXISTS
        idx_detection_results_inference_log_id
    ON detection_results(inference_log_id);
    """,
]


def _migrate_inference_roles(connection: sqlite3.Connection, old_sql: str) -> None:
    """Copy the parent table without renaming it or cascading into its children."""
    indexes = connection.execute(
        "SELECT sql FROM sqlite_master WHERE type = 'index' "
        "AND tbl_name = 'inference_logs' AND sql IS NOT NULL"
    ).fetchall()
    sequence = connection.execute(
        "SELECT seq FROM sqlite_sequence WHERE name = 'inference_logs'"
    ).fetchone()
    new_sql = old_sql.replace(
        "'score'", "'score', 'mid_exam_score', 'final_exam_score'"
    )
    # sqlite_master contains the original CREATE statement, including quoted names.
    opening = new_sql.index("(")
    connection.execute("CREATE TABLE inference_logs_new " + new_sql[opening:])
    connection.execute("INSERT INTO inference_logs_new SELECT * FROM inference_logs")
    connection.execute("DROP TABLE inference_logs")
    connection.execute("ALTER TABLE inference_logs_new RENAME TO inference_logs")
    if sequence is not None:
        connection.execute(
            "UPDATE sqlite_sequence SET seq = MAX(seq, ?) WHERE name = 'inference_logs'",
            (sequence[0],),
        )
    for (sql,) in indexes:
        connection.execute(sql)


def create_tables(connection: sqlite3.Connection) -> None:
    """Initialize tables and atomically upgrade the old image role constraint."""
    if connection.in_transaction:
        raise RuntimeError("テーブル初期化はトランザクション外で実行してください。")
    foreign_keys = connection.execute("PRAGMA foreign_keys").fetchone()[0]
    row = connection.execute(
        "SELECT sql FROM sqlite_master WHERE type = 'table' AND name = 'inference_logs'"
    ).fetchone()
    migrate = row is not None and "'mid_exam_score'" not in row[0]
    if migrate:
        connection.execute("PRAGMA foreign_keys = OFF")
    try:
        connection.execute("BEGIN IMMEDIATE")
        if migrate:
            _migrate_inference_roles(connection, row[0])
        for query in CREATE_TABLE_QUERIES:
            connection.execute(query)
        if connection.execute("PRAGMA foreign_key_check").fetchone() is not None:
            raise sqlite3.IntegrityError("DB初期化後の外部キーに不整合があります。")
        connection.commit()
    except BaseException:
        connection.rollback()
        raise
    finally:
        if migrate:
            connection.execute(f"PRAGMA foreign_keys = {foreign_keys}")
