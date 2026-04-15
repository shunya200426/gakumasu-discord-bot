# commands/groups.py
from discord import app_commands

gkms = app_commands.Group(name="gkms", description="学マス計算")
nia  = app_commands.Group(name="nia",  description="NIAシナリオ", parent=gkms)
hajime = app_commands.Group(name="hajime", description="初", parent=gkms)