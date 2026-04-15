# commands/nia_commands/final_grade/embed_builder.py

from discord import Embed
from models.nia.final_grade.result import NiaFinalGradeResult
from config.settings import SETTINGS

def build_final_grade_embed(result: NiaFinalGradeResult) -> Embed:
    embed = Embed(
        title=f"NIA 【{SETTINGS['NIA'][result.mode]['name']}】",
        color=SETTINGS['characters'][result.character]['color'],
        description=f"## {SETTINGS['NIA'][result.mode][result.audition]['name']}"
    )

    if result.is_boost_active:
        embed.add_field(
            name="アイドル強化月間適用",
            value=(f"ほしのきらめき: {result.kirameki}　\n\u200b"),
            inline=False
        )

    embed.add_field(
        name="キャラクター",
        value=f"**{SETTINGS['characters'][result.character]['name']}**\n\u200b",
        inline=False
    )

    embed.add_field(
        name="最終スコア",
        value=(f"**{str(result.final_score)}: {result.final_grade}**\n\u200b"),
        inline=False
    )

    embed.add_field(
        name=f"最終オーディション {result.vo_score + result.da_score + result.vi_score}pt",
        value=(
            f"**Vo: {result.vo_score}pt**　\n"
            f"**Da: {result.da_score}pt**　\n"
            f"**Vi: {result.vi_score}pt**　\n\u200b"
        ),
        inline=False
    )

    if result.challenge_P_item != 40:
        embed.add_field(
            name="チャレンジPアイテム変更",
            value=f"**{result.challenge_P_item}%**\n\u200b",
            inline=False
        )

    embed.add_field(
        name="パラメータ",
        value=(
            f"Vo: {result.vo_status} → **__{result.final_vo_status}__（+{result.get_vo_status}）**（{result.vo_bonus}%)　\n"
            f"Da: {result.da_status} → **__{result.final_da_status}__（+{result.get_da_status}）**（{result.da_bonus}%)　\n"
            f"Vi: {result.vi_status} → **__{result.final_vi_status}__（+{result.get_vi_status}）**（{result.vi_bonus}%)　\n\u200b"
        ),
        inline=False
    )

    embed.add_field(
        name="ファン数",
        value=(
            f"{result.now_fans} → **{result.final_fans}（+{result.get_fans}）**"
        ),
        inline=False
    )

    return embed
