# required_score/ui.py
from typing import Optional
from discord import Interaction, app_commands
from models.nia.required_score.params import NiaRequiredScoreParams
from config.settings import NIA, CHARACTERS
from .command import NiaRequiredScoreCommand
from commands.groups import nia

@nia.command(
    name="required_score",
    description="目標評価ランク/スコアに必要なオーディションスコアを計算します",
)

@app_commands.describe(
    キャラクター="キャラクターを選択",
    難易度="シナリオの難易度を選択",
    オーディション="最終オーディションの種類を選択",
    voパラメータ="オーディション前のVoパラメータ",
    daパラメータ="オーディション前のDaパラメータ",
    viパラメータ="オーディション前のViパラメータ",
    voパラメータボーナス="Voパラメータボーナス",
    daパラメータボーナス="Daパラメータボーナス",
    viパラメータボーナス="Viパラメータボーナス",
    ファン数="オーディション前のファン数",
    目標評価ランク="目標評価ランクの設定",
    目標スコア="目標スコアの設定",
    チャレンジアイテム="チャレンジアイテム倍率の変更",
    アイドル強化月間="アイドル強化月間を適用しますか？",
    ほしのきらめき="オーディション前のほしのきらめきの数"
)

@app_commands.choices(
    キャラクター=[
        app_commands.Choice(name=info["name"], value=key)
        for key, info in CHARACTERS.items()
    ]
)

@app_commands.choices(
    難易度=[
        # app_commands.Choice(name="プロ", value="pro"),
        app_commands.Choice(name="マスター", value="master")
    ]
)

@app_commands.choices(
    オーディション=[
        app_commands.Choice(name="FINALE", value="finale"),
        app_commands.Choice(name="QUARTET", value="quartet"),
        app_commands.Choice(name="IDOLBigup!", value="idol_bigup!")
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

async def nia_required_score_command(
    interaction: Interaction,
    キャラクター: app_commands.Choice[str],
    難易度: app_commands.Choice[str],
    オーディション: app_commands.Choice[str],
    voパラメータ: app_commands.Range[int, 0, 2600],
    daパラメータ: app_commands.Range[int, 0, 2600],
    viパラメータ: app_commands.Range[int, 0, 2600],
    voパラメータボーナス: float,
    daパラメータボーナス: float,
    viパラメータボーナス: float,
    ファン数: app_commands.Range[int, 20000],
    目標評価ランク: Optional[str] = None,
    目標スコア: Optional[app_commands.Range[int, 0]] = None,
    チャレンジアイテム: app_commands.Range[int, 0] = NIA["master"]["challenge_bonus_max"],
    アイドル強化月間: bool = False,
    ほしのきらめき: app_commands.Range[int, 0] = 0
):
    # Params組み立て
    params = NiaRequiredScoreParams(
        character=キャラクター.value,
        mode=難易度.value,
        audition=オーディション.value,
        vo_status=voパラメータ,
        da_status=daパラメータ,
        vi_status=viパラメータ,
        vo_bonus=voパラメータボーナス,
        da_bonus=daパラメータボーナス,
        vi_bonus=viパラメータボーナス,
        now_fans=ファン数,
        target_grade=目標評価ランク,
        target_score=目標スコア,
        challenge_P_item=チャレンジアイテム,
        is_boost_active=アイドル強化月間,
        kirameki=ほしのきらめき
    )

    # コマンド処理
    await NiaRequiredScoreCommand(interaction).execute(params)