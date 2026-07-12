# commands/nia_commands/required_score/command.py
import time
from typing import Dict, Optional, Tuple

from discord import ui

from commands.base_command import BaseCommand
from models.nia.final_grade.params import NiaFinalGradeParams
from models.nia.required_score.params import NiaRequiredScoreParams
from models.nia.required_score.result import NiaRequiredScoreResult
from scenarios.nia_scenario import NiaScenario
from utils.logger import get_logger

from .calculator import RequiredScoreCalculator

# from .embed_builder import build_required_score_embed
from .container_builder import build_required_score_container

COMMAND = "nia_required_score"
logger = get_logger()

class NiaRequiredScoreCommand(BaseCommand):
    """
    NIAシナリオの逆計算コマンド
    """

    async def execute(self, params: NiaRequiredScoreParams):
        self.log_command_start(COMMAND)
        t0 = time.perf_counter()

        # インスタンス生成
        scenario = NiaScenario(mode=params.mode)

        # 初期calc_params
        calc_params = NiaFinalGradeParams(
            character     = params.character,
            mode          = params.mode,
            audition      = params.audition,
            vo_status     = params.vo_status,
            da_status     = params.da_status,
            vi_status     = params.vi_status,
            vo_bonus      = params.vo_bonus,
            da_bonus      = params.da_bonus,
            vi_bonus      = params.vi_bonus,
            vo_score      = 0,
            da_score      = 0,
            vi_score      = 0,
            now_fans      = params.now_fans,
            challenge_P_item = params.challenge_P_item,
            is_boost_active  = params.is_boost_active,
            kirameki         = params.kirameki
        )
        logger.info("calc params %s", calc_params)

        # --- 共通コアへ委譲 ---
        t_core = time.perf_counter()
        result_dict = self._compute_required_result_dict(
            scenario=scenario,
            calc_params=calc_params,
            character=params.character,
            mode=params.mode,
            audition=params.audition,
            target_grade=params.target_grade,
            target_score=params.target_score,
        )
        logger.debug(
            "[required_score] compute_result_dict finished in %.1f ms",
            (time.perf_counter() - t_core) * 1000
        )

        t_pairs = time.perf_counter()
        pairs, target_grade_norm, target_score_norm = self._build_pairs(
            result_dict=result_dict,
            target_grade=params.target_grade,
            target_score=params.target_score,
        )
        logger.debug(
            "[required_score] build_pairs finished in %.1f ms mode=%s",
            (time.perf_counter() - t_pairs) * 1000,
            ("target_score" if target_score_norm is not None else
             "target_grade" if target_grade_norm is not None else "all_grades")
        )

        result = NiaRequiredScoreResult(
            character              = params.character,
            mode                   = params.mode,
            audition               = params.audition,
            vo_status              = params.vo_status,
            da_status              = params.da_status,
            vi_status              = params.vi_status,
            vo_bonus               = params.vo_bonus,
            da_bonus               = params.da_bonus,
            vi_bonus               = params.vi_bonus,
            now_fans               = params.now_fans,
            challenge_P_item       = params.challenge_P_item,
            is_boost_active        = params.is_boost_active,
            kirameki               = params.kirameki,
            SS_required_score      = self._total_or_none(result_dict.get("SS")),
            SS_plus_required_score = self._total_or_none(result_dict.get("SS+")),
            SSS_required_score     = self._total_or_none(result_dict.get("SSS")),
            SSS_plus_required_score= self._total_or_none(result_dict.get("SSS+")),
        )

        # 出力サマリ（INFO）
        def _brief(v):
            if isinstance(v, dict):
                return f"{v.get('total')} (Vo={v.get('vo')},Da={v.get('da')},Vi={v.get('vi')})" + (" [CLEAR!]" if "note" in v else "")
            return v
        logger.info(
            "result summary SS=%s SS+=%s SSS=%s SSS+=%s",
            _brief(result_dict.get("SS")), _brief(result_dict.get("SS+")),
            _brief(result_dict.get("SSS")), _brief(result_dict.get("SSS+")),
        )

        # logger.info("Embed構築開始")
        # self.embed = build_required_score_embed(result, override_pairs=pairs)
        # logger.info("Embed構築完了: メッセージ送信を開始")
        # await self.send_embed()
        # dt = (time.perf_counter() - t0) * 1000
        # logger.debug(f"nia_required_score_command finished in {dt:.2f} ms")
        # self.log_command_end("nia_required_score_command")

        # View / Container構築 -> メッセージ送信
        logger.debug("View/Container構築開始")
        view = ui.LayoutView()
        container = build_required_score_container(result, override_pairs=pairs)
        view.add_item(container)
        logger.debug("View/Container構築完了: メッセージ送信を開始")
        await self.interaction.response.send_message(view=view)

        dt = (time.perf_counter() - t0) * 1000
        logger.debug(f"nia_required_score_command finished in {dt:.2f} ms")
        self.log_command_end("nia_required_score_command")

    def _compute_required_result_dict(
        self,
        scenario: NiaScenario,
        calc_params: NiaFinalGradeParams,
        character: str,
        mode: str,
        audition: str,
        target_grade: Optional[str],
        target_score: Optional[int],
    ) -> Dict[str, object]:
        """
        共有コア：逆算ロジック本体
        戻り値: result_dict（"SS" などのキー: dict or "CLEAR不可" or None）
        """
        return RequiredScoreCalculator().compute_required_result_dict(
            scenario=scenario,
            calc_params=calc_params,
            character=character,
            mode=mode,
            audition=audition,
            target_grade=target_grade,
            target_score=target_score,
        )

    def _build_pairs(
        self,
        result_dict: Dict[str, object],
        target_grade: Optional[str],
        target_score: Optional[int],
    ) -> Tuple[list, Optional[str], Optional[int]]:
        """
        表示ペア（タイトル, 値）を生成。embed_builder の override_pairs に渡す。
        戻り値: (pairs, 正規化済みランク or None, 正規化済みスコア or None)
        """
        return RequiredScoreCalculator().build_pairs(
            result_dict=result_dict,
            target_grade=target_grade,
            target_score=target_score,
        )
    
    def _total_or_none(self, d):
        return RequiredScoreCalculator().total_or_none(d)
