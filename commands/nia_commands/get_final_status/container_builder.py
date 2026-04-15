from pathlib import Path

from discord import ui
from models.nia.get_final_status.result import NiaGetFinalStatusResult
from config.nia_settings import NIA
from config.settings import CHARACTERS

def build_get_final_status_container(result: NiaGetFinalStatusResult) -> ui.Container:
    # 埋め込みカラーの設定
    character_color = CHARACTERS[result.character]["color"]

    # キャラクターの設定
    character_name = CHARACTERS[result.character]["name"]

    # 難易度の設定
    mode_name = NIA[result.mode]["name"]

    # チャレンジPアイテムの表記設定
    if result.challenge_P_item != 40:
        p_item_block = f"\n## チャレンジPアイテム変更 **{result.challenge_P_item}%**\n"
    else:
        p_item_block = ""
    
    # テキストテンプレートの読み込み
    tpl_path = Path(__file__).with_name("template.md")
    text_template = tpl_path.read_text(encoding="utf-8")
    parts = text_template.split("---SEPARATE---")

    # 埋め込み作成
    container = ui.Container(accent_color=character_color)
    content = parts[0].format(
        mode            = mode_name,
        character       = character_name,
        option_P_item   = p_item_block,
    )
    container.add_item(ui.TextDisplay(content))

    for audition in result.audition_dict.keys():
        container.add_item(ui.Separator())
        audition_name = NIA[result.mode][audition]["name"]

        # 各パラメータのオーバーラインの算出
        get_vo_status = result.audition_dict[audition][0]
        get_da_status = result.audition_dict[audition][1]
        get_vi_status = result.audition_dict[audition][2]

        vo_over_line = result.max_status - get_vo_status
        da_over_line = result.max_status - get_da_status
        vi_over_line = result.max_status - get_vi_status

        content = parts[1].format(
            audition        = audition_name,
            vo_bonus        = result.vo_bonus,
            da_bonus        = result.da_bonus,
            vi_bonus        = result.vi_bonus,
            get_vo_status   = get_vo_status,
            get_da_status   = get_da_status,
            get_vi_status   = get_vi_status,
            vo_over_line    = vo_over_line,
            da_over_line    = da_over_line,
            vi_over_line    = vi_over_line,
            max_status      = result.max_status
        )
        container.add_item(ui.TextDisplay(content))

    return container