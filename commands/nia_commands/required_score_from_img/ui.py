# required_score_from_img/ui.py
from typing import Optional
import discord
from discord import Interaction, app_commands
from models.nia.required_score_from_img.params import NiaRequiredScoreFromImgParams
from config.settings import NIA, CHARACTERS
from .command import NiaRequiredScoreFromImgCommand
from commands.groups import nia

@nia.command(
    name="required_score_from_img",
    description="目標評価ランク/スコアに必要なオーディションスコアを画像から計算します",
)

@app_commands.describe(
    キャラクター="キャラクターを選択",
    難易度="シナリオの難易度を選択",
    オーディション="最終オーディションの種類を選択",
    スケジュール画面="P手帳 スケジュール画面のスクリーンショット",
    編成画面="P手帳 編成画面のスクリーンショット",
    目標評価ランク="目標評価ランクの設定",
    目標スコア="目標スコアの設定",
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

@app_commands.choices(
    目標評価ランク=[
        app_commands.Choice(name="SS", value="SS"),
        app_commands.Choice(name="SS+", value="SS+"),
        app_commands.Choice(name="SSS", value="SSS"),
        app_commands.Choice(name="SSS+", value="SSS+")
    ]
)

async def nia_required_score_from_img_command(
    interaction: Interaction,
    キャラクター: app_commands.Choice[str],
    難易度: app_commands.Choice[str],
    オーディション: app_commands.Choice[str],
    スケジュール画面: discord.Attachment,
    編成画面: discord.Attachment,
    目標評価ランク: Optional[str] = None,
    目標スコア: Optional[app_commands.Range[int, 0]] = None,
    チャレンジアイテム: app_commands.Range[int, 0] = NIA["master"]["challenge_bonus_max"],
    アイドル強化月間: bool = False,
    画像保存: bool | None = None,
):
    # Params組み立て
    params = NiaRequiredScoreFromImgParams(
        character=キャラクター.value,
        mode=難易度.value,
        audition=オーディション.value,
        schedule_img=スケジュール画面,
        party_img=編成画面,
        target_grade=目標評価ランク,
        target_score=目標スコア,
        challenge_P_item=チャレンジアイテム,
        is_boost_active=アイドル強化月間,
        image_save_consent=画像保存,
    )

    # コマンド処理
    await NiaRequiredScoreFromImgCommand(interaction).execute(params)
