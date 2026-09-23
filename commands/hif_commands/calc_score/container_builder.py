# commands/hif_commands/final_grade/container_builder.py

from pathlib import Path

import discord
from discord import ui

from config.character_settings import CHARACTERS
from models.hif.final_grade.result import HifCalcScoreResult


def build_final_grade_container(
    result: HifCalcScoreResult,
) -> ui.Container:

    # キャラクター表示 / コンテナカラー
    if result.character is not None:
        container_color = CHARACTERS[result.character]["color"]
        character_block = (
            f"### キャラクター\n"
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
    tpl_path = Path(__file__).with_name("template.md")
    text_template = tpl_path.read_text(encoding="utf-8")

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

    # Container構築
    container = ui.Container(
        accent_color=container_color,
    )
    container.add_item(
        ui.TextDisplay(content=content)
    )

    return container