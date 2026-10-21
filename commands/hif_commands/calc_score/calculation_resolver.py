# commands/hif_commands/calc_score/calculation_resolver.py

from dataclasses import dataclass
from enum import Enum

from config.hif_settings import HIF
from models.hif.calc_score.params import HifCalcScoreParams


class HifCalculationType(Enum):
    """H.I.F calc_score で実行する計算種別。"""

    FINAL_GRADE = "final_grade"
    REQUIRED_R1 = "required_r1"
    REQUIRED_R2 = "required_r2"


class HifStarSource(Enum):
    """計算に使用するスター性の決定方法。"""

    # ユーザー入力値をそのまま使用
    ROUND1_INPUT = "round1_input"
    ROUND2_INPUT = "round2_input"

    # R1前スター性 + R1獲得スター性からR2前を算出
    DERIVE_ROUND2_FROM_ROUND1 = "derive_round2_from_round1"

    # R2前スター性から、R1=最大スコアと仮定してR1前を推定
    DERIVE_ROUND1_FROM_ROUND2 = "derive_round1_from_round2"

    # デフォルト値
    DEFAULT_ROUND1 = "default_round1"
    DEFAULT_ROUND2 = "default_round2"


@dataclass(frozen=True)
class HifCalculationPlan:
    """入力内容を解釈した後の計算計画。"""

    calculation_type: HifCalculationType

    round1_score: int | None
    round2_score: int | None

    star_before_round1: int | None
    star_before_round2: int | None

    star_source: HifStarSource

    # R1スター獲得量の算出に使用するスコア。
    #
    # 通常は実際のR1スコア。
    # 特殊ケースではR1上限スコアを仮定する。
    round1_score_for_star_calc: int | None = None

    # 自動補完・仮定した値を表示側で判別するためのフラグ
    used_assumed_round1_score_for_star_calc: bool = False
    used_default_round2_score: bool = False
    used_default_star_before_round1: bool = False
    used_default_star_before_round2: bool = False


