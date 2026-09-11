# hajime_commands/required_score/command.py

import discord
from discord import ui

from commands.base_command import BaseCommand
from commands.hajime_commands.final_grade.container_builder import (
    build_final_grade_container,
)
from models.hajime.final_grade.params import HajimeFinalGradeParams
from models.hajime.final_grade.result import HajimeFinalGradeResult
from models.hajime.required_score.params import HajimeRequiredScoreParams
from models.hajime.required_score.result import HajimeRequiredScoreResult
from scenarios import HajimeScenario
from utils.logger import get_logger

from .calculator import BoostModeNotSupportedError, RequiredScoreCalculator
from .container_builder import build_required_score_container

COMMAND_NAME = "hajime_required_score"
logger = get_logger()

# --- Modal 定義 ---
class AddExamScoreModal(ui.Modal):
    def __init__(self, cmd: "HajimeRequiredScoreCommand"):
        super().__init__(title="最終試験のスコアを入力")
        self.cmd = cmd
        input_box = ui.TextInput(
            label="最終試験のスコア",
            required=False,
            placeholder="数値を入力"
        )
        self.add_item(input_box)
        self.input = input_box
        
    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer()
        raw = (self.input.value or "").strip()

        try:
            new_exam_score = int(raw)
        except ValueError:
            await interaction.response.send_message(
                "半角数字で入力してください。",
                ephemeral=True,
            )
            return
        
        await self.cmd._calc_final_grade(interaction, new_exam_score)

# --- Button 定義 ---
class AddExamScoreButton(ui.Button):
    def __init__(self, cmd: "HajimeRequiredScoreCommand"):
        super().__init__(
            style=discord.ButtonStyle.primary, 
            label="最終試験のスコアを入力する"
        )
        self.cmd = cmd
        
    async def callback(self, interaction: discord.Interaction):
        await interaction.response.send_modal(AddExamScoreModal(self.cmd))
        
        # ボタンを無効化
        self.disabled = True
        await interaction.message.edit(view=self.view)

class HajimeRequiredScoreCommand(BaseCommand):
    """
    初シナリオの目標グレード/スコアに必要な
    最終試験スコアを計算するコマンド
    """

    async def execute(self, params: HajimeRequiredScoreParams):
        self.log_command_start(COMMAND_NAME)
        logger.info("calc params %s", params)
        
        # 再計算に使う固定情報を保存
        self._static = {
            "mode": params.mode,
            "vo_status": params.vo_status,
            "da_status": params.da_status,
            "vi_status": params.vi_status,
            "vo_ability": params.vo_ability,
            "da_ability": params.da_ability,
            "vi_ability": params.vi_ability,
            "mid_exam_score": params.mid_exam_score,
            "character": params.character,
            "is_boost_active": params.is_boost_active,
            "kirameki": params.kirameki,
            "exam_score": 0,
        }

        # インスタンス生成
        scenario = HajimeScenario(mode=params.mode)
        
        # 要求スコアの計算
        calculator = RequiredScoreCalculator()
        try:
            result_dict = calculator.compute_required_result_dict(
                scenario=scenario,
                params=params,
            )
        except BoostModeNotSupportedError as exc:
            logger.info("required score calculation stopped: %s", exc)
            await self.interaction.response.send_message(str(exc), ephemeral=True)
            self.log_command_end(COMMAND_NAME)
            return
        logger.debug("[required_score] compute_result_dict finished")
        
        pairs, target_grade_norm, target_score_norm = calculator.build_pairs(
            result_dict=result_dict,
            target_grade=params.target_grade,
            target_score=params.target_score,
        )
        logger.debug(
            "[required_score] build_pairs finished mode=%s",
            ("target_score" if target_score_norm is not None else
             "target_grade" if target_grade_norm is not None else "all_grades")
        )
        
        result = HajimeRequiredScoreResult(
            **params.__dict__,
            SS_required_score      = result_dict.get("SS"),
            SS_plus_required_score = result_dict.get("SS+"),
            SSS_required_score     = result_dict.get("SSS"),
            SSS_plus_required_score= result_dict.get("SSS+"),
        )
        
        logger.info(
            "result summary SS=%s SS+=%s SSS=%s SSS+=%s",
            result_dict.get("SS"),
            result_dict.get("SS+"),
            result_dict.get("SSS"),
            result_dict.get("SSS+"),
        )

        # View / Container構築 -> メッセージ送信
        logger.info("View/Container構築開始")
        view = ui.LayoutView()
        container = build_required_score_container(result, override_pairs=pairs)
        container.add_item(ui.Separator())
        row = ui.ActionRow()
        row.add_item(AddExamScoreButton(self))
        container.add_item(row)
        view.add_item(container)
        logger.info("View/Container構築完了：メッセージを送信")
        await self.interaction.response.send_message(view=view)

        self.log_command_end(COMMAND_NAME)

    async def _calc_final_grade(
        self, 
        interaction: discord.Interaction, 
        add_exam_score: int,
    ):
        async with self.scoped_ctx(interaction):
            self.log_recompute_start(COMMAND_NAME)
            
            # params組み直し
            edit_params = HajimeFinalGradeParams(
                mode                = self._static["mode"],
                vo_status           = self._static["vo_status"],
                da_status           = self._static["da_status"],
                vi_status           = self._static["vi_status"],
                vo_ability          =  self._static["vo_ability"],
                da_ability          = self._static["da_ability"],
                vi_ability          = self._static["vi_ability"],
                mid_exam_score      = self._static["mid_exam_score"],
                final_exam_score    = add_exam_score,
                final_exam_rank     = "first",
                character           = self._static["character"],
                is_boost_active     = self._static["is_boost_active"],
                kirameki            = self._static["kirameki"],
            )
            logger.info("calc params %s", edit_params)
            
            scenario = HajimeScenario(mode=edit_params.mode)
            result: HajimeFinalGradeResult = scenario.calculate_score(edit_params)
            
            # View/Container 構築
            logger.info("View/Container構築開始")
            layout = ui.LayoutView()
            container = build_final_grade_container(result)
            container.add_item(ui.Separator())
            row = ui.ActionRow()
            row.add_item(AddExamScoreButton(self))
            container.add_item(row)
            layout.add_item(container)
            logger.info("View/Container構築完了：メッセージを送信")
            
            await interaction.followup.send(view=layout)
            self.log_recompute_end(COMMAND_NAME)
