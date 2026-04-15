# commands/nia_commands/final_grade/command.py
from discord import ui
from commands.base_command import BaseCommand
from models.nia.final_grade.params import NiaFinalGradeParams
from models.nia.final_grade.result import NiaFinalGradeResult
from scenarios import NiaScenario
# from .embed_builder import build_final_grade_embed  # Embed構築関数
from .container_builder import build_final_grade_container
from utils.logger import logger

class NiaFinalGradeCommand(BaseCommand):
    """
    NIAシナリオの最終評価計算コマンド
    """

    async def execute(self, params: NiaFinalGradeParams):
        self.log_command_start("nia_final_grade")
        logger.info(f"入力情報: {vars(params)}")

        # シナリオ実行
        scenario = NiaScenario(mode=params.mode)
        result: NiaFinalGradeResult = scenario.calculate_score(params)

        logger.info(f"最終スコア: {result.final_score}")
        logger.info(f"評価ランク: {result.final_grade}")

        # Embed構築
        # logger.info("Embed構築開始")
        # self.embed = build_final_grade_embed(result)
        # logger.info("Embed構築完了: メッセージ送信を開始")

        # Discordに送信
        # await self.send_embed()

        # Container 構築
        logger.info("Container構築開始")
        container = build_final_grade_container(result)
        logger.info("Container構築完了：メッセージを送信")

        # View に Container を追加して送信
        view = ui.LayoutView()
        view.add_item(container)
        await self.interaction.response.send_message(view=view)

        self.log_command_end("nia_final_grade")
