# commands/hif_commands/calc_score/container_builder.py

import math
from pathlib import Path

import discord
from discord import ui

from commands.hif_commands.calc_score.calculation_resolver import (
    HifCalculationPlan,
    HifCalculationType,
    HifStarSource,
)
from config.character_settings import CHARACTERS
from models.hif.calc_score.params import HifCalcScoreParams
from models.hif.calc_score.result import HifCalcScoreResult

SUPPORTED_GRADES = (
    "SS",
    "SS+",
    "SSS",
    "SSS+",
)


def build_final_grade_container(
    result: HifCalcScoreResult,
) -> ui.Container:

    # キャラクター表示 / コンテナカラー
    if result.character is not None:
        container_color = CHARACTERS[result.character]["color"]
        character_block = (
            "### キャラクター\n"
            f"**{CHARACTERS[result.character]['name']}**"
        )
    else:
        container_color = discord.Color.orange()
        character_block = ""

    # 強化月間表示
    if result.is_boost_active:
        kirameki_block = (
            "### アイドル強化月間適用\n"
            f"**ほしのきらめき: {result.kirameki}**\n"
        )
    else:
        kirameki_block = ""

    # テンプレート読み込み
    tpl_path = Path(__file__).with_name(
        "final_grade_template.md"
    )
    text_template = tpl_path.read_text(
        encoding="utf-8"
    )

    # テンプレートへ値を埋め込み
    content = text_template.format(
        option_kirameki=kirameki_block,
        option_character=character_block,

        final_point=result.final_point,
        final_grade=result.final_grade,

        round1_score=result.round1_score,
        round1_score_corrected=result.round1_score_corrected,
        round2_score=result.round2_score,

        star_before_round2=result.star_before_round2,
        round2_star_gain=result.round2_star_gain,
        final_star=result.final_star,

        vo_status=result.vo_status,
        da_status=result.da_status,
        vi_status=result.vi_status,

        vo_ability=result.vo_ability,
        da_ability=result.da_ability,
        vi_ability=result.vi_ability,

        final_vo_status=result.final_vo_status,
        final_da_status=result.final_da_status,
        final_vi_status=result.final_vi_status,
    )

    container = ui.Container(
        accent_color=container_color,
    )
    container.add_item(
        ui.TextDisplay(content=content)
    )

    return container


def build_required_score_container(
    *,
    params: HifCalcScoreParams,
    plan: HifCalculationPlan,
    result_dict: dict[str, int | str],
) -> ui.Container:
    """
    H.I.F要求スコア計算結果のContainerを構築する。
    """

    # ============================================================
    # キャラクター
    # ============================================================

    if params.character is not None:
        container_color = CHARACTERS[
            params.character
        ]["color"]

        character_block = (
            "### キャラクター\n"
            f"**{CHARACTERS[params.character]['name']}**"
        )
    else:
        container_color = discord.Color.orange()
        character_block = ""

    # ============================================================
    # アイドル強化月間
    # ============================================================

    if params.is_boost_active:
        kirameki_block = (
            "### アイドル強化月間適用\n"
            f"**ほしのきらめき: {params.kirameki}**\n"
        )
    else:
        kirameki_block = ""

    # ============================================================
    # 既知の試験スコア
    # ============================================================

    known_round_name, exam_score_block = (
        _build_exam_score_block(plan)
    )

    # ============================================================
    # スター性
    # ============================================================

    star_block = _build_star_block(plan)

    # ============================================================
    # 要求スコア
    # ============================================================

    required_block = _build_required_block(
        result_dict
    )

    # ============================================================
    # 自動補完 / 仮定値
    # ============================================================

    assumption_block = _build_assumption_block(
        plan
    )

    # ============================================================
    # テンプレート
    # ============================================================

    tpl_path = Path(__file__).with_name(
        "required_score_template.md"
    )
    text_template = tpl_path.read_text(
        encoding="utf-8"
    )

    content = text_template.format(
        option_kirameki=kirameki_block,
        option_character=character_block,

        vo_status=params.vo_status,
        da_status=params.da_status,
        vi_status=params.vi_status,

        vo_ability=params.vo_ability,
        da_ability=params.da_ability,
        vi_ability=params.vi_ability,

        known_round_name=known_round_name,
        exam_score_block=exam_score_block,
        star_block=star_block,
        required_block=required_block,
        assumption_block=assumption_block,
    )

    container = ui.Container(
        accent_color=container_color,
    )
    container.add_item(
        ui.TextDisplay(content=content)
    )

    return container


