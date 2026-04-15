# final_grade/container_builder.py
from typing import Iterable, Tuple, Any, Optional
from pathlib import Path

from discord import ui
from models.nia.final_grade.result import NiaFinalGradeResult
from config.nia_settings import NIA
from config.settings import CHARACTERS

def build_final_grade_container(
    result: NiaFinalGradeResult,
) -> ui.Container:
    # 埋め込みカラーの設定
    character_color = CHARACTERS[result.character]["color"]

    # キャラクターの設定
    character_name = CHARACTERS[result.character]["name"]

    # 難易度 / オーディションの設定
    mode_name = NIA[result.mode]["name"]
    audition_name = NIA[result.mode][result.audition]["name"]
    
    # きらめきの設定
    if result.is_boost_active:
        kirameki_block = "### アイドル強化月間適用\n**ほしのきらめき: {v}**\n".format(v=result.kirameki)
    else:
        kirameki_block = ""

    # チャレンジPアイテムの表記設定
    if result.challenge_P_item != 40:
        p_item_block = f"\n### チャレンジPアイテム変更\n**{result.challenge_P_item}%**\n"
    else:
        p_item_block = ""

    # テキストテンプレートの読み込み
    tpl_path = Path(__file__).with_name("template.md")
    text_template = tpl_path.read_text(encoding="utf-8")

    # テキストテンプレートに情報を入力
    content = text_template.format(
        # 難易度 / オーディション / 強化月間 / キャラクター / Pアイテム変更
        mode            = mode_name,
        audition        = audition_name,
        option_kirameki = kirameki_block,
        character       = character_name,
        option_P_item   = p_item_block,

        # 最終スコア / 最終評価
        final_score     = result.final_score,
        final_grade     = result.final_grade,

        # オーディションスコア
        sum_score       = result.vo_score + result.da_score + result.vi_score,
        vo_score        = result.vo_score,
        da_score        = result.da_score,
        vi_score        = result.vi_score,

        # パラメータ / パラメータボーナス
        vo_status       = result.vo_status,
        da_status       = result.da_status,
        vi_status       = result.vi_status,

        get_vo_status   = result.get_vo_status,
        get_da_status   = result.get_da_status,
        get_vi_status   = result.get_vi_status,

        final_vo_status = result.final_vo_status,
        final_da_status = result.final_da_status,
        final_vi_status = result.final_vi_status,

        vo_bonus        = result.vo_bonus,
        da_bonus        = result.da_bonus,
        vi_bonus        = result.vi_bonus,

        # ファン数
        now_fans        = result.now_fans,
        get_fans        = result.get_fans,
        final_fans      = result.final_fans
    )

    # 埋め込みを作成して返す
    container = ui.Container(accent_color=character_color)
    container.add_item(ui.TextDisplay(content=content))
    return container