class HifCalculationResolver:
    """H.I.F calc_score の入力状態から計算方法を決定する。"""

    def resolve(
        self,
        params: HifCalcScoreParams,
    ) -> HifCalculationPlan:

        round1_score = params.round1_score
        round2_score = params.round2_score

        # ============================================================
        # R1 / R2 両方入力
        # -> 最終評価
        # ============================================================

        if (
            round1_score is not None
            and round2_score is not None
        ):
            return self._resolve_final_grade(
                params
            )

        # ============================================================
        # R1のみ入力
        # -> R2要求スコア
        # ============================================================

        if round1_score is not None:
            return self._resolve_required_r2(
                params
            )

        # ============================================================
        # R1未入力
        # -> R1要求スコア
        #
        # R2も未入力ならR2=0を仮定
        # ============================================================

        return self._resolve_required_r1(
            params
        )

    def _resolve_final_grade(
        self,
        params: HifCalcScoreParams,
    ) -> HifCalculationPlan:
        """
        R1 / R2両方入力済み。

        R2前スター性を優先する。
        R2前が未入力でR1前が入力済みなら、
        R1獲得スター性を加算してR2前を導出する。
        両方未入力ならR2前スター性の最大値を使用する。
        """

        if params.star_before_round2 is not None:
            return HifCalculationPlan(
                calculation_type=HifCalculationType.FINAL_GRADE,
                round1_score=params.round1_score,
                round2_score=params.round2_score,
                star_before_round1=params.star_before_round1,
                star_before_round2=params.star_before_round2,
                star_source=HifStarSource.ROUND2_INPUT,
            )

        if params.star_before_round1 is not None:
            return HifCalculationPlan(
                calculation_type=HifCalculationType.FINAL_GRADE,
                round1_score=params.round1_score,
                round2_score=params.round2_score,
                star_before_round1=params.star_before_round1,
                star_before_round2=None,
                star_source=HifStarSource.DERIVE_ROUND2_FROM_ROUND1,
                round1_score_for_star_calc=params.round1_score,
            )

        default_star = HIF[params.mode]["star_max"]["before_round2"]

        return HifCalculationPlan(
            calculation_type=HifCalculationType.FINAL_GRADE,
            round1_score=params.round1_score,
            round2_score=params.round2_score,
            star_before_round1=None,
            star_before_round2=default_star,
            star_source=HifStarSource.DEFAULT_ROUND2,
            used_default_star_before_round2=True,
        )

    def _resolve_required_r2(
        self,
        params: HifCalcScoreParams,
    ) -> HifCalculationPlan:
        """
        R1入力済み / R2未入力。

        R2前スター性を優先する。
        R2前が未入力でR1前が入力済みなら、
        R1獲得スター性を加算してR2前を導出する。
        両方未入力ならR2前スター性の最大値を使用する。
        """

        if params.star_before_round2 is not None:
            return HifCalculationPlan(
                calculation_type=HifCalculationType.REQUIRED_R2,
                round1_score=params.round1_score,
                round2_score=None,
                star_before_round1=params.star_before_round1,
                star_before_round2=params.star_before_round2,
                star_source=HifStarSource.ROUND2_INPUT,
            )

        if params.star_before_round1 is not None:
            return HifCalculationPlan(
                calculation_type=HifCalculationType.REQUIRED_R2,
                round1_score=params.round1_score,
                round2_score=None,
                star_before_round1=params.star_before_round1,
                star_before_round2=None,
                star_source=HifStarSource.DERIVE_ROUND2_FROM_ROUND1,
                round1_score_for_star_calc=params.round1_score,
            )

        default_star = HIF[params.mode]["star_max"]["before_round2"]

        return HifCalculationPlan(
            calculation_type=HifCalculationType.REQUIRED_R2,
            round1_score=params.round1_score,
            round2_score=None,
            star_before_round1=None,
            star_before_round2=default_star,
            star_source=HifStarSource.DEFAULT_ROUND2,
            used_default_star_before_round2=True,
        )

    def _resolve_required_r1(
        self,
        params: HifCalcScoreParams,
    ) -> HifCalculationPlan:
        """
        R1未入力。

        R2入力済み:
            R1要求スコアを計算する。

        R2未入力:
            R2=0としてR1要求スコアを計算する。

        スター性:
            R1前スター性を優先する。

            R1前未入力かつ、
            R2スコア・R2前スター性が両方入力済みの場合のみ、
            R1=上限スコアと仮定してR1前スター性を推定する。

            それ以外はR1前スター性の最大値を使用する。
        """

        round2_score = params.round2_score
        used_default_round2_score = False

        # R1/R2両方未入力ならR2=0
        if round2_score is None:
            round2_score = 0
            used_default_round2_score = True

        # R1前スター性が入力されている場合は最優先
        if params.star_before_round1 is not None:
            return HifCalculationPlan(
                calculation_type=HifCalculationType.REQUIRED_R1,
                round1_score=None,
                round2_score=round2_score,
                star_before_round1=params.star_before_round1,
                star_before_round2=params.star_before_round2,
                star_source=HifStarSource.ROUND1_INPUT,
                used_default_round2_score=used_default_round2_score,
            )

        # ------------------------------------------------------------
        # 特殊ケース
        #
        # R1未入力
        # R2入力済み
        # R1前スター性未入力
        # R2前スター性入力済み
        #
        # R1=最大スコアとしてスター性を推定する
        # ------------------------------------------------------------

        if (
            params.round2_score is not None
            and params.star_before_round2 is not None
        ):
            round1_max_score = (
                HIF[params.mode]["score_attenuation"]
                ["round1"]["thresholds"][-1]
            )

            return HifCalculationPlan(
                calculation_type=HifCalculationType.REQUIRED_R1,
                round1_score=None,
                round2_score=round2_score,
                star_before_round1=None,
                star_before_round2=params.star_before_round2,
                star_source=HifStarSource.DERIVE_ROUND1_FROM_ROUND2,
                round1_score_for_star_calc=round1_max_score,
                used_assumed_round1_score_for_star_calc=True,
                used_default_round2_score=False,
            )

        # ------------------------------------------------------------
        # R1前スター性未入力
        #
        # R2前スター性だけ入力されていても、
        # R2も未入力ならR1要求計算のためR1前最大値を採用する。
        # ------------------------------------------------------------

        default_star = HIF[params.mode]["star_max"]["before_round1"]

        return HifCalculationPlan(
            calculation_type=HifCalculationType.REQUIRED_R1,
            round1_score=None,
            round2_score=round2_score,
            star_before_round1=default_star,
            star_before_round2=params.star_before_round2,
            star_source=HifStarSource.DEFAULT_ROUND1,
            used_default_round2_score=used_default_round2_score,
            used_default_star_before_round1=True,
        )