def _build_exam_score_block(
    plan: HifCalculationPlan,
) -> tuple[str, str]:
    """
    要求対象ではない、既知側の試験スコア表示を生成する。
    """

    if (
        plan.calculation_type
        == HifCalculationType.REQUIRED_R2
    ):
        if plan.round1_score is None:
            raise ValueError(
                "R2要求計算ですがR1スコアがありません"
            )

        round1_score_corrected = math.floor(
            plan.round1_score * 1.2
        )

        return (
            "R1",
            (
                f"**補正前: {plan.round1_score}**\n"
                f"**補正後: {round1_score_corrected}**"
            ),
        )

    if (
        plan.calculation_type
        == HifCalculationType.REQUIRED_R1
    ):
        if plan.round2_score is None:
            raise ValueError(
                "R1要求計算ですがR2スコアがありません"
            )

        return (
            "R2",
            f"**{plan.round2_score}**",
        )

    raise ValueError(
        "要求スコア用Containerに"
        "FINAL_GRADEが渡されました"
    )


def _build_star_block(
    plan: HifCalculationPlan,
) -> str:
    """
    CalculationPlanのスター性情報を表示用Markdownへ変換する。
    """

    lines: list[str] = []

    if plan.star_before_round1 is not None:
        lines.append(
            f"**R1開始前: {plan.star_before_round1}**"
        )

    if plan.star_before_round2 is not None:
        lines.append(
            f"**R2開始前: {plan.star_before_round2}**"
        )

    # R1前からR2前を導出する場合、
    # R2前の最終値はCalculator内部で候補スコアごとに変化するため、
    # ここでは入力元のみ表示する。
    if (
        plan.star_source
        == HifStarSource.DERIVE_ROUND2_FROM_ROUND1
    ):
        lines.append(
            "*R2開始前スター性は"
            "R1スコアから算出して計算*"
        )

    if (
        plan.star_source
        == HifStarSource.DERIVE_ROUND1_FROM_ROUND2
    ):
        lines.append(
            "*R1開始前スター性は"
            "R2開始前スター性から推定して計算*"
        )

    if not lines:
        return "**—**"

    return "\n".join(lines)


def _build_required_block(
    result_dict: dict[str, int | str],
) -> str:
    """
    SS～SSS+の要求スコア表示を生成する。
    """

    lines = []

    for grade in SUPPORTED_GRADES:
        value = result_dict.get(
            grade,
            "—",
        )

        lines.append(
            f"**{grade}: {value}**"
        )

    return "\n".join(lines)


def _build_assumption_block(
    plan: HifCalculationPlan,
) -> str:
    """
    Resolverが自動補完・仮定した値を注意書きとして表示する。
    """

    notes: list[str] = []

    if plan.used_default_round2_score:
        notes.append(
            "※ R2スコア未入力のため、"
            "**0**として計算しています。"
        )

    if plan.used_default_star_before_round1:
        notes.append(
            "※ R1開始前スター性未入力のため、"
            "**930**を使用しています。"
        )

    if plan.used_default_star_before_round2:
        notes.append(
            "※ R2開始前スター性未入力のため、"
            "**1110**を使用しています。"
        )

    if (
        plan.used_assumed_round1_score_for_star_calc
    ):
        notes.append(
            "※ R1スコア未入力のため、"
            "スター性の計算ではR1スコアを"
            "**1,400,000**として扱っています。"
        )

    if not notes:
        return ""

    return (
        "### 計算上の補足\n"
        + "\n".join(notes)
    )