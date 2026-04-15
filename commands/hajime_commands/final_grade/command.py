# hajime_commands/final_grade/command.py
import discord
from discord import ui
from commands.base_command import BaseCommand
from models.hajime.final_grade.params import HajimeFinalGradeParams
from models.hajime.final_grade.result import HajimeFinalGradeResult
from scenarios import HajimeScenario
from .container_builder import build_final_grade_container
from utils.logger import get_logger

COMMAND_NAME = "hajime_final_grade"
logger = get_logger()

# --- Modal 定義 ---
class ExamScoreEditModal(ui.Modal):
    def __init__(self, cmd: "HajimeFinalGradeCommand"):
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

        # 空欄なら維持
        if raw == "":
            new_exam_score = self.cmd._static.get("final_exam_score")
        else:
            try:
                new_exam_score = int(raw)
            except ValueError:
                await interaction.response.send_message(
                    "半角数字で入力してください。",
                    ephemeral=True,
                )
                return
        await self.cmd._recompute_and_edit(interaction, new_exam_score)

# --- Button 定義 ---
class ExamScoreEditButton(ui.Button):
    def __init__(self, cmd: "HajimeFinalGradeCommand"):
        super().__init__(
            style=discord.ButtonStyle.primary, 
            label="最終試験のスコアを変更する"
        )
        self.cmd = cmd
        
    async def callback(self, interaction: discord.Interaction):
        await interaction.response.send_modal(ExamScoreEditModal(self.cmd))
        
        # ボタンを無効化
        self.disabled = True
        await interaction.message.edit(view=self.view)

class HajimeFinalGradeCommand(BaseCommand):
    """
    初シナリオの最終評価計算コマンド
    """

    async def execute(self, params: HajimeFinalGradeParams):
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
            "final_exam_score": params.final_exam_score,
            "final_exam_rank": params.final_exam_rank,
            "character": params.character,
            "is_boost_active": params.is_boost_active,
            "kirameki": params.kirameki,
        }

        # インスタンス生成
        scenario = HajimeScenario(mode=params.mode)
        
        # 評価値計算の実行
        result: HajimeFinalGradeResult = scenario.calculate_score(params)

        # View/Container 構築
        logger.info("View/Container構築開始")
        layout = ui.LayoutView(timeout=600)
        container = build_final_grade_container(result)
        container.add_item(ui.Separator())
        row = ui.ActionRow()
        row.add_item(ExamScoreEditButton(self))
        container.add_item(row)
        layout.add_item(container)
        logger.info("View/Container構築完了：メッセージを送信")
        await self.interaction.response.send_message(view=layout)

        self.log_command_end(COMMAND_NAME)
        
    async def _recompute_and_edit(
        self, 
        interaction: discord.Interaction, 
        new_finale_exam_score: int | None,
    ):
        async with self.scoped_ctx(interaction):
            self.log_recompute_start(COMMAND_NAME)
            
            # 静的情報 + 編集値で params を組み直す
            edit_params = HajimeFinalGradeParams(
                mode             = self._static["mode"],
                vo_status        = self._static["vo_status"],
                da_status        = self._static["da_status"],
                vi_status        = self._static["vi_status"],
                vo_ability       = self._static["vo_ability"],
                da_ability       = self._static["da_ability"],
                vi_ability       = self._static["vi_ability"],
                mid_exam_score   = self._static["mid_exam_score"],
                final_exam_score = new_finale_exam_score if new_finale_exam_score is not None else self._static["final_exam_score"],
                final_exam_rank  = self._static["final_exam_rank"],
                character        = self._static["character"],
                is_boost_active  = self._static["is_boost_active"],
                kirameki         = self._static["kirameki"],
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
            row.add_item(ExamScoreEditButton(self))
            container.add_item(row)
            layout.add_item(container)
            logger.info("View/Container構築完了：メッセージを送信")
            
            await interaction.followup.send(view=layout)
            self.log_recompute_end(COMMAND_NAME)