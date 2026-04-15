from discord import ui
from commands.base_command import BaseCommand
from .container_builder import build_help_containers 
COMMAND_NAME = "help_command"

class HelpCommand(BaseCommand):
    async def execute(self, search_option):
        self.log_command_start(COMMAND_NAME)

        view = ui.LayoutView()
        for container in build_help_containers(search_option):
            view.add_item(container)

        await self.interaction.response.send_message(view=view)

        self.log_command_end(COMMAND_NAME)