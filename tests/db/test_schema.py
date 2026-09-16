import sqlite3

import pytest

from db import schema


def insert_log(connection, role="score", log_id=None):
    return connection.execute(
        "INSERT INTO inference_logs (id, request_id, command_name, image_role, model_name, model_format, status, created_at) VALUES (?, 'request', 'test', ?, 'model', 'onnx', 'SUCCESS', 'now')",
        (log_id, role),
    ).lastrowid


def old_database(connection):
    for sql in schema.CREATE_TABLE_QUERIES:
        connection.execute(
            sql.replace(
                "                    'score',\n                    'mid_exam_score',\n                    'final_exam_score'",
                "                    'score'",
            )
        )
    insert_log(connection, log_id=42)
    insert_log(connection, log_id=100)
    connection.execute("DELETE FROM inference_logs WHERE id=100")
    connection.execute(
        "INSERT INTO detection_results (id, inference_log_id, class_name, x1, y1, x2, y2, created_at) VALUES (7, 42, 'vo', 1, 2, 3, 4, 'now')"
    )
    connection.execute(
        "CREATE INDEX custom_inference_index ON inference_logs(command_name)"
    )
    connection.commit()


@pytest.fixture
def connection(tmp_path):
    connection = sqlite3.connect(tmp_path / "test.sqlite3")
    connection.execute("PRAGMA foreign_keys=ON")
    yield connection
    connection.close()


@pytest.mark.parametrize("old", [False, True])
def test_new_and_existing_database_roles_and_idempotence(connection, old):
    if old:
        old_database(connection)
    schema.create_tables(connection)
    statements = []
    connection.set_trace_callback(statements.append)
    schema.create_tables(connection)
    assert not any("inference_logs_new" in sql for sql in statements)
    connection.set_trace_callback(None)
    if old:
        assert connection.execute("SELECT id FROM inference_logs").fetchall() == [(42,)]
        assert connection.execute(
            "SELECT id, inference_log_id FROM detection_results"
        ).fetchall() == [(7, 42)]
        assert (
            connection.execute(
                "SELECT seq FROM sqlite_sequence WHERE name='inference_logs'"
            ).fetchone()[0]
            == 100
        )
        assert "custom_inference_index" in {
            row[1] for row in connection.execute("PRAGMA index_list(inference_logs)")
        }
    first = insert_log(connection, "mid_exam_score")
    second = insert_log(connection, "final_exam_score")
    assert first > (100 if old else 0)
    assert second > first
    indexes = {
        row[1] for row in connection.execute("PRAGMA index_list(inference_logs)")
    }
    assert {
        "idx_inference_logs_request_id",
        "idx_inference_logs_created_at",
        "idx_inference_logs_status",
    } <= indexes
    assert connection.execute("PRAGMA foreign_key_check").fetchall() == []
    assert connection.execute("PRAGMA foreign_keys").fetchone()[0] == 1


def test_migration_failure_rolls_back_everything(connection, monkeypatch):
    old_database(connection)
    before = connection.execute(
        "SELECT sql FROM sqlite_master WHERE name='inference_logs'"
    ).fetchone()[0]
    monkeypatch.setattr(schema, "CREATE_TABLE_QUERIES", ["INVALID SQL"])
    with pytest.raises(sqlite3.OperationalError):
        schema.create_tables(connection)
    assert (
        connection.execute(
            "SELECT sql FROM sqlite_master WHERE name='inference_logs'"
        ).fetchone()[0]
        == before
    )
    assert connection.execute("SELECT id FROM inference_logs").fetchall() == [(42,)]
    assert connection.execute(
        "SELECT inference_log_id FROM detection_results"
    ).fetchall() == [(42,)]
    assert (
        connection.execute(
            "SELECT seq FROM sqlite_sequence WHERE name='inference_logs'"
        ).fetchone()[0]
        == 100
    )
    assert connection.execute("PRAGMA foreign_key_check").fetchall() == []
    assert connection.execute("PRAGMA foreign_keys").fetchone()[0] == 1
    assert (
        connection.execute(
            "SELECT name FROM sqlite_master WHERE name='inference_logs_new'"
        ).fetchall()
        == []
    )


def test_empty_old_table_preserves_previous_autoincrement(connection):
    old_database(connection)
    connection.execute("DELETE FROM detection_results")
    connection.execute("DELETE FROM inference_logs")
    connection.commit()
    schema.create_tables(connection)
    assert insert_log(connection, "mid_exam_score") > 100
    assert connection.execute("PRAGMA foreign_key_check").fetchall() == []
