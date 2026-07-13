# commands/nia_commands/final_grade_from_img/command.py

from __future__ import annotations

import asyncio
import time
from typing import cast

import cv2
import discord
import numpy as np
from discord import Embed, ui

from commands.base_command import BaseCommand
from commands.nia_commands.final_grade.container_builder import (
    build_final_grade_container,
)
from models.nia.final_grade_from_img.params import (
    NiaFinalGradeFromImgParams,
)
from services.inference_service import InferenceService
from utils.logger import get_logger

from .container_builder import build_error_container
from .inference_use_case import InferenceUseCase

logger = get_logger()

COMMAND_NAME = "nia_final_grade_from_img"


# --- ラベル <-> 内部キー ---
_LABEL2KEY = {
    "Voパラメータ": "vo_status",
    "Daパラメータ": "da_status",
    "Viパラメータ": "vi_status",
    "Voパラメータボーナス": "vo_bonus",
    "Daパラメータボーナス": "da_bonus",
    "Viパラメータボーナス": "vi_bonus",
    "Voスコア": "vo_score",
    "Daスコア": "da_score",
    "Viスコア": "vi_score",
    "ファン数": "now_fans",
    "ほしのきらめき": "kirameki",
}


# --- Modal 定義 ---
class ParamEditModal(ui.Modal):
    def __init__(
        self,
        cmd: "NiaFinalGradeFromImgCommand",
        selected_params: list[str],
        current: dict,
    ) -> None:
        super().__init__(
            title="パラメータを編集"
        )

        self.cmd = cmd
        self.current = current
        self.inputs: dict[str, ui.TextInput] = {}

        for param in selected_params:
            input_box = ui.TextInput(
                label=param,
                required=False,
                default=str(
                    current.get(
                        _LABEL2KEY.get(param, ""),
                        "",
                    )
                ),
                placeholder="数値を入力",
            )

            self.add_item(input_box)
            self.inputs[param] = input_box

    async def on_submit(
        self,
        interaction: discord.Interaction,
    ) -> None:
        await interaction.response.defer()

        try:
            updates: dict[str, str] = {}

            for label, text_input in self.inputs.items():
                if text_input.value in ("", None):
                    continue

                key = _LABEL2KEY.get(label)

                if key:
                    updates[key] = text_input.value

            merged = {
                **(self.current or {}),
                **updates,
            }

            int_keys = (
                "vo_status",
                "da_status",
                "vi_status",
                "vo_score",
                "da_score",
                "vi_score",
                "now_fans",
                "kirameki",
            )

            float_keys = (
                "vo_bonus",
                "da_bonus",
                "vi_bonus",
            )

            for key in int_keys:
                if key not in merged:
                    continue

                try:
                    value = int(
                        str(merged[key]).strip() or 0
                    )

                    if value < 0:
                        raise ValueError(
                            f"{key} は0以上にしてください"
                        )

                    merged[key] = value

                except Exception as exc:
                    await interaction.followup.send(
                        embed=Embed(
                            title="入力エラー",
                            description=f"{key}: {exc}",
                        ),
                        ephemeral=True,
                    )
                    return

            for key in float_keys:
                if key not in merged:
                    continue

                try:
                    value = float(
                        str(merged[key]).strip() or 0.0
                    )

                    if value < 0:
                        raise ValueError(
                            f"{key} は0.0以上にしてください"
                        )

                    merged[key] = value

                except Exception as exc:
                    await interaction.followup.send(
                        embed=Embed(
                            title="入力エラー",
                            description=f"{key}: {exc}",
                        ),
                        ephemeral=True,
                    )
                    return

            merged["boost_month"] = bool(
                merged.get(
                    "boost_month",
                    self.cmd._static.get(
                        "is_boost_active",
                        False,
                    ),
                )
            )

            self.cmd._current_values = merged

            await self.cmd._recompute_and_edit(
                interaction,
                merged,
            )

        except Exception as exc:
            logger.exception(
                "ParamEditModal.on_submit failed"
            )

            await interaction.followup.send(
                embed=discord.Embed(
                    title="入力エラー",
                    description=(
                        f"{type(exc).__name__}: {exc}"
                    ),
                ),
                ephemeral=True,
            )


