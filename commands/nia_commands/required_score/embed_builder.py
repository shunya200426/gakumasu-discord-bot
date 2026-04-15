# required_score/embed_builder.py
from typing import Iterable, Tuple, Any, Optional

from discord import Embed
from models.nia.required_score_from_img.result import NiaRequiredScoreFromImgResult
from config.settings import CHARACTERS

def build_required_score_embed(
    result: NiaRequiredScoreFromImgResult,
    override_pairs: Optional[Iterable[Tuple[str, Any]]] = None,
) -> Embed:
    """
    override_pairs を与えると、そのペアのみを「必要スコア」欄に表示します。
    例: [("SS+ に必要な合計スコア", 102000)]
    未指定なら従来どおり SS/SS+/SSS/SSS+ を並べます。
    """
    embed = Embed(
        title=f"NIA 【{result.mode}】",
        color=CHARACTERS[result.character]["color"],
        description=f"## {result.audition}",
    )

    if result.is_boost_active:
        embed.add_field(
            name="アイドル強化月間適用",
            value=(f"**ほしのきらめき: {result.kirameki}**　\n\u200b"),
            inline=False
        )

    embed.add_field(
        name="キャラクター",
        value="**{character}**　\n\u200b".format(character = CHARACTERS[result.character]["name"]),
        inline=False,
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
            f"**Vo: {result.vo_status} ({result.vo_bonus}%)**　\n"
            f"**Da: {result.da_status} ({result.da_bonus}%)**　\n"
            f"**Vi: {result.vi_status} ({result.vi_bonus}%)**　\n\u200b"
        ),
        inline=False
    )

    embed.add_field(
        name="ファン数",
        value=f"**{result.now_fans}**　\n\u200b",
        inline=False
    )

    # --- 表示内容の組み立て ---
    if override_pairs is not None:
        lines = []
        for name, val in override_pairs:
            lines.append(f"{name}: {val}")
        required_block = "　\n".join(lines) + "　"
    else:
        required_block = (
            f"**SS**: {result.SS_required_score}　\n\u200b"
            f"**SS+**: {result.SS_plus_required_score}　\n\u200b"
            f"**SSS**: {result.SSS_required_score}　\n\u200b"
            f"**SSS+**: {result.SSS_plus_required_score}　\u200b"
        )

    embed.add_field(
        name="必要スコア",
        value=required_block,
        inline=False,
    )

    return embed