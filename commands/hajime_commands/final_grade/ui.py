# hajime_commands/final_grade/ui.py

from typing import Optional
from discord import Interaction, app_commands
from models.hajime.final_grade.params import HajimeFinalGradeParams
from config.settings import CHARACTERS
from .command import HajimeFinalGradeCommand
from commands.groups import hajime

@hajime.command(
    name="final_grade",
    description="最終評価を計算します",
)

@app_commands.describe(
    難易度="シナリオの難易度を選択",
    voパラメータ="最終試験前のVoパラメータ",
    daパラメータ="最終試験前のDaパラメータ",
    viパラメータ="最終試験前のViパラメータ",
    中間試験スコア="中間試験のスコア",
    最終試験スコア="最終試験のスコア",
    順位="最終試験順位",
    vo試験終了時アビ="Voの試験終了時に上昇するパラメータを入力",
    da試験終了時アビ="Daの試験終了時に上昇するパラメータを入力",
    vi試験終了時アビ="Viの試験終了時に上昇するパラメータを入力",
    キャラクター="キャラクターを選択"
    # アイドル強化月間="アイドル強化月間を適用しますか？",
    # ほしのきらめき="オーディション前のほしのきらめきの数"
)

@app_commands.choices(
    キャラクター=[
        app_commands.Choice(name=info["name"], value=key)
        for key, info in CHARACTERS.items()
    ]
)

@app_commands.choices(
    難易度=[
        app_commands.Choice(name="レギュラー", value="regular"),
        app_commands.Choice(name="プロ", value="pro"),
        app_commands.Choice(name="マスター", value="master"),
        app_commands.Choice(name="レジェンド", value="legend")
    ]
)

@app_commands.choices(
    順位=[
        app_commands.Choice(name="1位", value="first"),
        app_commands.Choice(name="2位", value="second"),
        app_commands.Choice(name="3位", value="third"),
        app_commands.Choice(name="4位以下", value="other")
    ]
)


async def nia_final_grade_command(
    interaction: Interaction,
    難易度: app_commands.Choice[str],
    voパラメータ: app_commands.Range[int, 0, 2800],
    daパラメータ: app_commands.Range[int, 0, 2800],
    viパラメータ: app_commands.Range[int, 0, 2800],
    中間試験スコア: app_commands.Range[int, 0],
    最終試験スコア: app_commands.Range[int, 0],
    順位: app_commands.Choice[str],
    vo試験終了時アビ: app_commands.Range[int, 0] = 0,
    da試験終了時アビ: app_commands.Range[int, 0] = 0,
    vi試験終了時アビ: app_commands.Range[int, 0] = 0,
    キャラクター: Optional[str] = None,
    # アイドル強化月間: bool = False,
    # ほしのきらめき: int = 0
):
    # Params組み立て
    params = HajimeFinalGradeParams(
        mode = 難易度.value,
        vo_status  = voパラメータ,
        da_status  = daパラメータ,
        vi_status  = viパラメータ,
        vo_ability = vo試験終了時アビ,
        da_ability = da試験終了時アビ,
        vi_ability = vi試験終了時アビ,
        mid_exam_score  = 中間試験スコア,
        final_exam_score = 最終試験スコア,
        final_exam_rank = 順位.value,
        character  = キャラクター,
        # is_boost_active = アイドル強化月間,
        # kirameki = ほしのきらめき,
        is_boost_active = False,
        kirameki        = 0
    )

    # コマンド処理
    await HajimeFinalGradeCommand(interaction).execute(params)