import discord
from discord import Interaction, app_commands
from models.nia.final_grade_from_img.params import NiaFinalGradeFromImgParams
from config.settings import NIA, CHARACTERS
from .command import NiaFinalGradeFromImgCommand
from commands.groups import nia

@nia.command(
    name="final_grade_from_img",
    description="最終評価を画像から計算します",
)

@app_commands.describe(
    キャラクター="キャラクターを選択",
    難易度="シナリオの難易度を選択",
    オーディション="最終オーディションの種類を選択",
    スケジュール画面="P手帳 スケジュール画面のスクリーンショット",
    編成画面="P手帳 編成画面のスクリーンショット",
    スコア画面="オーディションのスコアログ画面",
    チャレンジアイテム="チャレンジアイテム倍率の変更",
    アイドル強化月間="アイドル強化月間を適用しますか？",
    画像保存=(
        "精度向上用の画像保存設定"
        "（未指定の場合は現在の設定を維持します）"
    ),
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

async def nia_final_grade_from_img_command(
    interaction: Interaction,
    キャラクター: app_commands.Choice[str],
    難易度: app_commands.Choice[str],
    オーディション: app_commands.Choice[str],
    スケジュール画面: discord.Attachment,
    編成画面: discord.Attachment,
    スコア画面: discord.Attachment,
    チャレンジアイテム: int = NIA["master"]["challenge_bonus_max"],
    アイドル強化月間: bool = False,
    画像保存: bool | None = None,
):
    # Params組み立て
    params = NiaFinalGradeFromImgParams(
        character=キャラクター.value,
        mode=難易度.value,
        audition=オーディション.value,
        schedule_img=スケジュール画面,
        party_img=編成画面,
        score_img=スコア画面,
        challenge_P_item=チャレンジアイテム,
        is_boost_active=アイドル強化月間,
        image_save_consent=画像保存,
    )

    # コマンド処理
    await NiaFinalGradeFromImgCommand(interaction).execute(params)
