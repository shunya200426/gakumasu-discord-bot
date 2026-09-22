# scenarios/hif_scenario.py

import math

from config.hif_settings import HIF
from models.hif.final_grade.params import HifFinalGradeParams
from models.hif.final_grade.result import HifFinalGradeResult
from utils.logger import get_logger

from .base_scenario import ScenarioBase


class HifScenario(ScenarioBase):
    def __init__(self, mode: str):
        super().__init__(
            mode=mode,
            scenario_key="HIF",
        )

        self.settings = HIF
        self.log = get_logger(context={
            "scenario": "HIF",
            "mode": mode,
        })

    def calculate_score(
        self,
        params: HifFinalGradeParams,
    ) -> HifFinalGradeResult:
        """
        H.I.Fの評価値を計算する
        """

        # 入力情報を整理
        vo = params.vo_status
        da = params.da_status
        vi = params.vi_status

        round1_score = params.round1_score
        round2_score = params.round2_score

        self.log.debug(
            "input status: Vo=%d, Da=%d, Vi=%d",
            vo,
            da,
            vi,
        )

        # 試験終了時アビリティによるパラメータ加算
        vo += params.vo_ability
        da += params.da_ability
        vi += params.vi_ability

        # パラメータ上限でキャップ
        st_max = self.settings[self.mode]["st_max"]

        final_vo_status = min(vo, st_max)
        final_da_status = min(da, st_max)
        final_vi_status = min(vi, st_max)

        self.log.debug(
            "final status: Vo=%d, Da=%d, Vi=%d",
            final_vo_status,
            final_da_status,
            final_vi_status,
        )

        # パラメータ評価値
        status_rate = self.settings[self.mode]["status_point_rate"]

        status_eval_points = self.calclate_stats_score(
            final_vo_status,
            final_da_status,
            final_vi_status,
            status_rate,
        )

        self.log.debug(
            "status_eval_points: %d",
            status_eval_points,
        )

        # R1評価値
        # R1評価値は補正前スコアを使用
        # 補正後は1.2倍
        round1_score_corrected = math.floor(round1_score * 1.2)

        round1_settings = (
            self.settings[self.mode]
            ["score_attenuation"]
            ["round1"]
        )

        round1_eval_points = self._apply_attenuation(
            round1_score,
            round1_settings["thresholds"],
            round1_settings["coefficients"],
            round1_settings["den"],
        )

        self.log.debug(
            "round1_score: before_correction=%d, after_correction=%d, eval_points=%d",
            params.round1_score,
            round1_score_corrected,
            round1_eval_points,
        )

        # R2評価値
        round2_settings = (
            self.settings[self.mode]
            ["score_attenuation"]
            ["round2"]
        )

        round2_eval_points = self._apply_attenuation(
            round2_score,
            round2_settings["thresholds"],
            round2_settings["coefficients"],
            round2_settings["den"],
        )

        self.log.debug(
            "round2_score=%d, round2_eval_points=%d",
            round2_score,
            round2_eval_points,
        )

        # R2試験から獲得するスター性
        round2_star_settings = (
            self.settings[self.mode]
            ["star_gain"]
            ["round2"]
        )

        round2_star_gain = self._calculate_star_gain(
            round2_score,
            round2_star_settings["thresholds"],
            round2_star_settings["coefficients"],
            round2_star_settings["den"],
            round2_star_settings["multiplier"],
        )

        # 最終スター性
        #
        # star_before_round2 は外部ですでに
        # 「R2開始前スター性」へ正規化済みとする
        final_star = (
            params.star_before_round2
            + round2_star_gain
        )

        self.log.debug(
            "star_before_round2=%d, round2_star_gain=%d, "
            "final_star=%d",
            params.star_before_round2,
            round2_star_gain,
            final_star,
        )

        # スター性による評価値
        star_rate = self.settings[self.mode]["star_point_rate"]

        star_eval_points = math.floor(
            final_star * star_rate
        )

        # 通常時の最終評価値
        base_offset = self.settings[self.mode]["base_offset"]

        final_eval_points = (
            status_eval_points
            + star_eval_points
            + round1_eval_points
            + round2_eval_points
            + base_offset
        )

        self.log.debug(
            "base evaluation: status=%d star=%d "
            "round1=%d round2=%d offset=%d total=%d",
            status_eval_points,
            star_eval_points,
            round1_eval_points,
            round2_eval_points,
            base_offset,
            final_eval_points,
        )

        # アイドル強化月間
        if params.is_boost_active:
            get_kirameki = self._calculate_kirameki_gain()

            final_eval_points = self.boosted_mode(
                final_eval_points,
                params.kirameki + get_kirameki,
            )

            self.log.debug(
                "boosted evaluation: base_kirameki=%d "
                "get_kirameki=%d final=%d",
                params.kirameki,
                get_kirameki,
                final_eval_points,
            )

        # 最終評価
        final_grade = self.get_grade(final_eval_points)

        self.log.info(
            "final_eval_points=%d, final_grade=%s",
            final_eval_points,
            final_grade,
        )

        return HifFinalGradeResult(
            **params.__dict__,
            round1_score_corrected=round1_score_corrected,
            final_vo_status=final_vo_status,
            final_da_status=final_da_status,
            final_vi_status=final_vi_status,
            status_eval_points=status_eval_points,
            round1_eval_points=round1_eval_points,
            round2_eval_points=round2_eval_points,
            round2_star_gain=round2_star_gain,
            final_star=final_star,
            star_eval_points=star_eval_points,
            final_point=final_eval_points,
            final_grade=final_grade,
        )

    def _calculate_star_gain(
        self,
        raw_exam_score: int,
        thresholds: list[int],
        coefficients: list[int],
        den: int,
        multiplier: float,
    ) -> int:
        """
        各ラウンドのスコアから獲得するスター性を計算する
        """
        numerator = 0

        for i in range(len(thresholds) - 1):
            width = max(
                0,
                min(raw_exam_score, thresholds[i + 1]) - thresholds[i],
            )

            numerator += width * coefficients[i]

        base_stars = math.ceil(numerator / den)

        return math.floor(base_stars * multiplier)

    def _calculate_kirameki_gain(self) -> int:
        """
        H.I.Fの試験から獲得するきらめき数を返す。

        TODO:
            正式な計算式が判明後に置き換える。
            現在は最大値の190で固定。
        """
        return 190