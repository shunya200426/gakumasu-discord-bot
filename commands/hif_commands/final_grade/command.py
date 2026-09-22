# commands/hif_commands/final_grade/command.py

import discord
from discord import ui

from commands.base_command import BaseCommand
from config.bot_settings import LAYOUT_VIEW_TIMEOUT_SECONDS
from models.hif.final_grade.params import HifFinalGradeParams
from models.hif.final_grade.result import HifFinalGradeResult
from scenarios.hif_scenario import HifScenario
from utils.logger import get_logger

from .container_builder import build_final_grade_container

COMMAND_NAME = "hif_final_grade"
logger = get_logger()


# --- Modal 定義 ---
class Round2ScoreEditModal(ui.Modal):
    def __init__(self, cmd: "HifFinalGradeCommand"):
        super().__init__(title="ラウンド2のスコアを入力")
        self.cmd = cmd

        input_box = ui.TextInput(
            label="ラウンド2のスコア",
            required=False,
            placeholder="数値を入力",
        )

        self.add_item(input_box)
        self.input = input_box

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer()

        raw = (self.input.value or "").strip()

        # 空欄なら現在値を維持
        if raw == "":
            new_round2_score = self.cmd._static.get("round2_score")
        else:
            try:
                new_round2_score = int(raw)
            except ValueError:
                await interaction.followup.send(
                    "半角数字で入力してください。",
                    ephemeral=True,
                )
                return

            # 負数は受け付けない
            if new_round2_score < 0:
                await interaction.followup.send(
                    "0以上の数値を入力してください。",
                    ephemeral=True,
                )
                return

        await self.cmd._recompute_and_edit(
            interaction,
            new_round2_score,
        )


# --- Button 定義 ---
class Round2ScoreEditButton(ui.Button):
    def __init__(self, cmd: "HifFinalGradeCommand"):
        super().__init__(
            style=discord.ButtonStyle.primary,
            label="ラウンド2のスコアを変更する",
        )
        self.cmd = cmd

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.send_modal(
            Round2ScoreEditModal(self.cmd)
        )


class HifFinalGradeCommand(BaseCommand):
    """
    H.I.Fシナリオの最終評価計算コマンド
    """

    async def execute(self, params: HifFinalGradeParams):
        self.log_command_start(COMMAND_NAME)
        logger.info("calc params %s", params)

        # 再計算に使う情報を保存
        #
        # R2スコアだけ変更可能とし、
        # その他の値は初回入力時の値を維持する
        self._static = {
            "mode": params.mode,

            "vo_status": params.vo_status,
            "da_status": params.da_status,
            "vi_status": params.vi_status,

            "vo_ability": params.vo_ability,
            "da_ability": params.da_ability,
            "vi_ability": params.vi_ability,

            "round1_score": params.round1_score,
            "round2_score": params.round2_score,

            "star_before_round2": params.star_before_round2,

            "character": params.character,

            "is_boost_active": params.is_boost_active,
            "kirameki": params.kirameki,
        }

        # H.I.F評価値計算
        scenario = HifScenario(mode=params.mode)
        result: HifFinalGradeResult = scenario.calculate_score(params)

        # View / Container 構築
        logger.info("View/Container構築開始")

        layout = ui.LayoutView(timeout=LAYOUT_VIEW_TIMEOUT_SECONDS)

        container = build_final_grade_container(result)

        # R2スコア再計算ボタン
        container.add_item(ui.Separator())

        row = ui.ActionRow()
        row.add_item(Round2ScoreEditButton(self))
        container.add_item(row)

        layout.add_item(container)

        logger.info("View/Container構築完了：メッセージを送信")

        await self.interaction.response.send_message(
            view=layout,
        )

        self.log_command_end(COMMAND_NAME)

    async def _recompute_and_edit(
        self,
        interaction: discord.Interaction,
        new_round2_score: int | None,
    ):
        """
        ラウンド2スコアのみ変更して評価値を再計算する
        """
        async with self.scoped_ctx(interaction):
            self.log_recompute_start(COMMAND_NAME)

            # 新しいR2スコア
            round2_score = (
                new_round2_score
                if new_round2_score is not None
                else self._static["round2_score"]
            )

            # 初回入力値 + 新しいR2スコアでParamsを再構築
            edit_params = HifFinalGradeParams(
                mode=self._static["mode"],

                vo_status=self._static["vo_status"],
                da_status=self._static["da_status"],
                vi_status=self._static["vi_status"],

                vo_ability=self._static["vo_ability"],
                da_ability=self._static["da_ability"],
                vi_ability=self._static["vi_ability"],

                round1_score=self._static["round1_score"],
                round2_score=round2_score,

                star_before_round2=self._static["star_before_round2"],

                character=self._static["character"],

                is_boost_active=self._static["is_boost_active"],
                kirameki=self._static["kirameki"],
            )

            logger.info("recalc params %s", edit_params)

            # 再計算
            scenario = HifScenario(mode=edit_params.mode)
            result: HifFinalGradeResult = scenario.calculate_score(
                edit_params
            )

            # 次回再計算時の基準となるR2スコアを更新
            self._static["round2_score"] = round2_score

            # View / Container 再構築
            logger.info("View/Container再構築開始")

            layout = ui.LayoutView(timeout=LAYOUT_VIEW_TIMEOUT_SECONDS)

            container = build_final_grade_container(result)

            container.add_item(ui.Separator())

            row = ui.ActionRow()
            row.add_item(Round2ScoreEditButton(self))
            container.add_item(row)

            layout.add_item(container)

            logger.info("View/Container再構築完了：メッセージを送信")

            await interaction.followup.send(
                view=layout,
            )

            self.log_recompute_end(COMMAND_NAME)