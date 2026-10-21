# tests/scenarios/test_hif_calc_score.py

from commands.hif_commands.calc_score.calculation_resolver import (
    HifCalculationResolver,
)
from commands.hif_commands.calc_score.calculator import (
    HifRequiredScoreCalculator,
)
from models.hif.calc_score.params import HifCalcScoreParams
from scenarios.hif_scenario import HifScenario


def make_params(**overrides) -> HifCalcScoreParams:
    """
    H.I.F calc_score テスト用のデフォルトParamsを生成する。

    各テストでは必要な値だけ overrides で差し替える。
    """

    values = {
        "mode": "default",

        "vo_status": 3000,
        "da_status": 3000,
        "vi_status": 3000,

        "vo_ability": 0,
        "da_ability": 0,
        "vi_ability": 0,

        "round1_score": 1_000_000,
        "round2_score": None,

        "star_before_round1": None,
        "star_before_round2": 1000,

        "is_boost_active": False,
        "kirameki": 0,

        "character": None,
    }

    values.update(overrides)

    return HifCalcScoreParams(**values)


def test_required_round2_score_normal():
    """
    R1入力済み / R2未入力の場合、
    R2要求スコアが計算されることを確認する。
    """

    params = make_params()

    scenario = HifScenario(
        mode=params.mode,
    )

    resolver = HifCalculationResolver()
    plan = resolver.resolve(params)

    calculator = HifRequiredScoreCalculator()

    result = calculator.compute_required_result_dict(
        scenario=scenario,
        params=params,
        plan=plan,
    )

    assert "SS" in result
    assert "SS+" in result
    assert "SSS" in result
    assert "SSS+" in result


def test_required_round1_score_is_minimum():
    """
    算出されたR2要求スコアが、
    目標評価へ到達する最小スコアであることを確認する。
    """

    params = make_params(
        vo_status=900,
        da_status=900,
        vi_status=900,
        round1_score=None,
        star_before_round2=None
    )

    scenario = HifScenario(
        mode=params.mode,
    )

    resolver = HifCalculationResolver()
    plan = resolver.resolve(params)

    calculator = HifRequiredScoreCalculator()

    result = calculator.compute_required_result_dict(
        scenario=scenario,
        params=params,
        plan=plan,
    )

    required_score = result["SS"]

    assert isinstance(required_score, int)

    # 算出された要求スコアでSSへ到達する
    final_at_required = calculator._evaluate_final_point(
        scenario=scenario,
        params=params,
        plan=plan,

        # round1_score=plan.round1_score,
        # round2_score=required_score,
        
        round1_score=required_score,
        round2_score=plan.round2_score,
    )

    # 1点下ではSSへ届かない
    final_before_required = calculator._evaluate_final_point(
        scenario=scenario,
        params=params,
        plan=plan,

        # round1_score=plan.round1_score,
        # round2_score=required_score - 1,

        round1_score=required_score - 1,
        round2_score=plan.round2_score,
    )

    assert final_at_required >= 16_000
    assert final_before_required < 16_000