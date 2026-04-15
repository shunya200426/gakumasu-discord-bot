# hajime_commands/required_score/embed_builder.py
from typing import Iterable, Tuple, Any, Optional
from pathlib import Path
import discord
from discord import ui
from models.hajime.required_score.result import HajimeRequiredScoreResult
from config.hajime_settings import HAJIME
from config.settings import CHARACTERS

def build_required_score_container(
    result: HajimeRequiredScoreResult,
    override_pairs: Optional[Iterable[Tuple[str, Any]]] = None,
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
        
    # 必要スコアの表記設定
    if override_pairs is not None:
        lines = [f"{name}: {val}" for name, val in override_pairs]
        required_block = "　\n".join(lines) + "　"
    else:
        required_block = (
            f"**SS**: {result.SS_required_score}　\n"
            f"**SS+**: {result.SS_plus_required_score}　\n"
            f"**SSS**: {result.SSS_required_score}　\n"
            f"**SSS+**: {result.SSS_plus_required_score}　"
        )

    # テキストテンプレートの読み込み
    tpl_path = Path(__file__).with_name("template.md")
    text_template = tpl_path.read_text(encoding="utf-8")
    
    # テキストテンプレートに情報を入力
    content = text_template.format(
        mode                = mode_name,
        option_kirameki     = kirameki_block,
        option_character    = character_block,
        vo_status           = result.vo_status,
        da_status           = result.da_status,
        vi_status           = result.vi_status,
        vo_ability          = result.vo_ability,
        da_ability          = result.da_ability,
        vi_ability          = result.vi_ability,
        mid_exam_score      = result.mid_exam_score,
        required_block      = required_block
    )
    print("メッセージ構築CLEAR!")
    
    # 埋め込みを作成して返す
    container = ui.Container(accent_color=container_color)
    container.add_item(ui.TextDisplay(content=content))
    return container