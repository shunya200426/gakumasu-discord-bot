import ast
from dataclasses import replace
from pathlib import Path

import pytest

from commands.hajime_commands.required_score.calculator import (
    CLEAR,
    CLEAR_IMPOSSIBLE,
    BoostModeNotSupportedError,
    RequiredScoreCalculator,
)
from models.hajime.required_score.params import HajimeRequiredScoreParams
from scenarios import HajimeScenario


@pytest.fixture
def params() -> HajimeRequiredScoreParams:
    return HajimeRequiredScoreParams(
        mode="legend",
        vo_status=1000,
        da_status=1000,
        vi_status=1000,
        vo_ability=0,
        da_ability=0,
        vi_ability=0,
        mid_exam_score=50000,
        target_grade=None,
        target_score=None,
        character=None,
        is_boost_active=False,
        kirameki=0,
    )


@pytest.fixture
def calculator() -> RequiredScoreCalculator:
    return RequiredScoreCalculator()


@pytest.fixture
def scenario() -> HajimeScenario:
    return HajimeScenario(mode="legend")


def test_keeps_legacy_normal_mode_results(
    calculator: RequiredScoreCalculator,
    scenario: HajimeScenario,
    params: HajimeRequiredScoreParams,
) -> None:
    result = calculator.compute_required_result_dict(scenario, params)

    assert result == {
        "SS": 298800,
        "SS+": 498200,
        "SSS": 1782000,
        "SSS+": CLEAR_IMPOSSIBLE,
    }


def test_returns_clear_when_zero_exam_score_already_reaches_target(
    calculator: RequiredScoreCalculator,
    scenario: HajimeScenario,
    params: HajimeRequiredScoreParams,
) -> None:
    clear_params = replace(
        params,
        vo_status=3000,
        da_status=3000,
        vi_status=3000,
        target_grade="SS",
    )

    result = calculator.compute_required_result_dict(scenario, clear_params)

    assert result == {"SS": CLEAR}


def test_accepts_exact_maximum_exam_score(
    calculator: RequiredScoreCalculator,
    scenario: HajimeScenario,
    params: HajimeRequiredScoreParams,
) -> None:
    exact_max_params = replace(params, target_score=20218)

    result = calculator.compute_required_result_dict(scenario, exact_max_params)

    assert result == {"TARGET": 2000000}


def test_returns_clear_impossible_above_maximum_exam_score(
    calculator: RequiredScoreCalculator,
    scenario: HajimeScenario,
    params: HajimeRequiredScoreParams,
) -> None:
    above_max_params = replace(params, target_score=20219)

    result = calculator.compute_required_result_dict(scenario, above_max_params)

    assert result == {"TARGET": CLEAR_IMPOSSIBLE}


def test_calculates_only_requested_grade(
    calculator: RequiredScoreCalculator,
    scenario: HajimeScenario,
    params: HajimeRequiredScoreParams,
) -> None:
    grade_params = replace(params, target_grade="SSS")

    result = calculator.compute_required_result_dict(scenario, grade_params)

    assert result == {"SSS": 1782000}


def test_target_score_takes_priority_over_target_grade(
    calculator: RequiredScoreCalculator,
    scenario: HajimeScenario,
    params: HajimeRequiredScoreParams,
) -> None:
    target_params = replace(params, target_grade="SS", target_score=18000)

    result = calculator.compute_required_result_dict(scenario, target_params)
    pairs, target_grade, target_score = calculator.build_pairs(
        result,
        target_params.target_grade,
        target_params.target_score,
    )

    assert result == {"TARGET": 498200}
    assert pairs == [("**目標スコア = 18000**", "498200")]
    assert target_grade is None
    assert target_score == 18000


def test_boost_mode_stops_with_explicit_unsupported_error(
    calculator: RequiredScoreCalculator,
    scenario: HajimeScenario,
    params: HajimeRequiredScoreParams,
) -> None:
    boost_params = replace(params, is_boost_active=True, kirameki=420)

    with pytest.raises(BoostModeNotSupportedError, match="現在必要スコア計算に対応していません"):
        calculator.compute_required_result_dict(scenario, boost_params)


def test_calculator_module_does_not_import_discord() -> None:
    calculator_path = (
        Path(__file__).parents[4]
        / "commands"
        / "hajime_commands"
        / "required_score"
        / "calculator.py"
    )
    tree = ast.parse(calculator_path.read_text(encoding="utf-8"))
    imported_roots = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported_roots.update(
                alias.name.split(".", maxsplit=1)[0] for alias in node.names
            )
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported_roots.add(node.module.split(".", maxsplit=1)[0])

    assert "discord" not in imported_roots
