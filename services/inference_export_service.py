"""
推論結果JSONの保存を担当するサービス。
"""

from __future__ import annotations

import asyncio
import json
import zoneinfo
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Literal

from config.paths import INFERENCE_EXPORT_DIR
from inference.result import InferenceResult
from utils.logger import get_logger

JST = zoneinfo.ZoneInfo("Asia/Tokyo")

logger = get_logger()

ImageRole = Literal[
    "schedule",
    "party",
    "score",
]


class InferenceExportService:
    """
    推論結果をJSONファイルとして保存する。

    Discord通知、DB保存、画像保存、
    推論・OCR処理は担当しない。
    """

    def __init__(
        self,
        *,
        export_directory: Path = INFERENCE_EXPORT_DIR,
    ) -> None:
        self._export_directory = export_directory

    async def save(
        self,
        *,
        guild_id: int,
        user_id: int,
        request_id: str,
        image_role: ImageRole,
        inference_result: InferenceResult,
    ) -> str:
        """
        推論結果を別スレッドでJSONファイルへ保存する。

        Args:
            request_id:
                コマンド実行単位の相関ID。
            image_role:
                対象画像の種別。
            inference_result:
                保存対象の推論結果。

        Returns:
            保存したJSONファイルのパス。

        Raises:
            ValueError:
                request_idやimage_roleが不正な場合。
            OSError:
                ディレクトリ作成や保存に失敗した場合。
        """
        return await asyncio.to_thread(
            self._save_sync,
            guild_id=guild_id,
            user_id=user_id,
            request_id=request_id,
            image_role=image_role,
            inference_result=inference_result,
        )

    def _save_sync(
        self,
        *,
        guild_id: int,
        user_id: int,
        request_id: str,
        image_role: ImageRole,
        inference_result: InferenceResult,
    ) -> str:
        """
        推論結果を同期的にJSONファイルへ保存する。
        """
        if not request_id:
            raise ValueError(
                "request_id must not be empty"
            )

        if not image_role:
            raise ValueError(
                "image_role must not be empty"
            )

        target_directory = (
            self._export_directory
            / self._today_string()
            / str(guild_id)
            / str(user_id)
        )

        target_directory.mkdir(
            parents=True,
            exist_ok=True,
        )

        export_path = (
            target_directory
            / (
                f"{self._local_now_string()}_"
                f"{request_id}_"
                f"{image_role}.json"
            )
        )

        payload = {
            "request_id": request_id,
            "image_role": image_role,
            "exported_at": datetime.now(
                JST
            ).isoformat(timespec="seconds"),
            "result": asdict(inference_result),
        }

        serialized = json.dumps(
            payload,
            ensure_ascii=False,
            indent=2,
        )

        export_path.write_text(
            serialized,
            encoding="utf-8",
        )

        logger.info(
            "Inference result exported: "
            "request_id=%s role=%s path=%s",
            request_id,
            image_role,
            export_path,
        )

        return str(export_path)

    @staticmethod
    def _today_string() -> str:
        """現在のJST日付を返す。"""
        return datetime.now(JST).strftime(
            "%Y-%m-%d"
        )

    @staticmethod
    def _local_now_string() -> str:
        """ファイル名用の現在のJST日時を返す。"""
        return datetime.now(JST).strftime(
            "%Y%m%dT%H%M%S"
        )