# --- プルダウン定義 ---
class ParamSelect(ui.Select):
    def __init__(
        self,
        cmd: "NiaFinalGradeFromImgCommand",
    ) -> None:
        is_boost = bool(
            getattr(
                cmd,
                "_static",
                {},
            ).get(
                "is_boost_active",
                False,
            )
        )

        options = [
            discord.SelectOption(
                label="Voパラメータ"
            ),
            discord.SelectOption(
                label="Daパラメータ"
            ),
            discord.SelectOption(
                label="Viパラメータ"
            ),
            discord.SelectOption(
                label="Voパラメータボーナス"
            ),
            discord.SelectOption(
                label="Daパラメータボーナス"
            ),
            discord.SelectOption(
                label="Viパラメータボーナス"
            ),
            discord.SelectOption(
                label="Voスコア"
            ),
            discord.SelectOption(
                label="Daスコア"
            ),
            discord.SelectOption(
                label="Viスコア"
            ),
            discord.SelectOption(
                label="ファン数"
            ),
            discord.SelectOption(
                label="ほしのきらめき"
            ),
        ]

        if not is_boost:
            options = [
                option
                for option in options
                if option.label != "ほしのきらめき"
            ]

        super().__init__(
            placeholder="パラメータを修正する",
            min_values=1,
            max_values=5,
            options=options,
        )

        self.cmd = cmd

    async def callback(
        self,
        interaction: discord.Interaction,
    ) -> None:
        current = (
            getattr(
                self.cmd,
                "_current_values",
                {},
            )
            or {}
        )

        selected = [
            value
            for value in self.values
            if (
                value != "ほしのきらめき"
                or current.get("boost_month")
            )
        ]

        await interaction.response.send_modal(
            ParamEditModal(
                self.cmd,
                selected,
                current,
            )
        )

        self.disabled = True

        await interaction.message.edit(
            view=self.view
        )


