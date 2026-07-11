# db/repositories/inference_repository.py

import sqlite3
from datetime import datetime, timezone
from typing import Optional


class InferenceRepository:
    """
    inference_logs / detection_results テーブルを操作するRepository。
    """

    def __init__(self, connection: sqlite3.Connection) -> None:
        self.connection = connection

    def save_inference_log(
        self,
        request_id: str,
        guild_id: Optional[int],
        channel_id: Optional[int],
        user_id: Optional[int],
        command_name: Optional[str],
        image_path: str,
        export_path: Optional[str],
        model_name: str,
        model_format: str,
        image_width: Optional[int],
        image_height: Optional[int],
        preprocess_ms: Optional[float],
        inference_ms: Optional[float],
        postprocess_ms: Optional[float],
        total_ms: Optional[float],
        status: str,
    ) -> int:
        """
        推論ログを保存し、作成された inference_logs.id を返す。
        """
        now = datetime.now(timezone.utc).isoformat()

        cursor = self.connection.execute(
            """
            INSERT INTO inference_logs (
                request_id,
                guild_id,
                channel_id,
                user_id,
                command_name,
                image_path,
                export_path,
                model_name,
                model_format,
                image_width,
                image_height,
                preprocess_ms,
                inference_ms,
                postprocess_ms,
                total_ms,
                status,
                created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
            """,
            (
                request_id,
                guild_id,
                channel_id,
                user_id,
                command_name,
                image_path,
                export_path,
                model_name,
                model_format,
                image_width,
                image_height,
                preprocess_ms,
                inference_ms,
                postprocess_ms,
                total_ms,
                status,
                now,
            ),
        )

        return cursor.lastrowid

    def save_detection_result(
        self,
        request_id: str,
        inference_log_id: int,
        class_name: str,
        confidence: Optional[float],
        x1: float,
        y1: float,
        x2: float,
        y2: float,
        crop_path: Optional[str],
    ) -> int:
        """
        YOLOの検出結果を保存し、作成された detection_results.id を返す。
        """
        now = datetime.now(timezone.utc).isoformat()

        cursor = self.connection.execute(
            """
            INSERT INTO detection_results (
                request_id,
                inference_log_id,
                class_name,
                confidence,
                x1,
                y1,
                x2,
                y2,
                crop_path,
                created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
            """,
            (
                request_id,
                inference_log_id,
                class_name,
                confidence,
                x1,
                y1,
                x2,
                y2,
                crop_path,
                now,
            ),
        )

        return cursor.lastrowid

    def get_recent_inferences(self, limit: int = 20) -> list[sqlite3.Row]:
        """
        直近の推論ログを取得する。
        """
        cursor = self.connection.execute(
            """
            SELECT
                inference_logs.id,
                inference_logs.request_id,
                inference_logs.guild_id,
                registered_servers.guild_name,
                registered_servers.community_name,
                inference_logs.channel_id,
                inference_logs.user_id,
                users.user_name,
                users.display_name,
                inference_logs.command_name,
                inference_logs.image_path,
                inference_logs.export_path,
                inference_logs.model_name,
                inference_logs.model_format,
                inference_logs.image_width,
                inference_logs.image_height,
                inference_logs.preprocess_ms,
                inference_logs.inference_ms,
                inference_logs.postprocess_ms,
                inference_logs.total_ms,
                inference_logs.status,
                inference_logs.created_at
            FROM inference_logs
            LEFT JOIN registered_servers
                ON inference_logs.guild_id = registered_servers.guild_id
            LEFT JOIN users
                ON inference_logs.user_id = users.user_id
            ORDER BY inference_logs.created_at DESC
            LIMIT ?;
            """,
            (limit,),
        )

        return cursor.fetchall()

    def get_failed_inferences(self, limit: int = 20) -> list[sqlite3.Row]:
        """
        失敗した推論ログを取得する。
        """
        cursor = self.connection.execute(
            """
            SELECT
                id,
                request_id,
                guild_id,
                channel_id,
                user_id,
                command_name,
                image_path,
                export_path,
                model_name,
                model_format,
                total_ms,
                status,
                created_at
            FROM inference_logs
            WHERE status != 'SUCCESS'
            ORDER BY created_at DESC
            LIMIT ?;
            """,
            (limit,),
        )

        return cursor.fetchall()

    def get_detection_results_by_inference_id(
        self,
        inference_log_id: int,
    ) -> list[sqlite3.Row]:
        """
        指定した推論ログに紐づく検出結果を取得する。
        """
        cursor = self.connection.execute(
            """
            SELECT
                id,
                request_id,
                inference_log_id,
                class_name,
                confidence,
                x1,
                y1,
                x2,
                y2,
                crop_path,
                created_at
            FROM detection_results
            WHERE inference_log_id = ?
            ORDER BY id ASC;
            """,
            (inference_log_id,),
        )

        return cursor.fetchall()
    
    def get_statistics(self) -> sqlite3.Row:
        """
        推論ログと検出結果の統計情報を取得する。
        """
        cursor = self.connection.execute(
            """
            SELECT
                COUNT(*) AS total_inferences,
                SUM(
                    CASE
                        WHEN status = 'SUCCESS' THEN 1
                        ELSE 0
                    END
                ) AS successful_inferences,
                SUM(
                    CASE
                        WHEN status != 'SUCCESS' THEN 1
                        ELSE 0
                    END
                ) AS failed_inferences,
                AVG(preprocess_ms) AS average_preprocess_ms,
                AVG(inference_ms) AS average_inference_ms,
                AVG(postprocess_ms) AS average_postprocess_ms,
                AVG(total_ms) AS average_total_ms,
                MIN(total_ms) AS minimum_total_ms,
                MAX(total_ms) AS maximum_total_ms,
                (
                    SELECT COUNT(*)
                    FROM detection_results
                ) AS total_detections
            FROM inference_logs;
            """
        )

        return cursor.fetchone()