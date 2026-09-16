# Standard library
import importlib

# Third-party
from discord import app_commands
from discord.ext import commands

# Local application
from commands.groups import gkms
from utils.logger import get_logger

log = get_logger()


MODULES = [
    "commands.nia_commands.final_grade.ui",
    "commands.nia_commands.final_grade_from_img.ui",
    "commands.nia_commands.get_final_status.ui",
    "commands.nia_commands.required_score.ui",
    "commands.nia_commands.required_score_from_img.ui",
    "commands.help_command.ui",
    "commands.hajime_commands.final_grade.ui",
    "commands.hajime_commands.final_grade_from_img.ui",
    "commands.hajime_commands.required_score.ui",
    "commands.hajime_commands.required_score_from_img.ui",
]


def register_commands(
    bot: commands.Bot,
) -> None:
    """
    Slash Command関連モジュールを読み込み、
    command treeへ登録する。
    """

    for module_name in MODULES:
        importlib.import_module(
            module_name
        )

    # サブコマンドが追加されたgkmsをTreeへ登録
    bot.tree.add_command(
        gkms
    )

    log.info(
        "Command tree prepared "
        "(groups added, modules imported)"
    )

    # ====== コマンドツリー確認 ======
    try:
        commands_list = (
            bot.tree.get_commands()
        )

        log.debug(
            "Top-level cmds=%d",
            len(commands_list),
        )

        nia_group = next(
            (
                command
                for command in gkms.commands
                if isinstance(
                    command,
                    app_commands.Group,
                )
                and command.name == "nia"
            ),
            None,
        )

        if nia_group:
            log.debug(
                "gkms.nia subcmds=%s",
                [
                    command.name
                    for command
                    in nia_group.commands
                ],
            )

    except Exception:
        log.debug(
            "Command tree introspection failed",
            exc_info=True,
        )

    log.info(
        "Slash command registration scheduled"
    )