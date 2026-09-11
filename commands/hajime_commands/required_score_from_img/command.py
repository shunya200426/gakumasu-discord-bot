from __future__ import annotations

import asyncio
import time

import cv2
import discord
import numpy as np
from discord import Embed, ui

from commands.base_command import BaseCommand
from commands.hajime_commands.final_grade.container_builder import (
    build_final_grade_container,
)
from commands.hajime_commands.required_score.calculator import (
    BOOST_MODE_NOT_SUPPORTED_MESSAGE,
)
from commands.hajime_commands.required_score.container_builder import (
    build_required_score_container,
)
from inference.result import InferenceResult
from models.hajime.final_grade.params import HajimeFinalGradeParams
from models.hajime.final_grade.result import HajimeFinalGradeResult
from models.hajime.required_score_from_img.params import (
    HajimeRequiredScoreFromImgParams,
)
from scenarios import HajimeScenario
from services.image_consent_service import ImageConsentResult
from utils.logger import get_logger

from .container_builder import build_error_container
from .inference_use_case import SUPPORTED_MODE, InferenceUseCase
from .inference_use_case_result import InferenceUseCaseResult

COMMAND_NAME = "hajime_required_score_from_img"
UNSUPPORTED_MODE_MESSAGE = "初の画像必要スコア計算はLegendのみ対応しています。"
logger = get_logger()

_LABEL2KEY = {
    "Voパラメータ": "vo_status",
    "Daパラメータ": "da_status",
    "Viパラメータ": "vi_status",
    "中間試験スコア": "mid_exam_score",
}


class AddExamScoreModal(ui.Modal):
    def __init__(self, cmd: HajimeRequiredScoreFromImgCommand):
        super().__init__(title="最終試験のスコアを入力")
        self.cmd = cmd
        input_box = ui.TextInput(
            label="最終試験のスコア",
            required=False,
            placeholder="数値を入力",
        )
        self.add_item(input_box)
        self.input = input_box

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer()
        raw = (self.input.value or "").strip()
        try:
            new_exam_score = int(raw)
        except ValueError:
            await interaction.followup.send(
                "半角数字で入力してください。",
                ephemeral=True,
            )
            return
        await self.cmd._calc_final_grade(interaction, new_exam_score)


class ParamEditModal(ui.Modal):
    def __init__(
        self,
        cmd: HajimeRequiredScoreFromImgCommand,
        selected_params: list[str],
        current: dict,
    ):
        super().__init__(title="パラメータを編集")
        self.cmd = cmd
        self.current = current
        self.inputs = {}
        for param in selected_params:
            input_box = ui.TextInput(
                label=param,
                required=False,
                default=str(current.get(_LABEL2KEY.get(param, ""), "")),
                placeholder="数値を入力",
            )
            self.add_item(input_box)
            self.inputs[param] = input_box

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer()
        try:
            updates = {}
            for label, text_input in self.inputs.items():
                if text_input.value not in ("", None):
                    key = _LABEL2KEY.get(label)
                    if key:
                        updates[key] = int(text_input.value.strip())

            merged = {**(self.current or {}), **updates}
            for key in _LABEL2KEY.values():
                if merged.get(key) is None or merged[key] < 0:
                    raise ValueError(f"{key} は0以上の整数にしてください。")

            self.cmd._current_values = merged
            await self.cmd._recompute_and_edit(interaction, merged)
        except (TypeError, ValueError) as exc:
            await interaction.followup.send(
                embed=Embed(title="入力エラー", description=str(exc)),
                ephemeral=True,
            )
        except Exception as exc:
            logger.exception("ParamEditModal.on_submit failed")
            await interaction.followup.send(
                embed=Embed(
                    title="入力エラー",
                    description=f"{type(exc).__name__}: {exc}",
                ),
                ephemeral=True,
            )


class ParamSelect(ui.Select):
    def __init__(self, cmd: HajimeRequiredScoreFromImgCommand):
        options = [
            discord.SelectOption(label="Voパラメータ"),
            discord.SelectOption(label="Daパラメータ"),
            discord.SelectOption(label="Viパラメータ"),
            discord.SelectOption(label="中間試験スコア"),
        ]
        super().__init__(
            placeholder="パラメータを修正する",
            min_values=1,
            max_values=len(options),
            options=options,
        )
        self.cmd = cmd

    async def callback(self, interaction: discord.Interaction):
        current = getattr(self.cmd, "_current_values", {}) or {}
        await interaction.response.send_modal(
            ParamEditModal(self.cmd, list(self.values), current)
        )
        self.disabled = True
        await interaction.message.edit(view=self.view)


