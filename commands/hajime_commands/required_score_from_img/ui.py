# required_score_from_img/ui.py
from typing import Optional
import discord
from discord import Interaction, app_commands
from models.hajime.required_score_from_img.params import HajimeRequiredScoreFromImgParams
from config.settings import NIA, CHARACTERS
from .command import HajimeRequiredScoreFromImgCommand
from commands.groups import hajime

@hajime.command(
    name="required_score_from_img",
    description="目標評価ランク/スコアに必要な最終試験スコアを画像から計算します",
)

@app_commands.describe(
    キャラクター="キャラクターを選択",
    難易度="シナリオの難易度を選択",
    スケジュール画面="P手帳 スケジュール画面のスクリーンショット",
    中間試験スコア画面="中間試験のスコアログ画面",
    vo試験終了時アビ="Voの試験終了時に上昇するパラメータを入力",
    da試験終了時アビ="Daの試験終了時に上昇するパラメータを入力",
    vi試験終了時アビ="Viの試験終了時に上昇するパラメータを入力",
    # 編成画面="P手帳 編成画面のスクリーンショット",
    目標評価ランク="目標評価ランクの設定",
    目標スコア="目標スコアの設定",
    # チャレンジアイテム="チャレンジアイテム倍率の変更",
    # アイドル強化月間="アイドル強化月間を適用しますか？",
    画像ログ="ご協力いただける場合はTrueを選んでください（入力画像を保存し、30日後に自動削除されます）"
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
    目標評価ランク=[
        app_commands.Choice(name="SS", value="SS"),
        app_commands.Choice(name="SS+", value="SS+"),
        app_commands.Choice(name="SSS", value="SSS"),
        app_commands.Choice(name="SSS+", value="SSS+")
    ]
)

async def nia_required_score_from_img_command(
    interaction: Interaction,
    難易度: app_commands.Choice[str],
    スケジュール画面: discord.Attachment,
    中間試験スコア画面: discord.Attachment,
    vo試験終了時アビ: app_commands.Range[int, 0] = 0,
    da試験終了時アビ: app_commands.Range[int, 0] = 0,
    vi試験終了時アビ: app_commands.Range[int, 0] = 0,
    # 編成画面: discord.Attachment,
    目標評価ランク: Optional[str] = None,
    目標スコア: Optional[app_commands.Range[int, 0]] = None,
    キャラクター: Optional[str] = None,
    # チャレンジアイテム: app_commands.Range[int, 0, 40] = NIA["master"]["challenge_bonus_max"],
    # アイドル強化月間: bool = False,
    画像ログ: bool = False
):
    # Params組み立て
    params = HajimeRequiredScoreFromImgParams(
        mode              = 難易度.value,
        vo_ability        = vo試験終了時アビ,
        da_ability        = da試験終了時アビ,
        vi_ability        = vi試験終了時アビ,
        schedule_img      = スケジュール画面,
        score_img         = 中間試験スコア画面,
        character         = キャラクター,
        # is_boost_active = アイドル強化月間,
        is_boost_active   = False,
        # party_img       = 編成画面,
        party_img         = None,
        target_grade      = 目標評価ランク,
        target_score      = 目標スコア,
        save_agree        = 画像ログ
    )

    # コマンド処理
    await HajimeRequiredScoreFromImgCommand(interaction).execute(params)