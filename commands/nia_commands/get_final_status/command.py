# commands/nia_commands/final_grade/command.py
from discord import ui
from commands.base_command import BaseCommand
from models.nia.get_final_status.params import NiaGetFinalStatusParams
from models.nia.get_final_status.result import NiaGetFinalStatusResult
from scenarios import NiaScenario
# from .embed_builder import build_get_final_status_embed  # Embed構築関数
from .container_builder import build_get_final_status_container
from utils.logger import logger
from config.nia_settings import NIA

class NiaGetFinalStarusCommand(BaseCommand):
    """
    NIAシナリオの最終オーディションの獲得パラメータを計算するコマンド
    """

    async def execute(self, params: NiaGetFinalStatusParams):
        self.log_command_start("nia_get_final_parameters_command")
        logger.info("入力情報: %s", params)
        
        # 限界突破スコアを設定
        score = 200000

        # シナリオ実行
        scenario = NiaScenario(mode=params.mode)

        for audition in params.audition_dict.keys():

            # 計算実行
            get_vo_status, get_da_status, get_vi_status = scenario.calculate_get_status(
                character=params.character,
                audition=audition,
                vo_score=score,
                da_score=score,
                vi_score=score,
                vo_bonus=params.vo_bonus,
                da_bonus=params.da_bonus,
                vi_bonus=params.vi_bonus,
                challenge_P_item=params.challenge_P_item
            )
            params.audition_dict[audition] = get_vo_status, get_da_status, get_vi_status

        # オーバーラインの設定
        if params.set_over_line is not None:
            max_status = params.set_over_line
        else:
            max_status=NIA[params.mode]["st_max"]

        result = NiaGetFinalStatusResult(
            character           = params.character,
            mode                = params.mode,
            audition_dict       = params.audition_dict,
            vo_bonus            = params.vo_bonus,
            da_bonus            = params.da_bonus,
            vi_bonus            = params.vi_bonus,
            challenge_P_item    = params.challenge_P_item,
            set_over_line       = params.set_over_line,
            # get_vo_status       = get_vo_status,
            # get_da_status       = get_da_status,
            # get_vi_status       = get_vi_status,
            max_status          = max_status
        )

        logger.debug(f"出力結果: {vars(result)}")

        # Embed構築
        # logger.info("Embed構築開始")
        # self.embed = build_get_final_status_embed(result)
        # logger.info("Embed構築完了: メッセージ送信を開始")

        # Discordに送信
        # await self.send_embed()

        # Container構築
        logger.info("Container構築開始")
        container = build_get_final_status_container(result)
        logger.info("Container構築完了：メッセージ送信を開始")

        # ViewにContainerを追加してメッセージを送信
        view= ui.LayoutView()
        view.add_item(container)
        await self.interaction.response.send_message(view=view)

        self.log_command_end("nia_get_final_parameters_command")