class AddExamScoreButton(ui.Button):
    def __init__(self, cmd: HajimeRequiredScoreFromImgCommand):
        super().__init__(
            style=discord.ButtonStyle.primary,
            label="最終試験のスコアを入力する",
        )
        self.cmd = cmd

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.send_modal(AddExamScoreModal(self.cmd))
        self.disabled = True
        await interaction.message.edit(view=self.view)


class HajimeRequiredScoreFromImgCommand(BaseCommand):
    """初の必要最終試験スコアを画像から計算するコマンド。"""

    async def execute(self, params: HajimeRequiredScoreFromImgParams):
        self.log_command_start(COMMAND_NAME)
        started_at = time.perf_counter()

        if params.is_boost_active:
            await self.interaction.response.send_message(
                BOOST_MODE_NOT_SUPPORTED_MESSAGE,
                ephemeral=True,
            )
            self.log_command_end(COMMAND_NAME)
            return
        if params.mode != SUPPORTED_MODE:
            await self.interaction.response.send_message(
                UNSUPPORTED_MODE_MESSAGE,
                ephemeral=True,
            )
            self.log_command_end(COMMAND_NAME)
            return

        self._static = {
            "mode": params.mode,
            "vo_ability": params.vo_ability,
            "da_ability": params.da_ability,
            "vi_ability": params.vi_ability,
            "character": params.character,
            "target_grade": params.target_grade,
            "target_score": params.target_score,
            "is_boost_active": False,
            "kirameki": 0,
        }

        interaction: discord.Interaction = self.interaction
        await interaction.response.defer(thinking=True, ephemeral=False)

        try:
            consent_result = self.resolve_image_consent(
                interaction=interaction,
                requested=params.save_agree,
            )
        except Exception:
            logger.exception("Failed to resolve image save consent")
            await interaction.edit_original_response(
                content=(
                    "画像保存設定を確認できませんでした。"
                    "時間をおいて、もう一度お試しください。"
                ),
                embed=None,
                view=None,
            )
            self.log_command_end(COMMAND_NAME)
            return

        schedule_bytes: bytes | None = None
        party_bytes: bytes | None = None
        mid_exam_bytes: bytes | None = None
        saved_input_paths: dict[str, str] = {}

        try:
            schedule_bytes, party_bytes, mid_exam_bytes = await asyncio.gather(
                self.read_image_attachment(
                    params.schedule_img,
                    label="スケジュール画面",
                ),
                self.read_image_attachment(
                    params.party_img,
                    label="編成画面",
                ),
                self.read_image_attachment(
                    params.mid_exam_score_img,
                    label="中間試験スコア画面",
                    required=False,
                ),
            )
            if schedule_bytes is None or party_bytes is None:
                raise RuntimeError("必須画像の読み込み結果がありません。")

            archive_images = self._build_archive_images(
                params=params,
                schedule_bytes=schedule_bytes,
                party_bytes=party_bytes,
                mid_exam_bytes=mid_exam_bytes,
            )
            saved_input_paths = await self._save_input_images(
                interaction=interaction,
                consent_result=consent_result,
                images=archive_images,
                metadata={
                    "mode": params.mode,
                    "character": params.character,
                },
            )

            schedule_image = self._decode_image(
                schedule_bytes,
                label="スケジュール画面",
            )
            party_image = self._decode_image(party_bytes, label="編成画面")
            mid_exam_image = (
                self._decode_image(mid_exam_bytes, label="中間試験スコア画面")
                if mid_exam_bytes is not None
                else None
            )

            use_case = self._get_inference_use_case(interaction)
            use_case_result = await use_case.execute(
                params=params,
                schedule_image=schedule_image,
                party_image=party_image,
                mid_exam_image=mid_exam_image,
            )
            inference_items = self._inference_items(use_case_result)
            saved_export_paths = await self._export_inference_results(
                interaction=interaction,
                inference_items=inference_items,
            )
            self._record_inference_results(
                interaction=interaction,
                inference_items=inference_items,
                saved_input_paths=saved_input_paths,
                saved_export_paths=saved_export_paths,
                status="SUCCESS" if use_case_result.success else "OCR_FAILED",
            )

            self._set_current_values(use_case_result)
            if not use_case_result.success:
                await self._send_ocr_error_view(
                    interaction=interaction,
                    use_case_result=use_case_result,
                )
                await self.send_image_consent_notification(consent_result)
                self.log_command_end(COMMAND_NAME)
                return

            result = use_case_result.required_score_result
            if result is None:
                raise RuntimeError("必要スコア計算結果がありません。")

            layout = ui.LayoutView()
            container = build_required_score_container(
                result,
                override_pairs=use_case_result.pairs,
            )
            container.add_item(ui.Separator())
            parameter_row = ui.ActionRow()
            parameter_row.add_item(ParamSelect(self))
            container.add_item(parameter_row)
            exam_row = ui.ActionRow()
            exam_row.add_item(AddExamScoreButton(self))
            container.add_item(exam_row)
            layout.add_item(container)
            await interaction.edit_original_response(
                content=None,
                embed=None,
                view=layout,
            )
            await self.send_image_consent_notification(consent_result)
            self.message = await interaction.original_response()
        except Exception as exc:
            logger.warning("%s: %s", type(exc).__name__, exc, exc_info=True)
            error = discord.Embed(
                title="画像の読み取りに失敗しました",
                description=f"`{type(exc).__name__}: {exc}`",
                color=0xE74C3C,
            )
            await interaction.edit_original_response(
                content=None,
                embed=error,
                view=None,
            )
            await self.send_image_consent_notification(consent_result)
            self.log_command_end(COMMAND_NAME)
            return

        logger.debug(
            "%s finished in %.2f ms",
            COMMAND_NAME,
            (time.perf_counter() - started_at) * 1000.0,
        )
        self.log_command_end(COMMAND_NAME)

    @staticmethod
    def _decode_image(image_bytes: bytes, *, label: str) -> np.ndarray:
        if not image_bytes:
            raise ValueError(f"{label}の画像データが空です。")
        encoded = np.frombuffer(image_bytes, dtype=np.uint8)
        image = cv2.imdecode(encoded, cv2.IMREAD_COLOR)
        if image is None:
            raise ValueError(f"{label}を画像として読み込めませんでした。")
        return image

    @staticmethod
    def _build_archive_images(
        *,
        params: HajimeRequiredScoreFromImgParams,
        schedule_bytes: bytes,
        party_bytes: bytes,
        mid_exam_bytes: bytes | None,
    ) -> dict[str, tuple[str, bytes]]:
        images = {
            "schedule": (
                params.schedule_img.filename or "schedule.png",
                schedule_bytes,
            ),
            "party": (
                params.party_img.filename or "party.png",
                party_bytes,
            ),
        }
        if mid_exam_bytes is not None and params.mid_exam_score_img is not None:
            images["score"] = (
                params.mid_exam_score_img.filename or "score.png",
                mid_exam_bytes,
            )
        return images

    @staticmethod
    def _inference_items(
        result: InferenceUseCaseResult,
    ) -> list[tuple[str, InferenceResult]]:
        items = [
            ("schedule", result.schedule_inference),
            ("party", result.party_inference),
        ]
        if result.mid_exam_inference is not None:
            items.append(("score", result.mid_exam_inference))
        return items

    async def _save_input_images(
        self,
        *,
        interaction: discord.Interaction,
        consent_result: ImageConsentResult,
        images: dict[str, tuple[str, bytes]],
        metadata: dict,
    ) -> dict[str, str]:
        if not consent_result.current:
            return {}
        try:
            return await self.get_image_storage_service(
                interaction
            ).save_input_images(
                guild_id=interaction.guild_id,
                user_id=interaction.user.id,
                command_name=COMMAND_NAME,
                request_id=self.request_id,
                images=images,
                metadata=metadata,
            )
        except Exception:
            logger.warning("Failed to save input images", exc_info=True)
            return {}

    async def _export_inference_results(
        self,
        *,
        interaction: discord.Interaction,
        inference_items: list[tuple[str, InferenceResult]],
    ) -> dict[str, str]:
        try:
            service = self.get_inference_export_service(interaction)
            paths = await asyncio.gather(
                *(
                    service.save(
                        guild_id=interaction.guild_id,
                        user_id=interaction.user.id,
                        request_id=self.request_id,
                        image_role=role,
                        inference_result=inference_result,
                    )
                    for role, inference_result in inference_items
                )
            )
            return {
                role: path
                for (role, _), path in zip(inference_items, paths, strict=True)
            }
        except Exception:
            logger.warning("Failed to export inference results", exc_info=True)
            return {}

    def _record_inference_results(
        self,
        *,
        interaction: discord.Interaction,
        inference_items: list[tuple[str, InferenceResult]],
        saved_input_paths: dict[str, str],
        saved_export_paths: dict[str, str],
        status: str,
    ) -> None:
        try:
            recorder = self.get_inference_log_recorder(interaction)
            for role, inference_result in inference_items:
                recorder.save(
                    request_id=self.request_id,
                    guild_id=interaction.guild_id,
                    channel_id=interaction.channel_id,
                    user_id=interaction.user.id,
                    command_name=COMMAND_NAME,
                    image_role=role,
                    image_path=saved_input_paths.get(role),
                    export_path=saved_export_paths.get(role),
                    inference_result=inference_result,
                    status=status,
                )
        except Exception:
            logger.warning("Failed to save inference logs", exc_info=True)

    def _get_inference_use_case(
        self,
        interaction: discord.Interaction,
    ) -> InferenceUseCase:
        inference_service = getattr(interaction.client, "inference_service", None)
        if inference_service is None:
            raise RuntimeError("InferenceServiceが初期化されていません。")
        return InferenceUseCase(inference_service)

    def _set_current_values(self, result: InferenceUseCaseResult) -> None:
        self._current_values = {
            "vo_status": result.parameters.get("vo") or 0,
            "da_status": result.parameters.get("da") or 0,
            "vi_status": result.parameters.get("vi") or 0,
            "mid_exam_score": result.mid_exam_score or 0,
        }
        self._static.update(self._current_values)

    async def _send_ocr_error_view(
        self,
        *,
        interaction: discord.Interaction,
        use_case_result: InferenceUseCaseResult,
    ) -> None:
        layout = ui.LayoutView()
        container = build_error_container(
            params=use_case_result.parameters,
            score_dict=use_case_result.scores,
        )
        container.add_item(ui.Separator())
        row = ui.ActionRow()
        row.add_item(ParamSelect(self))
        container.add_item(row)
        layout.add_item(container)
        await interaction.edit_original_response(
            content=use_case_result.error_reason,
            embed=None,
            view=layout,
        )

    async def _recompute_and_edit(
        self,
        interaction: discord.Interaction,
        merged: dict,
    ) -> None:
        static = getattr(self, "_static", None)
        if not static:
            await interaction.followup.send(
                embed=Embed(
                    title="再計算エラー",
                    description="内部状態が不足しています。もう一度コマンドを実行してください。",
                ),
                ephemeral=True,
            )
            return

        async with self.scoped_ctx(interaction):
            self.log_recompute_start(COMMAND_NAME)
            use_case = self._get_inference_use_case(interaction)
            result, pairs = use_case.calculate(
                mode=static["mode"],
                character=static["character"],
                target_grade=static["target_grade"],
                target_score=static["target_score"],
                vo_ability=static["vo_ability"],
                da_ability=static["da_ability"],
                vi_ability=static["vi_ability"],
                vo_status=merged.get("vo_status"),
                da_status=merged.get("da_status"),
                vi_status=merged.get("vi_status"),
                mid_exam_score=merged.get("mid_exam_score"),
            )
            self._current_values = merged
            self._static.update(merged)

            layout = ui.LayoutView()
            container = build_required_score_container(result, override_pairs=pairs)
            container.add_item(ui.Separator())
            parameter_row = ui.ActionRow()
            parameter_row.add_item(ParamSelect(self))
            container.add_item(parameter_row)
            exam_row = ui.ActionRow()
            exam_row.add_item(AddExamScoreButton(self))
            container.add_item(exam_row)
            layout.add_item(container)
            await interaction.followup.send(view=layout)
            self.log_recompute_end(COMMAND_NAME)

    async def _calc_final_grade(
        self,
        interaction: discord.Interaction,
        final_exam_score: int,
    ) -> None:
        async with self.scoped_ctx(interaction):
            self.log_recompute_start(COMMAND_NAME)
            params = HajimeFinalGradeParams(
                mode=self._static["mode"],
                vo_status=self._static["vo_status"],
                da_status=self._static["da_status"],
                vi_status=self._static["vi_status"],
                vo_ability=self._static["vo_ability"],
                da_ability=self._static["da_ability"],
                vi_ability=self._static["vi_ability"],
                mid_exam_score=self._static["mid_exam_score"],
                final_exam_score=final_exam_score,
                final_exam_rank="first",
                character=self._static["character"],
                is_boost_active=False,
                kirameki=0,
            )
            scenario = HajimeScenario(mode=params.mode)
            result: HajimeFinalGradeResult = scenario.calculate_score(params)

            layout = ui.LayoutView()
            container = build_final_grade_container(result)
            container.add_item(ui.Separator())
            row = ui.ActionRow()
            row.add_item(AddExamScoreButton(self))
            container.add_item(row)
            layout.add_item(container)
            await interaction.followup.send(view=layout)
            self.log_recompute_end(COMMAND_NAME)