class NiaFinalGradeFromImgCommand(BaseCommand):
    """
    NIAシナリオの最終評価を、
    添付画像から読み取って計算するコマンド。
    """

    async def execute(
        self,
        params: NiaFinalGradeFromImgParams,
    ) -> None:
        self.log_command_start(
            COMMAND_NAME
        )

        command_started_at = time.perf_counter()

        self._static = {
            "character": params.character,
            "mode": params.mode,
            "audition": params.audition,
            "challenge_P_item": (
                params.challenge_P_item
            ),
            "is_boost_active": (
                params.is_boost_active
            ),
        }

        interaction: discord.Interaction = (
            self.interaction
        )

        await interaction.response.defer(
            thinking=True,
            ephemeral=False,
        )

        # 例外発生時の画像保存でも参照できるよう、
        # tryより前で初期化しておく。
        schedule_img_bytes: bytes | None = None
        party_img_bytes: bytes | None = None
        score_img_bytes: bytes | None = None

        try:
            # ========================================
            # Discord添付画像の検証・読み込み
            # ========================================
            image_load_started_at = (
                time.perf_counter()
            )

            schedule_img_bytes, party_img_bytes, score_img_bytes = (
                await asyncio.gather(
                    self.read_image_attachment(
                        params.schedule_img,
                        label="スケジュール画面",
                    ),
                    self.read_image_attachment(
                        params.party_img,
                        label="編成画面",
                    ),
                    self.read_image_attachment(
                        params.score_img,
                        label="スコア画面",
                    ),
                )
            )

            # NIAでは3画像とも必須。
            # 型上のNoneをここで除外する。
            if (
                schedule_img_bytes is None
                or party_img_bytes is None
                or score_img_bytes is None
            ):
                raise RuntimeError(
                    "必須画像の読み込み結果がありません。"
                )

            image_load_ms = (
                time.perf_counter()
                - image_load_started_at
            ) * 1000.0

            logger.debug(
                "Attachment loading completed: "
                "time=%.3f ms",
                image_load_ms,
            )

            # ========================================
            # OpenCV画像へのデコード
            # ========================================
            schedule_image = self._decode_image(
                schedule_img_bytes,
                label="スケジュール画面",
            )

            party_image = self._decode_image(
                party_img_bytes,
                label="編成画面",
            )

            score_image = self._decode_image(
                score_img_bytes,
                label="スコア画面",
            )

            # ========================================
            # 画像推論UseCaseを取得
            # ========================================
            inference_use_case = (
                self._get_inference_use_case(
                    interaction
                )
            )

            # ========================================
            # 画像推論・OCR検証・最終評価計算
            # ========================================
            use_case_result = (
                await inference_use_case.execute(
                    params=params,
                    schedule_image=schedule_image,
                    party_image=party_image,
                    score_image=score_image,
                )
            )

            # ========================================
            # 推論ログ・検出結果のDB保存
            # ========================================
            inference_status = (
                "SUCCESS"
                if use_case_result.success
                else "OCR_FAILED"
            )

            try:
                inference_log_recorder = (
                    self.get_inference_log_recorder(
                        interaction
                    )
                )

                inference_log_recorder.save(
                    request_id=self.request_id,
                    guild_id=interaction.guild_id,
                    channel_id=interaction.channel_id,
                    user_id=interaction.user.id,
                    command_name=COMMAND_NAME,
                    image_role="schedule",
                    image_path=None,
                    export_path=None,
                    inference_result=(
                        use_case_result.schedule_inference
                    ),
                    status=inference_status,
                )

                inference_log_recorder.save(
                    request_id=self.request_id,
                    guild_id=interaction.guild_id,
                    channel_id=interaction.channel_id,
                    user_id=interaction.user.id,
                    command_name=COMMAND_NAME,
                    image_role="party",
                    image_path=None,
                    export_path=None,
                    inference_result=(
                        use_case_result.party_inference
                    ),
                    status=inference_status,
                )

                inference_log_recorder.save(
                    request_id=self.request_id,
                    guild_id=interaction.guild_id,
                    channel_id=interaction.channel_id,
                    user_id=interaction.user.id,
                    command_name=COMMAND_NAME,
                    image_role="score",
                    image_path=None,
                    export_path=None,
                    inference_result=(
                        use_case_result.score_inference
                    ),
                    status=inference_status,
                )

            except Exception:
                logger.warning(
                    "Failed to save inference logs",
                    exc_info=True,
                )

            parameters_dict = (
                use_case_result.parameters
            )

            bonus_dict = (
                use_case_result.bonuses
            )

            score_dict = (
                use_case_result.scores
            )

            # ========================================
            # OCR不足時の修正UI
            # ========================================
            if not use_case_result.success:
                error_reason = (
                    use_case_result.error_reason
                    or "OCR required values missing"
                )

                logger.warning(
                    error_reason
                )

                self._set_current_values(
                    params=params,
                    parameters_dict=parameters_dict,
                    bonus_dict=bonus_dict,
                    score_dict=score_dict,
                )

                await self._send_ocr_error_view(
                    interaction=interaction,
                    params=params,
                    parameters_dict=parameters_dict,
                    bonus_dict=bonus_dict,
                    score_dict=score_dict,
                )

                await self.maybe_archive_inputs(
                    interaction=interaction,
                    save_agree=params.save_agree,
                    command=COMMAND_NAME,
                    images=self._build_archive_images(
                        params=params,
                        schedule_img_bytes=(
                            schedule_img_bytes
                        ),
                        party_img_bytes=(
                            party_img_bytes
                        ),
                        score_img_bytes=(
                            score_img_bytes
                        ),
                    ),
                    meta={
                        "status": "ocr_failed",
                        "error": error_reason,
                        "ocr_params": parameters_dict,
                        "ocr_bonus": bonus_dict,
                        "ocr_score": score_dict,
                        "schedule_inference_ms": (
                            use_case_result
                            .schedule_inference_ms
                        ),
                        "party_inference_ms": (
                            use_case_result
                            .party_inference_ms
                        ),
                        "score_inference_ms": (
                            use_case_result
                            .score_inference_ms
                        ),
                    },
                )

                self.log_command_end(
                    COMMAND_NAME
                )
                return

        except Exception as exc:
            logger.exception(
                "Image inference failed: %s",
                exc,
            )

            error_embed = discord.Embed(
                title="画像の読み取りに失敗しました",
                description=(
                    f"`{type(exc).__name__}: {exc}`"
                ),
                color=0xE74C3C,
            )

            await interaction.edit_original_response(
                content=None,
                embed=error_embed,
                view=None,
            )

            archive_images = (
                self._build_archive_images(
                    params=params,
                    schedule_img_bytes=(
                        schedule_img_bytes
                    ),
                    party_img_bytes=(
                        party_img_bytes
                    ),
                    score_img_bytes=(
                        score_img_bytes
                    ),
                )
            )

            if archive_images:
                await self.maybe_archive_inputs(
                    interaction=interaction,
                    save_agree=params.save_agree,
                    command=COMMAND_NAME,
                    images=archive_images,
                    meta={
                        "status": "exception",
                        "error": (
                            f"{type(exc).__name__}: {exc}"
                        ),
                    },
                )

            self.log_command_end(
                COMMAND_NAME
            )
            return

        # ============================================
        # UseCaseの最終評価計算結果を取得
        # ============================================
        result = (
            use_case_result.final_grade_result
        )

        if result is None:
            raise RuntimeError(
                "最終評価計算結果がありません。"
            )

        calculation_ms = (
            use_case_result.calculation_ms
        )

        logger.info(
            "最終スコア: %s",
            result.final_score,
        )

        logger.info(
            "評価ランク: %s",
            result.final_grade,
        )

        self._set_current_values(
            params=params,
            parameters_dict=parameters_dict,
            bonus_dict=bonus_dict,
            score_dict=score_dict,
        )

        # ============================================
        # Discord結果表示
        # ============================================
        logger.debug(
            "View/Container構築開始"
        )

        view = ui.LayoutView()
        container = build_final_grade_container(
            result
        )

        container.add_item(
            ui.Separator()
        )

        row = ui.ActionRow()
        row.add_item(
            ParamSelect(self)
        )

        container.add_item(row)
        view.add_item(container)

        logger.debug(
            "View/Container構築完了: "
            "メッセージ送信開始"
        )

        await interaction.edit_original_response(
            content=None,
            embed=None,
            view=view,
        )

        command_total_ms = (
            time.perf_counter()
            - command_started_at
        ) * 1000.0

        # ============================================
        # 同意済み入力画像の保存
        # ============================================
        await self.maybe_archive_inputs(
            interaction=interaction,
            save_agree=params.save_agree,
            command=COMMAND_NAME,
            images=self._build_archive_images(
                params=params,
                schedule_img_bytes=(
                    schedule_img_bytes
                ),
                party_img_bytes=(
                    party_img_bytes
                ),
                score_img_bytes=(
                    score_img_bytes
                ),
            ),
            meta={
                "status": "success",
                "mode": params.mode,
                "audition": params.audition,
                "character": params.character,
                "runtime_ms": command_total_ms,
                "calculation_ms": calculation_ms,
                "ocr_params": parameters_dict,
                "ocr_bonus": bonus_dict,
                "ocr_score": score_dict,
                "schedule_inference_ms": (
                    use_case_result.schedule_inference_ms
                ),
                "party_inference_ms": (
                    use_case_result.party_inference_ms
                ),
                "score_inference_ms": (
                    use_case_result.score_inference_ms
                ),
            },
        )

        logger.debug(
            "calculate_score finished in %.3f ms",
            calculation_ms,
        )

        logger.debug(
            "%s command finished in %.3f ms",
            COMMAND_NAME,
            command_total_ms,
        )

        self.log_command_end(
            COMMAND_NAME
        )

    @staticmethod
    def _decode_image(
        image_bytes: bytes,
        *,
        label: str,
    ) -> np.ndarray:
        """
        画像バイト列をOpenCVのBGR画像へ変換する。

        Raises:
            ValueError:
                空データ、または画像として
                デコードできない場合。
        """
        if not image_bytes:
            raise ValueError(
                f"{label}の画像データが空です。"
            )

        encoded = np.frombuffer(
            image_bytes,
            dtype=np.uint8,
        )

        image = cv2.imdecode(
            encoded,
            cv2.IMREAD_COLOR,
        )

        if image is None:
            raise ValueError(
                f"{label}を画像として"
                "読み込めませんでした。"
            )

        return image

    @staticmethod
    def _build_archive_images(
        *,
        params: NiaFinalGradeFromImgParams,
        schedule_img_bytes: bytes | None,
        party_img_bytes: bytes | None,
        score_img_bytes: bytes | None,
    ) -> dict[str, tuple[str, bytes]]:
        """
        読み込み済み画像だけを保存用辞書へまとめる。
        """
        images: dict[
            str,
            tuple[str, bytes],
        ] = {}

        if schedule_img_bytes is not None:
            images["schedule"] = (
                params.schedule_img.filename
                or "schedule.png",
                schedule_img_bytes,
            )

        if party_img_bytes is not None:
            images["party"] = (
                params.party_img.filename
                or "party.png",
                party_img_bytes,
            )

        if score_img_bytes is not None:
            images["score"] = (
                params.score_img.filename
                or "score.png",
                score_img_bytes,
            )

        return images

    def _set_current_values(
        self,
        *,
        params: NiaFinalGradeFromImgParams,
        parameters_dict: dict,
        bonus_dict: dict,
        score_dict: dict,
    ) -> None:
        """
        Modalによる再計算で使用する現在値を保持する。
        """
        self._current_values = {
            "vo_status": (
                parameters_dict.get("vo")
                or 0
            ),
            "da_status": (
                parameters_dict.get("da")
                or 0
            ),
            "vi_status": (
                parameters_dict.get("vi")
                or 0
            ),
            "vo_bonus": (
                bonus_dict.get("vo")
                or 0
            ),
            "da_bonus": (
                bonus_dict.get("da")
                or 0
            ),
            "vi_bonus": (
                bonus_dict.get("vi")
                or 0
            ),
            "vo_score": (
                score_dict.get("vo")
                or 0
            ),
            "da_score": (
                score_dict.get("da")
                or 0
            ),
            "vi_score": (
                score_dict.get("vi")
                or 0
            ),
            "now_fans": (
                parameters_dict.get("fans")
                or 0
            ),
            "boost_month": bool(
                params.is_boost_active
            ),
            "kirameki": (
                bonus_dict.get("kirameki")
                or 0
            )
            if params.is_boost_active
            else 0,
        }

    async def _send_ocr_error_view(
        self,
        *,
        interaction: discord.Interaction,
        params: NiaFinalGradeFromImgParams,
        parameters_dict: dict,
        bonus_dict: dict,
        score_dict: dict,
    ) -> None:
        """
        OCR結果に不足がある場合の修正UIを表示する。
        """
        logger.info(
            "ERROR View/Container構築開始"
        )

        view = ui.LayoutView()

        error_container = build_error_container(
            params=parameters_dict,
            bonus=bonus_dict,
            score=score_dict,
            is_boost=params.is_boost_active,
        )

        error_container.add_item(
            ui.Separator()
        )

        row = ui.ActionRow()
        row.add_item(
            ParamSelect(self)
        )

        error_container.add_item(row)
        view.add_item(error_container)

        logger.info(
            "ERROR View/Container構築完了: "
            "メッセージ送信開始"
        )

        await interaction.edit_original_response(
            content=None,
            embed=None,
            view=view,
        )

    def _get_inference_use_case(
        self,
        interaction: discord.Interaction,
    ) -> InferenceUseCase:
        """
        Botが保持するInferenceServiceから
        画像推論UseCaseを生成する。
        """
        inference_service = cast(
            InferenceService | None,
            getattr(
                interaction.client,
                "inference_service",
                None,
            ),
        )

        if inference_service is None:
            raise RuntimeError(
                "InferenceServiceが"
                "初期化されていません。"
            )

        return InferenceUseCase(
            inference_service
        )

    # --- 内部: 再計算してメッセージを書き換える ---
    async def _recompute_and_edit(
        self,
        interaction: discord.Interaction,
        merged: dict,
    ) -> None:
        """
        OCRは再実行せず、ユーザーが修正した値で再計算する。
        """
        static = getattr(
            self,
            "_static",
            None,
        )

        if not static:
            await interaction.followup.send(
                embed=Embed(
                    title="再計算エラー",
                    description=(
                        "内部状態が不足しています。"
                        "もう一度コマンドを"
                        "実行してください。"
                    ),
                ),
                ephemeral=True,
            )
            return

        async with self.scoped_ctx(
            interaction
        ):
            self.log_recompute_start(
                COMMAND_NAME
            )

            inference_use_case = (
                self._get_inference_use_case(
                    interaction
                )
            )

            result = inference_use_case.calculate(
                character=static["character"],
                mode=static["mode"],
                audition=static["audition"],
                challenge_p_item=(
                    static[
                        "challenge_P_item"
                    ]
                ),
                is_boost_active=(
                    static[
                        "is_boost_active"
                    ]
                ),
                values=merged,
            )

            logger.info(
                "View/Container構築開始"
            )

            layout = ui.LayoutView()

            container = (
                build_final_grade_container(
                    result
                )
            )

            container.add_item(
                ui.Separator()
            )

            row = ui.ActionRow()
            row.add_item(
                ParamSelect(self)
            )

            container.add_item(row)
            layout.add_item(container)

            logger.info(
                "View/Container構築完了: "
                "メッセージ送信開始"
            )

            await interaction.followup.send(
                view=layout
            )

            self.log_recompute_end(
                COMMAND_NAME
            )
