# hif_commands/final_grade/ui.py


from discord import Interaction, app_commands

from commands.groups import hif
from config.character_settings import CHARACTERS
from config.hif_settings import HIF
from models.hif.final_grade.params import HifFinalGradeParams

from .command import HifFinalGradeCommand

st_max = HIF['default']['st_max']
star_before_round2_max = HIF["default"]["star_max"]["before_round2"]

@hif.command(
    name="final_grade",
    description="最終評価を計算します",
)

@app_commands.describe(
    voパラメータ="Voパラメータ",
    daパラメータ="Daパラメータ",
    viパラメータ="Viパラメータ",
    ラウンド1スコア='ラウンド1の補正"前"スコア',
    ラウンド2スコア="ラウンド2のスコア",
    スター性='ラウンド2"直前"のスター性',
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


async def hif_final_grade_command(
    interaction: Interaction,
    voパラメータ: app_commands.Range[int, 0, st_max],
    daパラメータ: app_commands.Range[int, 0, st_max],
    viパラメータ: app_commands.Range[int, 0, st_max],
    ラウンド1スコア: app_commands.Range[int, 0],
    ラウンド2スコア: app_commands.Range[int, 0],
    スター性: app_commands.Range[int, 0, star_before_round2_max],
    vo試験終了時アビ: app_commands.Range[int, 0] = 0,
    da試験終了時アビ: app_commands.Range[int, 0] = 0,
    vi試験終了時アビ: app_commands.Range[int, 0] = 0,
    キャラクター: str | None = None,
    # アイドル強化月間: bool = False,
    # ほしのきらめき: int = 0
):
    # Params組み立て
    params = HifFinalGradeParams(
        mode = "default",
        vo_status  = voパラメータ,
        da_status  = daパラメータ,
        vi_status  = viパラメータ,
        vo_ability = vo試験終了時アビ,
        da_ability = da試験終了時アビ,
        vi_ability = vi試験終了時アビ,
        round1_score = ラウンド1スコア,
        round2_score = ラウンド2スコア,
        star_before_round2 = スター性,
        # is_boost_active = アイドル強化月間,
        # kirameki = ほしのきらめき,
        is_boost_active = False,
        kirameki        = 0,
        character  = キャラクター
    )

    # コマンド処理
    await HifFinalGradeCommand(interaction).execute(params)