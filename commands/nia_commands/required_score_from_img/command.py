# commands/nia_commands/required_score_from_img/command.py
from __future__ import annotations

import time
from typing import cast

import cv2
import discord
import numpy as np
from discord import Embed, ui

from commands.nia_commands.required_score.command import NiaRequiredScoreCommand
from commands.nia_commands.required_score.container_builder import (
    build_required_score_container,
)
from models.nia.required_score_from_img.params import NiaRequiredScoreFromImgParams
from services.inference_service import InferenceService
from utils.logger import get_logger

from .container_builder import build_error_container
from .inference_use_case import InferenceUseCase

COMMAND_NAME = "nia_required_score_from_img"
logger = get_logger()

# --- ラベル <-> 内部キー ---
_LABEL2KEY = {
    "Voパラメータ": "vo_status",
    "Daパラメータ": "da_status",
    "Viパラメータ": "vi_status",
    "Voパラメータボーナス": "vo_bonus",
    "Daパラメータボーナス": "da_bonus",
    "Viパラメータボーナス": "vi_bonus",
    "ファン数": "now_fans",
    "ほしのきらめき": "kirameki",
}

# --- Modal 定義 ---
class ParamEditModal(ui.Modal):
    def __init__(self, cmd: "NiaRequiredScoreFromImgCommand", selected_params: list[str], current: dict):
        super().__init__(title="パラメータを編集")
        self.cmd = cmd
        self.current = current
        self.inputs = {}
        for param in selected_params:
            input_box = ui.TextInput(
                label=param,
                required=False,
                default=str(current.get(_LABEL2KEY.get(param, ""), "")),
                placeholder="数値を入力"
            )
            self.add_item(input_box)
            self.inputs[param] = input_box

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer()

        # 1) 入力を current にマージ（空欄は据え置き）
        try:
            updates = {}
            for label, ti in self.inputs.items():
                if ti.value not in ("", None):
                    key = _LABEL2KEY.get(label)
                    if key:
                        updates[key] = ti.value
            merged = {**(self.current or {}), **updates}

            # 2) 型/範囲の軽い検証＆キャスト（int前提）
            int_keys = ("vo_status", "da_status", "vi_status", "now_fans", "kirameki")
            float_keys = ("vo_bonus", "da_bonus", "vi_bonus")

            for k in int_keys:
                if k in merged:
                    try:
                        merged[k] = int(str(merged[k]).strip() or 0)
                        if merged[k] < 0:
                            raise ValueError(f"{k} は0以上にしてください")
                    except Exception as e:
                        await interaction.response.send_message(
                            embed=Embed(title="入力エラー", description=f"{k}: {e}"),
                            ephemeral=True
                        )
                        return

            for k in float_keys:
                if k in merged:
                    try:
                        merged[k] = float(str(merged[k]).strip() or 0.0)
                        if merged[k] < 0:
                            raise ValueError(f"{k} は0.0以上にしてください")
                    except Exception as e:
                        await interaction.response.send_message(
                            embed=Embed(title="入力エラー", description=f"{k}: {e}"),
                            ephemeral=True
                        )
                        return
                    
            merged["boost_month"] = bool(merged.get("boost_month", self.cmd._static.get("is_boost_active", False)))

            # 3) 現在値を更新し、再計算して新規メッセージを送信
            self.cmd._current_values = merged
            await self.cmd._recompute_and_edit(interaction, merged)

        except Exception as e:
            logger.exception("ParamEditModal.on_submit failed")
            await interaction.followup.send(
                embed=discord.Embed(title="入力エラー", description=f"{type(e).__name__}: {e}"),
                ephemeral=True
            )


