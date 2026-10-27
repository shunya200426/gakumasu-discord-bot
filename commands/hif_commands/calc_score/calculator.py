# commands/hif_commands/calc_score/calculator.py

import math
from collections.abc import Callable

from config.hif_settings import HIF
from config.settings import SETTINGS
from models.hif.calc_score.params import HifCalcScoreParams
from scenarios.hif_scenario import HifScenario
from utils.logger import get_logger

from .calculation_resolver import (
    HifCalculationPlan,
    HifCalculationType,
    HifStarSource,
)

logger = get_logger()

CLEAR = "CLEAR!"
CLEAR_IMPOSSIBLE = "__CLEAR不可__"

SUPPORTED_GRADES = (
    "SSS",
    "SSS+",
    "S4",
    "S4+",
)


class HifRequiredScoreCalculator:
    """
    H.I.FシナリオのR1 / R2要求スコア計算を担当する。

    calculation_resolver.py で解決済みの
    HifCalculationPlan を受け取り、
    二分探索で要求スコアの最小値を求める。
    """

    def compute_required_result_dict(
        self,
        scenario: HifScenario,
        params: HifCalcScoreParams,
        plan: HifCalculationPlan,
    ) -> dict[str, int | str]:
        """
        SS / SS+ / SSS / SSS+ について要求スコアを計算する。
        """

        if plan.calculation_type == HifCalculationType.REQUIRED_R1:
            return self._compute_required_r1_result_dict(
                scenario=scenario,
                params=params,
                plan=plan,
            )

        if plan.calculation_type == HifCalculationType.REQUIRED_R2:
            return self._compute_required_r2_result_dict(
                scenario=scenario,
                params=params,
                plan=plan,
            )

        raise ValueError(
            "要求スコア計算ではないCalculationPlanが渡されました: "
            f"{plan.calculation_type}"
        )

    # ============================================================
    # R1要求スコア
    # ============================================================

    def _compute_required_r1_result_dict(
        self,
        scenario: HifScenario,
        params: HifCalcScoreParams,
        plan: HifCalculationPlan,
    ) -> dict[str, int | str]:
        """
        R1スコアを変化させ、
        目標評価値へ到達する最小R1スコアを求める。
        """

        max_score = (
            HIF[params.mode]
            ["score_attenuation"]
            ["round1"]
            ["thresholds"][-1]
        )

        def evaluator(round1_score: int) -> int:
            return self._evaluate_final_point(
                scenario=scenario,
                params=params,
                plan=plan,
                round1_score=round1_score,
                round2_score=plan.round2_score,
            )

        return self._compute_for_grades(
            evaluator=evaluator,
            max_score=max_score,
        )

    # ============================================================
    # R2要求スコア
    # ============================================================

    def _compute_required_r2_result_dict(
        self,
        scenario: HifScenario,
        params: HifCalcScoreParams,
        plan: HifCalculationPlan,
    ) -> dict[str, int | str]:
        """
        R2スコアを変化させ、
        目標評価値へ到達する最小R2スコアを求める。
        """

        max_score = (
            HIF[params.mode]
            ["score_attenuation"]
            ["round2"]
            ["thresholds"][-1]
        )

        def evaluator(round2_score: int) -> int:
            return self._evaluate_final_point(
                scenario=scenario,
                params=params,
                plan=plan,
                round1_score=plan.round1_score,
                round2_score=round2_score,
            )

        return self._compute_for_grades(
            evaluator=evaluator,
            max_score=max_score,
        )

    # ============================================================
    # 評価ランクごとの要求スコア
    # ============================================================

    def _compute_for_grades(
        self,
        evaluator: Callable[[int], int],
        max_score: int,
    ) -> dict[str, int | str]:

        thresholds = SETTINGS["grade_thresholds"]

        result_dict: dict[str, int | str] = {}

        for grade in SUPPORTED_GRADES:
            target_point = thresholds[grade]

            required_score = self._find_minimum_score(
                target_point=target_point,
                max_score=max_score,
                evaluator=evaluator,
            )

            result_dict[grade] = required_score

        return result_dict

    # ============================================================
    # 二分探索
    # ============================================================

    def _find_minimum_score(
        self,
        *,
        target_point: int,
        max_score: int,
        evaluator: Callable[[int], int],
    ) -> int | str:
        """
        target_point以上となる最小スコアを二分探索で求める。

        0点ですでに到達:
            CLEAR!

        最大スコアでも未到達:
            CLEAR不可
        """

        # 0点ですでに目標到達
        if evaluator(0) >= target_point:
            return CLEAR

        # 最大値でも届かない
        if evaluator(max_score) < target_point:
            return CLEAR_IMPOSSIBLE

        low = 0
        high = max_score

        while low < high:
            mid = (low + high) // 2

            if evaluator(mid) >= target_point:
                high = mid
            else:
                low = mid + 1

        return low

    # ============================================================
    # 最終評価値
    # ============================================================

    def _evaluate_final_point(
        self,
        *,
        scenario: HifScenario,
        params: HifCalcScoreParams,
        plan: HifCalculationPlan,
        round1_score: int | None,
        round2_score: int | None,
    ) -> int:
        """
        候補R1/R2スコアから最終評価値を計算する。

        この関数は二分探索中に繰り返し呼ばれるため、
        Result生成や表示処理は行わない。
        """

        if round1_score is None:
            raise ValueError(
                "最終評価値計算に必要なround1_scoreがありません"
            )

        if round2_score is None:
            raise ValueError(
                "最終評価値計算に必要なround2_scoreがありません"
            )

        settings = HIF[params.mode]

        # --------------------------------------------------------
        # ステータス評価値
        # --------------------------------------------------------

        st_max = settings["st_max"]

        final_vo = min(
            params.vo_status + params.vo_ability,
            st_max,
        )
        final_da = min(
            params.da_status + params.da_ability,
            st_max,
        )
        final_vi = min(
            params.vi_status + params.vi_ability,
            st_max,
        )

        status_eval_points = scenario.calclate_stats_score(
            final_vo,
            final_da,
            final_vi,
            settings["status_point_rate"],
        )

        # --------------------------------------------------------
        # R1評価値
        # --------------------------------------------------------

        round1_settings = (
            settings["score_attenuation"]["round1"]
        )

        round1_eval_points = scenario._apply_attenuation(
            round1_score,
            round1_settings["thresholds"],
            round1_settings["coefficients"],
            round1_settings["den"],
        )

        # --------------------------------------------------------
        # R2評価値
        # --------------------------------------------------------

        round2_settings = (
            settings["score_attenuation"]["round2"]
        )

        round2_eval_points = scenario._apply_attenuation(
            round2_score,
            round2_settings["thresholds"],
            round2_settings["coefficients"],
            round2_settings["den"],
        )

        # --------------------------------------------------------
        # R2開始前スター性
        # --------------------------------------------------------

        star_before_round2 = (
            self.resolve_star_before_round2(
                scenario=scenario,
                params=params,
                plan=plan,
                round1_score=round1_score,
            )
        )

        # --------------------------------------------------------
        # R2獲得スター性
        # --------------------------------------------------------

        round2_star_settings = (
            settings["star_gain"]["round2"]
        )

        round2_star_gain = scenario._calculate_star_gain(
            round2_score,
            round2_star_settings["thresholds"],
            round2_star_settings["coefficients"],
            round2_star_settings["den"],
            round2_star_settings["multiplier"],
        )

        final_star = (
            star_before_round2
            + round2_star_gain
        )

        star_eval_points = math.floor(
            final_star
            * settings["star_point_rate"]
        )

        # --------------------------------------------------------
        # 通常評価値
        # --------------------------------------------------------

        final_point = (
            status_eval_points
            + round1_eval_points
            + round2_eval_points
            + star_eval_points
            + settings["base_offset"]
        )

        # --------------------------------------------------------
        # アイドル強化月間
        # --------------------------------------------------------

        if params.is_boost_active:
            get_kirameki = (
                scenario._calculate_kirameki_gain()
            )

            final_point = scenario.boosted_mode(
                final_point,
                params.kirameki + get_kirameki,
            )

        return final_point

    # ============================================================
    # R2開始前スター性
    # ============================================================

    def resolve_star_before_round2(
        self,
        *,
        scenario: HifScenario,
        params: HifCalcScoreParams,
        plan: HifCalculationPlan,
        round1_score: int,
    ) -> int:
        """
        CalculationPlanに従って、
        R2開始前スター性を確定する。
        """

        star_max = HIF[params.mode]["star_max"]

        # --------------------------------------------------------
        # R2前スター性を直接使用
        # --------------------------------------------------------

        if plan.star_source in (
            HifStarSource.ROUND2_INPUT,
            HifStarSource.DEFAULT_ROUND2,
        ):
            if plan.star_before_round2 is None:
                raise ValueError(
                    "R2開始前スター性が解決されていません"
                )

            return plan.star_before_round2

        # --------------------------------------------------------
        # R1前スター性からR2前スター性を算出
        # --------------------------------------------------------

        if plan.star_source in (
            HifStarSource.ROUND1_INPUT,
            HifStarSource.DEFAULT_ROUND1,
            HifStarSource.DERIVE_ROUND2_FROM_ROUND1,
        ):
            if plan.star_before_round1 is None:
                raise ValueError(
                    "R1開始前スター性が解決されていません"
                )

            round1_star_gain = (
                self._calculate_round1_star_gain(
                    scenario=scenario,
                    params=params,
                    round1_score=round1_score,
                )
            )

            return min(
                plan.star_before_round1
                + round1_star_gain,
                star_max["before_round2"],
            )

        # --------------------------------------------------------
        # R2前スター性からR1前を推定する特殊ケース
        # --------------------------------------------------------

        if (
            plan.star_source
            == HifStarSource.DERIVE_ROUND1_FROM_ROUND2
        ):
            if plan.star_before_round2 is None:
                raise ValueError(
                    "R2開始前スター性が解決されていません"
                )

            if plan.round1_score_for_star_calc is None:
                raise ValueError(
                    "スター性推定用R1スコアがありません"
                )

            assumed_gain = (
                self._calculate_round1_star_gain(
                    scenario=scenario,
                    params=params,
                    round1_score=(
                        plan.round1_score_for_star_calc
                    ),
                )
            )

            estimated_star_before_round1 = max(
                0,
                plan.star_before_round2
                - assumed_gain,
            )

            actual_gain = (
                self._calculate_round1_star_gain(
                    scenario=scenario,
                    params=params,
                    round1_score=round1_score,
                )
            )

            return min(
                estimated_star_before_round1
                + actual_gain,
                star_max["before_round2"],
            )

        raise ValueError(
            "未知のHifStarSourceです: "
            f"{plan.star_source}"
        )

    # ============================================================
    # R1獲得スター性
    # ============================================================

    @staticmethod
    def _calculate_round1_star_gain(
        *,
        scenario: HifScenario,
        params: HifCalcScoreParams,
        round1_score: int,
    ) -> int:

        settings = (
            HIF[params.mode]
            ["star_gain"]
            ["round1"]
        )

        return scenario._calculate_star_gain(
            round1_score,
            settings["thresholds"],
            settings["coefficients"],
            settings["den"],
            settings["multiplier"],
        )