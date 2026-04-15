# get_final_status/embed_builder.py

from discord import Embed
from models.nia.get_final_status.result import NiaGetFinalStatusResult
from config.settings import CHARACTERS

def build_get_final_status_embed(result: NiaGetFinalStatusResult) -> Embed:
    embed = Embed(
        title=f"NIA 【{result.mode}】",
        color=CHARACTERS[result.character]["color"],
        description=f"## {result.audition}"
    )

    embed.add_field(
        name="キャラクター",
        value=(f"**{CHARACTERS[result.character]['name']}**\n\u200b"),
        inline=False
    )

    if result.challenge_P_item != 40:
        embed.add_field(
            name="チャレンジPアイテム変更",
            value=f"**{result.challenge_P_item}%**\n\u200b",
            inline=False
        )

    embed.add_field(
        name="最大獲得パラメータ",
        value=(
            f"Vo: **+{result.get_vo_status}** （{result.vo_bonus}%）\n"
            f"Da: **+{result.get_da_status}** （{result.da_bonus}%）\n"
            f"Vi: **+{result.get_vi_status}** （{result.vi_bonus}%）\n\u200b"
        ),
        inline=False
    )

    embed.add_field(
        name="オーバーライン",
        value=(
            f"Vo: **{result.max_status} - {result.get_vo_status} = __{result.max_status - result.get_vo_status}__**　\n"
            f"Da: **{result.max_status} - {result.get_da_status} = __{result.max_status - result.get_da_status}__**　\n"
            f"Vi: **{result.max_status} - {result.get_vi_status} = __{result.max_status - result.get_vi_status}__**　"
        ),
        inline=False
    )

    return embed