# --- プルダウン定義 ---
class ParamSelect(ui.Select):
    """
    パラメータの編集セレクト
    """
    def __init__(self, cmd: "NiaRequiredScoreFromImgCommand"):
        # 強化月間フラグ
        is_boost = bool(getattr(cmd, "_static", {}).get("is_boost_active", False))

        # プルダウンメニューの構築
        options = [
            discord.SelectOption(label="Voパラメータ"),
            discord.SelectOption(label="Daパラメータ"),
            discord.SelectOption(label="Viパラメータ"),
            discord.SelectOption(label="Voパラメータボーナス"),
            discord.SelectOption(label="Daパラメータボーナス"),
            discord.SelectOption(label="Viパラメータボーナス"),
            discord.SelectOption(label="ファン数"),
            discord.SelectOption(label="ほしのきらめき"),
        ]

        # 強化月間適用時以外はきらめきを削除
        if not is_boost:
            options = [o for o in options if o.label != "ほしのきらめき"]

        super().__init__(
            placeholder="パラメータを修正する",
            min_values=1,
            max_values=5,
            options=options
        )
        self.cmd = cmd

    async def callback(self, interaction: discord.Interaction):
        # 強化月間でない場合は「きらめき」を除外
        current = getattr(self.cmd, "_current_values", {}) or {}
        selected = [o for o in self.values if (o != "ほしのきらめき" or current.get("boost_month"))]
        await interaction.response.send_modal(ParamEditModal(self.cmd, selected, current))

        # プルダウンを無効化
        self.disabled = True
        await interaction.message.edit(view=self.view)

class AuditionSelect(ui.Select):
    """
    比較するオーディションのセレクト
    """
    def __init__(self, cmd: "NiaRequiredScoreFromImgCommand"):
        # 現在のオーディションを取得
        # audition = getattr(cmd, "_static", {}).get("audition")

        # プルダウンメニューの構築
        options = [
            discord.SelectOption(label="FINALE", value="finale"),
            discord.SelectOption(label="QUARTET", value="quartet"),
            discord.SelectOption(label="IDOLBigup!", value="idol_bigup!"),
        ]

        super().__init__(
            placeholder="他のオーディションと比較する",
            options=options
        )
        self.cmd = cmd

    async def callback(self, interaction: discord.Interaction):
        """
        ここで選択したオーディションで再計算をする
        """
        await interaction.response.defer()
        
        # 選択したオーディションで再計算して新規メッセージを送信
        current = getattr(self.cmd, "_current_values", {}) or {}
        if self.values:
            selected_audition = self.values[0]
            current = {**current, "audition": selected_audition}

        self.cmd._current_values = current
        await self.cmd._recompute_and_edit(interaction, current)

        # プルダウンを無効化
        self.disabled = True
        await interaction.message.edit(view=self.view)

