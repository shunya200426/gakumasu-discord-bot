# hajime_commands/final_grade/embed_builder.py
from pathlib import Path
import discord
from discord import ui
from models.hajime.final_grade.result import HajimeFinalGradeResult
from config.hajime_settings import HAJIME
from config.settings import CHARACTERS

def build_final_grade_container(
    result: HajimeFinalGradeResult
) -> ui.Container:
    
    # 埋め込みカラーの設定
    # 任意のキャラが選択されている場合は、そのキャラのイメージカラーにする
    if result.character is not None:
        container_color = CHARACTERS[result.character]["color"]
        character_block = f'### キャラクター\n**{CHARACTERS[result.character]["name"]}**'
    else:
        container_color = discord.Color.orange()
        character_block = ''
        
    
    # 難易度の設定
    mode_name = HAJIME[result.mode]["name"]
    
    # きらめきの設定
    if result.is_boost_active:
        kirameki_block = "### アイドル強化月間適用\n**ほしのきらめき: {v}**\n".format(v=result.kirameki)
    else:
        kirameki_block = ""
        
    # 順位の設定
    final_exam_rank = {
        "first": "1位",
        "second": "2位",
        "third": "3位",
        "other": "4位以下",
    }

    # テキストテンプレートの読み込み
    tpl_path = Path(__file__).with_name("template.md")
    text_template = tpl_path.read_text(encoding="utf-8")
    
    # テキストテンプレートに情報を入力
    content = text_template.format(
        mode                = mode_name,
        option_kirameki     = kirameki_block,
        option_character    = character_block,
        final_point         = result.final_point,
        final_grade         = result.final_grade,
        mid_exam_score      = result.mid_exam_score,
        final_exam_rank     = final_exam_rank[result.final_exam_rank],
        final_exam_score    = result.final_exam_score,
        exam_post_bonus     = result.exam_post_bonus,
        vo_status           = result.vo_status,
        da_status           = result.da_status,
        vi_status           = result.vi_status,
        vo_ability          = result.vo_ability,
        da_ability          = result.da_ability,
        vi_ability          = result.vi_ability,
        final_vo_status     = result.final_vo_status,
        final_da_status     = result.final_da_status,
        final_vi_status     = result.final_vi_status
    )
    print("メッセージ構築CLEAR!")
    
    # 埋め込みを作成して返す
    container = ui.Container(accent_color=container_color)
    container.add_item(ui.TextDisplay(content=content))
    return container