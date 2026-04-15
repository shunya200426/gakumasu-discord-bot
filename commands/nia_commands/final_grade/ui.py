from discord import Interaction, app_commands
from models.nia.final_grade.params import NiaFinalGradeParams
from config.settings import NIA, CHARACTERS
from .command import NiaFinalGradeCommand
from commands.groups import nia

@nia.command(
    name="final_grade",
    description="最終評価を計算します",
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
    voスコア="Voのオーディションスコア",
    daスコア="Daのオーディションスコア",
    viスコア="Viのオーディションスコア",
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

async def nia_final_grade_command(
    interaction: Interaction,
    キャラクター: app_commands.Choice[str],
    難易度: app_commands.Choice[str],
    オーディション: app_commands.Choice[str],
    voパラメータ: int,
    daパラメータ: int,
    viパラメータ: int,
    voパラメータボーナス: float,
    daパラメータボーナス: float,
    viパラメータボーナス: float,
    ファン数: int,
    voスコア: int,
    daスコア: int,
    viスコア: int,
    チャレンジアイテム: int = NIA["master"]["challenge_bonus_max"],
    アイドル強化月間: bool = False,
    ほしのきらめき: int = 0
):
    # Params組み立て
    params = NiaFinalGradeParams(
        character=キャラクター.value,
        mode=難易度.value,
        audition=オーディション.value,
        vo_status=voパラメータ,
        da_status=daパラメータ,
        vi_status=viパラメータ,
        vo_bonus=voパラメータボーナス,
        da_bonus=daパラメータボーナス,
        vi_bonus=viパラメータボーナス,
        vo_score=voスコア,
        da_score=daスコア,
        vi_score=viスコア,
        now_fans=ファン数,
        challenge_P_item=チャレンジアイテム,
        is_boost_active=アイドル強化月間,
        kirameki=ほしのきらめき
    )

    # コマンド処理
    await NiaFinalGradeCommand(interaction).execute(params)