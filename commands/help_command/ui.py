# command/help_command/ui.py

from discord import Interaction, app_commands

from commands.groups import gkms

from .command import HelpCommand


@gkms.command(name="help", description="各コマンドのマニュアルを表示します")

@app_commands.describe(
    検索="マニュアル検索"
)

@app_commands.choices(
    検索=[
        app_commands.Choice(name="使い方の基本", value="basics"),
        app_commands.Choice(name="コマンド一覧", value="commands"),
        app_commands.Choice(name="任意引数について", value="optional_args"),
        app_commands.Choice(name="読み込みエラー時の対処法", value="ocr_fix"),
        app_commands.Choice(name="画像ログについて", value="image_logs")
    ]
)

async def help_command(interaction: Interaction, 検索: str | None = None,):
    await HelpCommand(interaction).execute(検索)