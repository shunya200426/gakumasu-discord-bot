# scenarios/hajime.py
from typing import Dict, List
from .base_scenario import ScenarioBase
from models.hajime.final_grade.params import HajimeFinalGradeParams
from models.hajime.final_grade.result import HajimeFinalGradeResult
from config.settings import HAJIME
from utils.logger import logger
import math

class HajimeScenario(ScenarioBase):
    def __init__(self, mode: str):
        super().__init__(mode)
        self.settings = HAJIME

    def calculate_score(self, params: HajimeFinalGradeParams):
        """
        通常スコア計算
        """

        # 入力情報を整理
        vo = params.vo_status
        da = params.da_status
        vi = params.vi_status
        mid_exam_score_raw = params.mid_exam_score
        final_exam_score_raw = params.final_exam_score
    
            
        # 入力ステータス
        logger.debug(f"input status: Vo={vo}, Da={da}, Vi={vi}")

        # 試験後ステータス補正
        post_bonus = self.settings[self.mode]["exam_post_bonus"][params.final_exam_rank]
        vo += post_bonus + params.vo_ability
        da += post_bonus + params.da_ability
        vi += post_bonus + params.vi_ability
        
        # ステータス上限値でキャップ
        st_max = self.settings[self.mode]["st_max"]
        vo = min(vo, st_max)
        da = min(da, st_max)
        vi = min(vi, st_max)
        logger.debug(f"final status: Vo={vo}, Da={da}, Vi={vi}")

        # ステータス合計値 × 共通倍率
        rate = self.settings[self.mode]["status_point_rates"]
        status_eval_points = self.calclate_stats_score(vo, da, vi, rate)
        logger.debug(f"status_eval_points: {status_eval_points}")
        
        # 中間試験スコアの評価値点数
        if self.mode == "legend":
            mid_exam_thresholds = self.settings[self.mode]["score_attenuation"]["mid_exam"]["thresholds"]
            midexam_coefficients = self.settings[self.mode]["score_attenuation"]["mid_exam"]["coefficients"]
            mid_den = self.settings[self.mode]["score_attenuation"]["final_exam"]["den"]
            mid_exam_eval_points = self._apply_attenuation(mid_exam_score_raw, mid_exam_thresholds, midexam_coefficients, mid_den)
            logger.debug(f"mid_exam_score_raw: {mid_exam_score_raw}, mid_exam_eval_points: {mid_exam_eval_points}")
        else:
            mid_exam_eval_points = 0

        # 最終試験スコアの評価値点数
        thresholds = self.settings[self.mode]["score_attenuation"]["final_exam"]["thresholds"]
        coefficients = self.settings[self.mode]["score_attenuation"]["final_exam"]["coefficients"]
        den = self.settings[self.mode]["score_attenuation"]["final_exam"]["den"]
        final_exam_eval_points = self._apply_attenuation(final_exam_score_raw, thresholds, coefficients, den)
        logger.debug(f"final_raw_exam_score: {final_exam_score_raw}, final_exam_eval_points: {final_exam_eval_points}")
        
        # 順位ボーナス
        final_exam_rank_bonus_points = self.settings["final_exam_rank_bonus"][params.final_exam_rank]
        logger.debug(f"final_exam_rank: {params.final_exam_rank}, final_exam_rank_bonus_points: {final_exam_rank_bonus_points}")

        # 最終評価スコア
        final_eval_points = status_eval_points + mid_exam_eval_points + final_exam_eval_points + final_exam_rank_bonus_points
        logger.info(f"final_eval_points: {final_eval_points}")

        # 最終評価
        final_grade = self.get_grade(final_eval_points)
        logger.info(f"final_grade: {final_grade}")

        return HajimeFinalGradeResult(
            **params.__dict__,
            exam_post_bonus         = post_bonus,
            final_vo_status         = vo,
            final_da_status         = da,
            final_vi_status         = vi,
            status_eval_points      = status_eval_points,
            mid_exam_eval_points    = mid_exam_eval_points,
            final_exam_eval_points  = final_exam_eval_points,
            final_exam_rank_bonus_points = final_exam_rank_bonus_points,
            final_point             = final_eval_points,
            final_grade             = final_grade
        )
        

    def invert_attenuation(self, required_eval_points: int) -> int:
        """
        required eval points -> minimal raw score (ceil)
        """
        table = self.settings[self.mode]["score_attenuation"]["final_exam"]
        thresholds: List[int] = table["thresholds"]
        coefs: List[int] = table["coefficients"]
        den: int = table["den"]

        if required_eval_points <= 0:
            return 0

        remain = float(required_eval_points)
        score = 0

        # finite intervals
        for i in range(len(thresholds) - 1):
            lo = thresholds[i]
            hi = thresholds[i + 1]
            width = hi - lo
            rate = coefs[i] / den
            cap = width * rate  # この区間で稼げる最大評価値

            if remain <= cap + 1e-12:
                # この区間内で足りる
                need = remain / rate
                return math.ceil(lo + need)
            else:
                remain -= cap

        # tail interval
        last = thresholds[-1]
        tail_rate = coefs[len(thresholds) - 1] / den
        need = remain / tail_rate
        return math.ceil(last + need)


    def _apply_attenuation(self, raw_exam_score: int, thresholds: list, coefficients: list, den: int = 1000) -> int:
        """
        試験のスコアを、評価値点へ変換する
        raw_exam_score: 試験のスコア
        thresholds: 減衰の区間のリスト
        coefficients: 係数のリスト
        den: 係数の母数
        """
        out = []
        for i in range(len(thresholds)-1):
            width = max(0, min(raw_exam_score, thresholds[i+1]) - thresholds[i])
            out.append((width * coefficients[i]) // den)
        
        exam_eval_points = sum(out)
        
        # 減衰処理をしたスコアの値を返す
        return exam_eval_points