class NiaRequiredScoreFromImgCommand(NiaRequiredScoreCommand):
    """
    NIAシナリオの逆計算コマンド
    """
    async def execute(self, params: NiaRequiredScoreFromImgParams):
        self.log_command_start(COMMAND_NAME)
        t0 = time.perf_counter()

        # 再計算で使う固定情報を保存
        self._static = {
            "character": params.character,
            "mode": params.mode,
            "target_grade": params.target_grade,
            "target_score": params.target_score,
            "challenge_P_item": params.challenge_P_item,
            "is_boost_active": params.is_boost_active,
        }

        # 先に保留応答
        interaction: discord.Interaction = self.interaction
        await interaction.response.defer(thinking=True, ephemeral=False)

        # 入力画像の確認
        if params.schedule_img.content_type and not params.schedule_img.content_type.startswith("image/"):
            logger.warning("input img error")
            return await interaction.edit_original_response(
                content="画像ファイルを添付してください"
            )
        
        if params.party_img.content_type and not params.party_img.content_type.startswith("image/"):
            logger.warning("input img error")
            return await interaction.edit_original_response(
                content="画像ファイルを添付してください"
            )

        schedule_img_bytes: bytes | None = None
        party_img_bytes: bytes | None = None

        try:
            # 画像の読み込み
            t1 = time.perf_counter()
            schedule_img_bytes = await params.schedule_img.read()
            party_img_bytes = await params.party_img.read()
            dt = (time.perf_counter() - t1) * 1000
            logger.debug("loading img time %.1f ms", dt)

            schedule_image = self._decode_image(
                schedule_img_bytes,
                label="スケジュール画面",
            )

            party_image = self._decode_image(
                party_img_bytes,
                label="編成画面",
            )

            inference_use_case = (
                self._get_inference_use_case(
                    interaction
                )
            )

            use_case_result = (
                await inference_use_case.execute(
                    params=params,
                    schedule_image=schedule_image,
                    party_image=party_image,
                )
            )

            parameters_dict = (
                use_case_result.parameters
            )

            bonus_dict = (
                use_case_result.bonuses
            )

            if not use_case_result.success:
                # 現在値を保持（モーダル初期値用）
                self._set_current_values(
                    params=params,
                    parameters_dict=parameters_dict,
                    bonus_dict=bonus_dict,
                )

                # View / Container構築 -> メッセージ送信
                await self._send_ocr_error_view(
                    interaction=interaction,
                    params=params,
                    parameters_dict=parameters_dict,
                    bonus_dict=bonus_dict,
                )

                # ▼ 失敗時も保存する（同意時）
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
                    ),
                    meta={
                        "error": "param_or_bonus_read_failed",
                        "ocr_params": parameters_dict,
                        "ocr_bonus": bonus_dict,
                    },
                )
                self.log_command_end(COMMAND_NAME)
                return
            

        except Exception as e:
            logger.warning("%s: %s", type(e).__name__, e)
            logger.info("ERROR Embed構築開始")
            err = discord.Embed(
                title="画像の読み取りに失敗しました",
                description=f"`{type(e).__name__}: {e}`",
                color=0xE74C3C
            )
            logger.info("ERROR Embed構築完了: メッセージ送信を開始")
            await interaction.edit_original_response(content=None, embed=err)

            # ▼ 失敗時も保存する（同意時）: 取得済みバイトがなければ再読込を試みる
            try:
                images = {}
                if params.schedule_img:
                    images["schedule"] = (
                        params.schedule_img.filename or "schedule.png",
                        locals().get("schedule_img_bytes") or await params.schedule_img.read()
                    )
                if params.party_img:
                    images["party"] = (
                        params.party_img.filename or "party.png",
                        locals().get("party_img_bytes") or await params.party_img.read()
                    )
            except Exception:
                images = {}

            await self.maybe_archive_inputs(
                interaction=interaction,
                save_agree=params.save_agree,
                command=COMMAND_NAME,
                images=images,
                meta={
                    "error": "exception",
                    "exception": f"{type(e).__name__}: {e}",
                },
            )
            self.log_command_end(COMMAND_NAME)
            return

        # 現在値を保持（モーダル初期値用）
        self._set_current_values(
            params=params,
            parameters_dict=parameters_dict,
            bonus_dict=bonus_dict,
        )

        result = (
            use_case_result.required_score_result
        )

        if result is None:
            raise RuntimeError(
                "必要スコア計算結果がありません。"
            )

        pairs = (
            use_case_result.pairs
        )

        # View / Container構築
        logger.debug("View/Container構築開始")
        layout = ui.LayoutView()
        container = build_required_score_container(result, override_pairs=pairs)
        container.add_item(ui.Separator())

        row = ui.ActionRow()
        row.add_item(ParamSelect(self))
        container.add_item(row)

        audition_select = ui.ActionRow()
        audition_select.add_item(AuditionSelect(self))
        container.add_item(audition_select)

        layout.add_item(container)
        logger.debug("View/Container構築完了: メッセージ送信を開始")
        await interaction.followup.send(view=layout)
        self.message = await interaction.original_response()

        # 送信後：同意時のみ保存（共通化）
        await self.maybe_archive_inputs(
            interaction=interaction,
            save_agree=params.save_agree,
            command="nia_required_score_from_img",
            images=self._build_archive_images(
                params=params,
                schedule_img_bytes=(
                    schedule_img_bytes
                ),
                party_img_bytes=(
                    party_img_bytes
                ),
            ),
            meta={
                "mode": params.mode,
                "audition": params.audition,
                "character": params.character,
                "runtime_ms": (time.perf_counter() - t0) * 1000.0,
                "ocr_params": parameters_dict,
                "ocr_bonus":  bonus_dict,
            },
        )
                
        dt = use_case_result.calculation_ms
        logger.debug("required score finished in %.2f ms", dt)

        dt = (time.perf_counter() - t0) * 1000
        logger.debug("%s finished in %.2f ms",COMMAND_NAME, dt)
        self.log_command_end(COMMAND_NAME)

    @staticmethod
    def _decode_image(
        image_bytes: bytes,
        *,
        label: str,
    ) -> np.ndarray:
        """
        画像バイト列をOpenCVのBGR画像へ変換する。
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
        params: NiaRequiredScoreFromImgParams,
        schedule_img_bytes: bytes | None,
        party_img_bytes: bytes | None,
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

        return images

    def _set_current_values(
        self,
        *,
        params: NiaRequiredScoreFromImgParams,
        parameters_dict: dict,
        bonus_dict: dict,
    ) -> None:
        """
        Modalによる再計算で使用する現在値を保持する。
        """
        self._current_values = {
            "audition": params.audition,
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
        params: NiaRequiredScoreFromImgParams,
        parameters_dict: dict,
        bonus_dict: dict,
    ) -> None:
        """
        OCR結果に不足がある場合の修正UIを表示する。
        """
        logger.info("ERROR View/Container構築開始")

        err_layout = ui.LayoutView()
        err_container = build_error_container(
            params=parameters_dict,
            bonus=bonus_dict,
            is_boost=params.is_boost_active,
        )
        err_container.add_item(ui.Separator())
        row = ui.ActionRow()
        row.add_item(ParamSelect(self))
        err_container.add_item(row)
        err_layout.add_item(err_container)

        logger.info("ERROR View/Container構築完了: メッセージ送信を開始")
        await interaction.edit_original_response(view=err_layout)

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
    async def _recompute_and_edit(self, interaction: discord.Interaction, merged: dict):
        """
        merged には vo_status/vo_bonus/now_fans/kirameki などが int 化されて入っている想定。
        OCRは再実行せず、値だけ差し替えて必要スコアを再計算し、新規メッセージを送信。
        """
        # 1) 直近の固定情報（実行時の params 相当）を保持しておく
        #    初回 execute() で保存しておく
        static = getattr(self, "_static", None)
        if not static:
            # 初回に備えた保険。execute() 冒頭で _static を必ず埋めるのが理想。
            await interaction.followup.send(
                embed=Embed(title="再計算エラー", description="内部状態が不足しています。もう一度コマンドを実行してください。"),
                ephemeral=True
            )
            return

        async with self.scoped_ctx(interaction):
            self.log_recompute_start(COMMAND_NAME)
            t0 = time.perf_counter()

            inference_use_case = (
                self._get_inference_use_case(
                    interaction
                )
            )

            result, pairs = inference_use_case.calculate(
                character=static["character"],
                mode=static["mode"],
                audition=merged["audition"],
                target_grade=static["target_grade"],
                target_score=static["target_score"],
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

            # View / Container構築 -> メッセージ送信
            logger.debug("View/Container構築開始")
            layout = ui.LayoutView()
            container = build_required_score_container(result, override_pairs=pairs)
            container.add_item(ui.Separator())

            row = ui.ActionRow()
            row.add_item(ParamSelect(self))
            container.add_item(row)

            audition_select = ui.ActionRow()
            audition_select.add_item(AuditionSelect(self))
            container.add_item(audition_select)

            layout.add_item(container)
            logger.debug("View/Container構築完了")
            await interaction.followup.send(view=layout)

            dt = (time.perf_counter() - t0) * 1000
            logger.debug(f"nia_required_score_command finished in {dt:.2f} ms")
            self.log_recompute_end(COMMAND_NAME)
