import asyncio
import hashlib
import json
import os
import shutil
import uuid
import zoneinfo
from abc import ABC, abstractmethod
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from typing import cast

import discord
from discord import Embed, Interaction, ui

from config.paths import PROVIDED_UPLOAD_DIR
from services.image_consent_service import (
    ImageConsentResult,
    ImageConsentService,
)
from services.inference_log_recorder import InferenceLogRecorder
from utils.context import build_ctx_from_interaction
from utils.logger import get_logger, use_log_context

KEEP_DAYS = 30
MAX_IMAGE_BYTES = 10 * 1024 * 1024

UTC = timezone.utc
JST = zoneinfo.ZoneInfo("Asia/Tokyo")

logger = get_logger()


def _utc_now_str(
    fmt: str = "%Y%m%dT%H%M%S.%fZ",
) -> str:
    """現在のUTC時刻を指定形式で返す。"""
    return datetime.now(UTC).strftime(fmt)


def _local_now_str(
    fmt: str = "%Y%m%dT%H%M%S",
) -> str:
    """現在のJST時刻を指定形式で返す。"""
    return datetime.now(JST).strftime(fmt)


def _today_str() -> str:
    """現在のJST日付をディレクトリ名用の形式で返す。"""
    return datetime.now(JST).strftime("%Y-%m-%d")


def _short_hash(
    data: bytes,
    length: int = 8,
) -> str:
    """バイト列のSHA-256ハッシュを短縮して返す。"""
    return hashlib.sha256(data).hexdigest()[:length]


def _safe_ext(
    filename: str,
) -> str:
    """
    保存を許可する画像拡張子を返す。

    許可外、または拡張子なしの場合は.binを返す。
    """
    extension = os.path.splitext(filename or "")[1].lower()

    if extension in {
        ".png",
        ".jpg",
        ".jpeg",
        ".webp",
    }:
        return extension

    return ".bin"


