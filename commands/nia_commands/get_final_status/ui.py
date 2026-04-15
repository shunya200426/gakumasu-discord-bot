from discord import Interaction, app_commands
from models.nia.get_final_status.params import NiaGetFinalStatusParams
from config.settings import NIA, CHARACTERS
from .command import NiaGetFinalStarusCommand
from commands.groups import nia

@nia.command(
    name="get_final_parameters",
    description="最終オーディションで獲得する最大パラメータを計算します",
)

@app_commands.describe(
    キャラクター="キャラクターを選択",
    難易度="シナリオの難易度を選択",
    voパラメータボーナス="Voパラメータボーナス",
    daパラメータボーナス="Daパラメータボーナス",
    viパラメータボーナス="Viパラメータボーナス",
    オーディション="最終オーディションの種類を選択",
    チャレンジアイテム="チャレンジアイテム倍率の変更",
    オーバーライン="オーバーラインを設定できます"
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
        app_commands.Choice(name="IDOLBigup!", value="idol_bigup!"),
        app_commands.Choice(name="ALL", value="all")
    ]
)

async def nia_get_final_parameters_command(
    interaction: Interaction,
    キャラクター: app_commands.Choice[str],
    難易度: app_commands.Choice[str],
    voパラメータボーナス: float,
    daパラメータボーナス: float,
    viパラメータボーナス: float,
    オーディション: app_commands.Choice[str] = None,
    チャレンジアイテム: int = NIA["master"]["challenge_bonus_max"],
    オーバーライン: app_commands.Range[int, 0, 2600] = None
):
    if オーディション is None:
        audition_value = "finale"
    else:
        audition_value = オーディション.value

    audition_dict = {}
    audition_dict["finale"] = None  # オーディションの種類をまとめるリスト
    
    if audition_value == "finale":
        pass

    elif audition_value == "all":
        audition_dict["quartet"] = None
        audition_dict["idol_bigup!"] = None

    else:
        audition_dict[audition_value] = None

    # Params組み立て
    params = NiaGetFinalStatusParams(
        character=キャラクター.value,
        mode=難易度.value,
        audition_dict=audition_dict,
        vo_bonus=voパラメータボーナス,
        da_bonus=daパラメータボーナス,
        vi_bonus=viパラメータボーナス,
        challenge_P_item=チャレンジアイテム,
        set_over_line=オーバーライン
    )

    # コマンド処理
    await NiaGetFinalStarusCommand(interaction).execute(params)