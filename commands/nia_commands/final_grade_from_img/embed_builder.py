# final_grade_from_img/embed_builder.py
from discord import Embed


def _fmt_num(v):
    return "__ERROR__ " if v is None else str(v)

def build_error_embed(*, params: dict, bonus: dict | None = None, scores: dict | None = None, is_boost: bool = False) -> Embed:
    """
    OCR読み取りエラー時に、取得できた/できなかった値を1枚のEmbedで俯瞰表示する。
    - params: {"vo", "da", "vi", "fans"}
    - bonus:  {"vo","da","vi"}
    - scores: {"sum_score","vo","da","vi")
    """
    embed = Embed(
        title="パラメータの読み取りに失敗しました",
        description="**読み取り結果の一覧を表示します**",
        color=0xE67E22
    )

    # 強化月間適用時
    if is_boost:
        embed.add_field(
            name="アイドル強化月間適用",
            value=f"ほしのきらめき: **{_fmt_num(bonus.get('kirameki'))}**\n\u200b"
        )

    # パラメータ & ファン数
    embed.add_field(
        name="パラメータ / ファン数",
        value=(
            f"Vo: **{_fmt_num(params.get('vo'))}**\n"
            f"Da: **{_fmt_num(params.get('da'))}**\n"
            f"Vi: **{_fmt_num(params.get('vi'))}**\n"
            f"ファン数: **{_fmt_num(params.get('fans'))}**\n\u200b"
        ),
        inline=False
    )

    embed.add_field(
        name="パラメータボーナス",
        value=(
            f"Vo: **{_fmt_num(bonus.get('vo'))}%**\n"
            f"Da: **{_fmt_num(bonus.get('da'))}%**\n"
            f"Vi: **{_fmt_num(bonus.get('vi'))}%**\n\u200b"
        ),
        inline=False
    )

    embed.add_field(
        name="スコア",
        value=(
            f"Vo: **{_fmt_num(scores.get('vo'))}pt**\n"
            f"Da: **{_fmt_num(scores.get('da'))}pt**\n"
            f"Vi: **{_fmt_num(scores.get('vi'))}pt**\n"
            f"sum: **{_fmt_num(scores.get('sum_score'))}pt**"
        ),
        inline=False
    )

    return embed
