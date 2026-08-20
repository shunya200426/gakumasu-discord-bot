"""
ユーザーから提供された画像の保存を担当するサービス。
"""

from __future__ import annotations

import asyncio
import json
import os
import shutil
import threading
import zoneinfo
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from config.bot_settings import IMAGE_RETENTION_DAYS
from config.paths import PROVIDED_UPLOAD_DIR
from utils.logger import get_logger

UTC = timezone.utc
JST = zoneinfo.ZoneInfo("Asia/Tokyo")

logger = get_logger()


class ImageStorageService:
    """
    入力画像と付随するメタデータを保存する。

    Discord通知、同意状態の判定、推論、
    OCR、DB保存は担当しない。
    """

    def __init__(
        self,
        *,
        provided_directory: Path = PROVIDED_UPLOAD_DIR,
        retention_days: int = IMAGE_RETENTION_DAYS,
    ) -> None:
        if retention_days <= 0:
            raise ValueError(
                "retention_days must be greater than 0"
            )

        self._provided_directory = provided_directory
        self._retention_days = retention_days
        self._metadata_lock = threading.Lock()

    async def save_input_images(
        self,
        *,
        guild_id: int,
        user_id: int,
        command_name: str,
        request_id: str,
        images: dict[str, tuple[str, bytes]],
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, str]:
        """
        入力画像とメタデータを別スレッドで保存する。

        Args:
            guild_id:
                DiscordサーバーID。
            user_id:
                DiscordユーザーID。
            command_name:
                実行されたコマンド名。
            request_id:
                コマンド実行単位の相関ID。
            images:
                画像種別をキーとし、
                元ファイル名と画像バイト列を持つ辞書。
            metadata:
                保存する追加メタデータ。

        Returns:
            画像種別をキー、保存パスを値とする辞書。

        Raises:
            ValueError:
                引数や画像データが不正な場合。
            OSError:
                ディレクトリ作成や保存に失敗した場合。
        """
        return await asyncio.to_thread(
            self._save_input_images_sync,
            guild_id=guild_id,
            user_id=user_id,
            command_name=command_name,
            request_id=request_id,
            images=images,
            metadata=metadata,
        )

    def _save_input_images_sync(
        self,
        *,
        guild_id: int,
        user_id: int,
        command_name: str,
        request_id: str,
        images: dict[str, tuple[str, bytes]],
        metadata: dict[str, Any] | None,
    ) -> dict[str, str]:
        """
        入力画像とメタデータを同期的に保存する。
        """
        if not request_id:
            raise ValueError("request_id must not be empty")

        if not images:
            raise ValueError("images must not be empty")

        target_directory = (
            self._provided_directory
            / self._today_string()
            / str(guild_id)
            / str(user_id)
        )

        target_directory.mkdir(
            parents=True,
            exist_ok=True,
        )

        timestamp = self._local_now_string()
        saved_paths: dict[str, str] = {}

        for image_role, (
            original_filename,
            image_bytes,
        ) in images.items():
            if not image_role:
                raise ValueError(
                    "image_role must not be empty"
                )

            if not image_bytes:
                raise ValueError(
                    f"image data is empty: role={image_role}"
                )

            extension = self._safe_extension(
                original_filename
            )

            image_path = (
                target_directory
                / (
                    f"{timestamp}_"
                    f"{request_id}_"
                    f"{image_role}"
                    f"{extension}"
                )
            )

            image_path.write_bytes(image_bytes)

            saved_paths[image_role] = str(image_path)

        self._append_metadata(
            target_directory=target_directory,
            guild_id=guild_id,
            user_id=user_id,
            command_name=command_name,
            request_id=request_id,
            saved_paths=saved_paths,
            metadata=metadata,
        )

        self._purge_expired_directories()

        logger.info(
            "Input images saved: "
            "request_id=%s directory=%s images=%d",
            request_id,
            target_directory,
            len(saved_paths),
        )

        return saved_paths

    def _append_metadata(
        self,
        *,
        target_directory: Path,
        guild_id: int,
        user_id: int,
        command_name: str,
        request_id: str,
        saved_paths: dict[str, str],
        metadata: dict[str, Any] | None,
    ) -> None:
        """
        保存画像に付随するメタデータをJSONLへ追記する。
        """
        record = {
            "timestamp_local": datetime.now(
                JST
            ).isoformat(timespec="seconds"),
            "timestamp_utc": datetime.now(
                UTC
            ).isoformat(timespec="seconds"),
            "guild_id": guild_id,
            "user_id": user_id,
            "command_name": command_name,
            "request_id": request_id,
            "retention_days": self._retention_days,
            "image_paths": saved_paths,
            **(metadata or {}),
        }

        metadata_path = (
            target_directory / "metadata.jsonl"
        )

        serialized = (
            json.dumps(
                record,
                ensure_ascii=False,
            )
            + "\n"
        )

        with self._metadata_lock, metadata_path.open(
            "a",
            encoding="utf-8",
        ) as file:
            file.write(serialized)

    def _purge_expired_directories(self) -> None:
        """
        保存期間を超過した日付ディレクトリを削除する。
        """
        if not self._provided_directory.exists():
            return

        cutoff = datetime.now(JST).date() - timedelta(
            days=self._retention_days
        )

        for directory in (
            self._provided_directory.iterdir()
        ):
            if not directory.is_dir():
                continue

            try:
                directory_date = datetime.strptime(
                    directory.name,
                    "%Y-%m-%d",
                ).date()

            except ValueError:
                continue

            if directory_date >= cutoff:
                continue

            shutil.rmtree(directory)

            logger.info(
                "Expired image directory removed: %s",
                directory,
            )

    @staticmethod
    def _safe_extension(
        filename: str,
    ) -> str:
        """
        保存を許可する画像拡張子を返す。

        許可されていない拡張子または拡張子なしの場合は
        `.bin` を返す。
        """
        extension = os.path.splitext(
            filename or ""
        )[1].lower()

        if extension in {
            ".png",
            ".jpg",
            ".jpeg",
            ".webp",
        }:
            return extension

        return ".bin"

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