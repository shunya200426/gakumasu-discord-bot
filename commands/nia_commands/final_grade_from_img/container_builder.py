from pathlib import Path
from discord import ui

def _fmt_num(v):
    return "__ERROR__ " if v is None else str(v)

def build_error_container(*, params: dict, bonus: dict | None = None, score: dict | None = None, is_boost: bool = False) -> ui.Container:
    # 埋め込みカラーの設定
    color = 0xE67E22
    
    # きらめきの設定
    if is_boost:
        kirameki_block = "\n### アイドル強化月間適用\n**ほしのきらめき: {v}**\n".format(v=_fmt_num(bonus.get('kirameki')))
    else:
        kirameki_block = ""

    # テキストテンプレートの読み込み
    tpl_path = Path(__file__).with_name("err_template.md")
    text_template = tpl_path.read_text(encoding="utf-8")

    # テキストテンプレートに情報を入力
    content = text_template.format(
        option_kirameki = kirameki_block,
        vo_status       = _fmt_num(params.get('vo')),
        da_status       = _fmt_num(params.get('da')),
        vi_status       = _fmt_num(params.get('vi')),
        vo_bonus        = _fmt_num(bonus.get('vo')),
        da_bonus        = _fmt_num(bonus.get('da')),
        vi_bonus        = _fmt_num(bonus.get('vi')),
        vo_score        = _fmt_num(score.get('vo')),
        da_score        = _fmt_num(score.get('da')),
        vi_score        = _fmt_num(score.get('vi')),
        now_fans        = _fmt_num(params.get('fans'))
    )

    # 埋め込みを作成して返す
    container = ui.Container(accent_color=color)
    container.add_item(ui.TextDisplay(content=content))
    return container