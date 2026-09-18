# hajime_commands/required_score/ui.py


from discord import Interaction, app_commands

from commands.groups import hajime
from config.character_settings import CHARACTERS
from config.hajime_settings import HAJIME
from models.hajime.required_score.params import HajimeRequiredScoreParams

from .command import HajimeRequiredScoreCommand

ST_MAX = HAJIME['legend']['st_max']

@hajime.command(
    name="required_score",
    description="最終評価を計算します",
)

@app_commands.describe(
    難易度="シナリオの難易度を選択",
    voパラメータ="最終試験前のVoパラメータ",
    daパラメータ="最終試験前のDaパラメータ",
    viパラメータ="最終試験前のViパラメータ",
    中間試験スコア="中間試験のスコア",
    vo試験終了時アビ="Voの試験終了時に上昇するパラメータを入力",
    da試験終了時アビ="Daの試験終了時に上昇するパラメータを入力",
    vi試験終了時アビ="Viの試験終了時に上昇するパラメータを入力",
    目標評価ランク="目標評価ランクの設定",
    目標スコア="目標スコアの設定",
    キャラクター="キャラクターを選択",
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
        # app_commands.Choice(name="レギュラー", value="regular"),
        # app_commands.Choice(name="プロ", value="pro"),
        # app_commands.Choice(name="マスター", value="master"),
        app_commands.Choice(name="レジェンド", value="legend")
    ]
)

@app_commands.choices(
    目標評価ランク=[
        app_commands.Choice(name="SS", value="SS"),
        app_commands.Choice(name="SS+", value="SS+"),
        app_commands.Choice(name="SSS", value="SSS"),
        app_commands.Choice(name="SSS+", value="SSS+")
    ]
)


async def hajime_required_score_command(
    interaction: Interaction,
    難易度: app_commands.Choice[str],
    voパラメータ: app_commands.Range[int, 0, ST_MAX],
    daパラメータ: app_commands.Range[int, 0, ST_MAX],
    viパラメータ: app_commands.Range[int, 0, ST_MAX],
    中間試験スコア: app_commands.Range[int, 0, 200000] = 50000,
    vo試験終了時アビ: app_commands.Range[int, 0] = 0,
    da試験終了時アビ: app_commands.Range[int, 0] = 0,
    vi試験終了時アビ: app_commands.Range[int, 0] = 0,
    目標評価ランク: str | None = None,
    目標スコア: app_commands.Range[int, 0] | None = None,
    キャラクター: str | None = None,
    # アイドル強化月間: bool = False,
    # ほしのきらめき: int = 0
):
    # Params組み立て
    params = HajimeRequiredScoreParams(
        mode            = 難易度.value,
        vo_status       = voパラメータ,
        da_status       = daパラメータ,
        vi_status       = viパラメータ,
        vo_ability      = vo試験終了時アビ,
        da_ability      = da試験終了時アビ,
        vi_ability      = vi試験終了時アビ,
        mid_exam_score  = 中間試験スコア,
        target_grade    = 目標評価ランク,
        target_score    = 目標スコア,
        character       = キャラクター,
        # is_boost_active = アイドル強化月間,
        # kirameki        = ほしのきらめき,
        is_boost_active = False,
        kirameki        = 0,
    )

    # コマンド処理
    await HajimeRequiredScoreCommand(interaction).execute(params)