class BaseCommand(ABC):
    """
    全コマンド共通の基底クラス。
    """

    def __init__(
        self,
        interaction: Interaction,
    ) -> None:
        self.interaction = interaction
        self.embed = self._init_embed()
        self._request_id: str | None = None

    def _init_embed(self) -> Embed:
        """共通のEmbedを初期化する。"""
        return Embed(color=0x5DADE2)

    def log_command_start(
        self,
        command_name: str,
    ) -> None:
        """コマンド開始ログを記録する。"""
        logger.info(
            "コマンド実行開始: %s",
            command_name,
        )

    def log_command_end(
        self,
        command_name: str,
    ) -> None:
        """コマンド終了ログを記録する。"""
        logger.info(
            "コマンド実行完了: %s",
            command_name,
        )

    def log_recompute_start(
        self,
        command_name: str,
    ) -> None:
        """再計算開始ログを記録する。"""
        logger.info(
            "再計算実行開始: %s",
            command_name,
        )

    def log_recompute_end(
        self,
        command_name: str,
    ) -> None:
        """再計算終了ログを記録する。"""
        logger.info(
            "再計算実行完了: %s",
            command_name,
        )

    async def read_image_attachment(
        self,
        attachment: discord.Attachment | None,
        *,
        label: str,
        required: bool = True,
        max_bytes: int = MAX_IMAGE_BYTES,
    ) -> bytes | None:
        """
        Discordの画像添付を検証し、バイト列として読み込む。

        Args:
            attachment:
                読み込むDiscord添付ファイル。
            label:
                エラーメッセージに表示する画像の名称。
            required:
                Trueの場合、添付がない場合にValueErrorを送出する。
                Falseの場合、添付がなければNoneを返す。
            max_bytes:
                読み込みを許可する最大ファイルサイズ。

        Returns:
            添付画像のバイト列。
            required=Falseかつ添付がない場合はNone。

        Raises:
            ValueError:
                必須画像が未添付、画像以外、サイズ超過、
                または空データの場合。
        """
        if max_bytes <= 0:
            raise ValueError(
                "max_bytes must be greater than 0"
            )

        if attachment is None:
            if required:
                raise ValueError(
                    f"{label}を添付してください。"
                )

            return None

        content_type = attachment.content_type

        if (
            content_type is None
            or not content_type.startswith("image/")
        ):
            raise ValueError(
                f"{label}には画像ファイルを指定してください。"
            )

        if attachment.size > max_bytes:
            max_megabytes = max_bytes / (1024 * 1024)

            raise ValueError(
                f"{label}のファイルサイズが大きすぎます。"
                f"{max_megabytes:.0f}MB以下の画像を指定してください。"
            )

        image_bytes = await attachment.read()

        if not image_bytes:
            raise ValueError(
                f"{label}の画像データが空です。"
            )

        return image_bytes
    
    def get_inference_log_recorder(
        self,
        interaction: discord.Interaction,
    ) -> InferenceLogRecorder:
        """
        Botが保持しているInferenceLogRecorderを取得する。
        """

        recorder = cast(
            InferenceLogRecorder | None,
            getattr(
                interaction.client,
                "inference_log_recorder",
                None,
            ),
        )

        if recorder is None:
            raise RuntimeError(
                "InferenceLogRecorderが"
                "初期化されていません。"
            )

        return recorder

    def get_image_consent_service(
        self,
        interaction: discord.Interaction,
    ) -> ImageConsentService:
        """
        Botが保持しているImageConsentServiceを取得する。
        """
        service = cast(
            ImageConsentService | None,
            getattr(
                interaction.client,
                "image_consent_service",
                None,
            ),
        )

        if service is None:
            raise RuntimeError(
                "ImageConsentServiceが"
                "初期化されていません。"
            )

        return service

    def resolve_image_consent(
        self,
        *,
        interaction: discord.Interaction,
        requested: bool | None,
    ) -> ImageConsentResult:
        """
        画像保存同意を解決する。

        同意結果は呼び出し側へ返し、このインスタンスには保持しない。
        """
        service = self.get_image_consent_service(
            interaction
        )
        result = service.resolve(
            user_id=interaction.user.id,
            requested=requested,
        )

        return result

    async def send_image_consent_notification(
        self,
        result: ImageConsentResult,
    ) -> None:
        """
        同意状態が変化した場合のみユーザーへ通知する。

        original response確定後に呼び出すことを前提とする。
        """
        if not result.changed:
            return

        if result.current:
            message = (
                "画像保存へのご協力ありがとうございます！\n"
                "今後は設定を変更するまで、入力画像および"
                "推論・切り抜き画像を保存します。"
            )
        else:
            message = (
                "画像保存を無効にしました。\n"
                "今回以降の入力画像および推論・切り抜き画像は"
                "保存されません。"
            )

        await self._safe_send(
            content=message,
            ephemeral=True,
        )

    @property
    def request_id(self) -> str:
        """
        現在のコマンド実行に割り当てられたrequest_idを返す。
        """
        if self._request_id is None:
            raise RuntimeError(
                "request_idが初期化されていません。"
            )

        return self._request_id

    @asynccontextmanager
    async def scoped_ctx(
        self,
        interaction: Interaction,
    ):
        """
        任意のInteraction区間へログコンテキストを適用する。

        再計算、Modal、Button、Selectなど、
        execute()以外の入口で使用する。
        """
        try:
            ctx = await build_ctx_from_interaction(
                interaction
            )
        except Exception:
            ctx = {}

        if self._request_id:
            ctx = {
                "request_id": self._request_id,
                **ctx,
            }

        with use_log_context(ctx):
            yield

    async def send_embed(self) -> None:
        """EmbedメッセージをDiscordへ送信する。"""
        await self._safe_send(
            embed=self.embed
        )

    async def _safe_send(
        self,
        *,
        content: str | None = None,
        embed: Embed | None = None,
        view: ui.View | None = None,
        ephemeral: bool = False,
    ) -> None:
        """
        Interactionの応答状態に応じてメッセージを送信する。
        """
        kwargs: dict = {
            "ephemeral": ephemeral,
        }

        if content is not None:
            kwargs["content"] = content

        if embed is not None:
            kwargs["embed"] = embed

        if view is not None:
            kwargs["view"] = view

        try:
            if self.interaction.response.is_done():
                await self.interaction.followup.send(
                    **kwargs,
                )
            else:
                await self.interaction.response.send_message(
                    **kwargs,
                )

        except Exception:
            logger.warning(
                "send failed",
                exc_info=True,
            )

    @staticmethod
    def _purge_old_days() -> None:
        """
        保存期間を超過した提供画像ディレクトリを削除する。
        """
        cutoff = datetime.now(JST) - timedelta(
            days=KEEP_DAYS
        )

        if not PROVIDED_UPLOAD_DIR.exists():
            return

        for directory in PROVIDED_UPLOAD_DIR.iterdir():
            if not directory.is_dir():
                continue

            try:
                directory_date = datetime.strptime(
                    directory.name,
                    "%Y-%m-%d",
                ).replace(
                    tzinfo=JST
                )

            except ValueError:
                continue

            if directory_date < cutoff:
                shutil.rmtree(
                    directory,
                    ignore_errors=True,
                )

                logger.info(
                    "Old archive directory removed: %s",
                    directory,
                )

    @staticmethod
    def _archive_sync(
        *,
        guild_id: int,
        user_id: int,
        command: str,
        images: dict[str, tuple[str, bytes]],
        meta: dict,
        request_id: str | None = None,
    ) -> None:
        """
        同意済みの入力画像とメタデータを同期的に保存する。

        Args:
            guild_id:
                DiscordサーバーID。
            user_id:
                DiscordユーザーID。
            command:
                実行されたコマンド名。
            images:
                画像種別をキーとし、
                ファイル名とバイト列を保持する辞書。
            meta:
                JSONLへ追加する任意メタデータ。
            request_id:
                コマンド実行単位の相関ID。
        """
        day_dir = (
            PROVIDED_UPLOAD_DIR
            / _today_str()
            / str(guild_id)
            / str(user_id)
        )

        day_dir.mkdir(
            parents=True,
            exist_ok=True,
        )

        timestamp = _local_now_str()
        saved_names: dict[str, str] = {}

        for key, (
            filename,
            image_bytes,
        ) in images.items():
            if not image_bytes:
                logger.warning(
                    "Empty archive image skipped: key=%s",
                    key,
                )
                continue

            extension = _safe_ext(filename)

            image_id = (
                request_id
                or _short_hash(image_bytes)
            )

            image_path = (
                day_dir
                / (
                    f"{timestamp}_"
                    f"{image_id}_"
                    f"{key}"
                    f"{extension}"
                )
            )

            with image_path.open("wb") as file:
                file.write(image_bytes)

            saved_names[f"{key}_file"] = (
                image_path.name
            )

        record = {
            "ts_local": datetime.now(JST).isoformat(
                timespec="seconds"
            ),
            "ts_utc": _utc_now_str(
                "%Y-%m-%dT%H:%M:%SZ"
            ),
            "guild_id": guild_id,
            "user_id": user_id,
            "command": command,
            "request_id": request_id,
            "keep_policy": f"{KEEP_DAYS}days",
            **saved_names,
            **meta,
        }

        metadata_path = (
            day_dir
            / "metadata.jsonl"
        )

        with metadata_path.open(
            "a",
            encoding="utf-8",
        ) as file:
            file.write(
                json.dumps(
                    record,
                    ensure_ascii=False,
                )
                + "\n"
            )

        BaseCommand._purge_old_days()

        logger.info(
            "Archive saved: directory=%s images=%d",
            day_dir,
            len(saved_names),
        )

    @staticmethod
    async def _archive_async(
        **kwargs,
    ) -> None:
        """
        同期的な画像保存処理を別スレッドで実行する。
        """
        await asyncio.to_thread(
            BaseCommand._archive_sync,
            **kwargs,
        )

    async def maybe_archive_inputs(
        self,
        *,
        interaction: Interaction,
        save_agree: bool,
        command: str,
        images: dict[str, tuple[str, bytes]],
        meta: dict,
    ) -> None:
        """
        ユーザーが同意した場合のみ入力画像を保存する。

        画像保存の失敗は、コマンド本体の成否には影響させない。
        """
        if not save_agree:
            return

        try:
            await BaseCommand._archive_async(
                guild_id=interaction.guild_id,
                user_id=interaction.user.id,
                command=command,
                images=images,
                meta=meta,
                request_id=self._request_id,
            )

        except Exception:
            logger.warning(
                "Input archive failed",
                exc_info=True,
            )

    def __init_subclass__(
        cls,
        **kwargs,
    ) -> None:
        """
        サブクラスのexecute()へ共通ログコンテキストを適用する。
        """
        super().__init_subclass__(
            **kwargs
        )

        original_execute = getattr(
            cls,
            "execute",
            None,
        )

        if (
            original_execute is None
            or not asyncio.iscoroutinefunction(
                original_execute
            )
        ):
            return

        async def _wrapped(
            self,
            *args,
            **kwargs,
        ):
            if getattr(
                self,
                "_request_id",
                None,
            ) is None:
                self._request_id = (
                    uuid.uuid4().hex[:8]
                )

            interaction = getattr(
                self,
                "interaction",
                None,
            )

            try:
                ctx = (
                    await build_ctx_from_interaction(
                        interaction
                    )
                    if interaction
                    else {}
                )

            except Exception:
                ctx = {}

            if self._request_id:
                ctx = {
                    "request_id": self._request_id,
                    **ctx,
                }

            with use_log_context(ctx):
                return await original_execute(
                    self,
                    *args,
                    **kwargs,
                )

        setattr(
            cls,
            "execute",
            _wrapped,
        )

    @abstractmethod
    async def execute(
        self,
        *args,
        **kwargs,
    ):
        """
        コマンドのメイン処理。

        各コマンドで必ず実装する。
        """
        raise NotImplementedError
