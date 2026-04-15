# commands/help_command/container_builder.py
from pathlib import Path
from typing import List
import discord
from discord import ui

BASE = Path(__file__).parent / "md"

def _md(name: str) -> str:
    """
    .mdファイルの読み込み
    """
    return (BASE / name).read_text(encoding="utf-8").strip()


def build_section_basics() -> ui.Container:
    """
    使い方の基本
    """
    basics_md = _md("01_basics.md")
    c = ui.Container(accent_color=0x00AA88)
    c.add_item(ui.TextDisplay(basics_md))
    return c


def build_section_commands() -> ui.Container:
    """
    コマンド一覧
    """
    commands_md = _md("02_commands.md")
    parts = commands_md.split("---IMAGE_BREAK---")
    c = ui.Container(accent_color=0x2B90D9)

    c.add_item(ui.TextDisplay(parts[0]))
    c.add_item(ui.Separator(spacing=discord.SeparatorSpacing.large))

    c.add_item(ui.TextDisplay(parts[1]))
    gallery1 = ui.MediaGallery(
        discord.MediaGalleryItem(
            media="https://media.discordapp.net/attachments/1259854577566617665/1422817540509270097/IMG_9249.png?ex=68de0d98&is=68dcbc18&hm=dd3f2b836772353a6ce5ae58416d44ae372204a824b616a0a69cffb75aa177c6&=&format=webp&quality=lossless&width=399&height=864"
        ),
    )
    c.add_item(gallery1)
    c.add_item(ui.Separator())

    c.add_item(ui.TextDisplay(parts[2]))
    gallery2 = ui.MediaGallery(
        discord.MediaGalleryItem(
            media="https://media.discordapp.net/attachments/1259854577566617665/1422817540861857862/IMG_9250.png?ex=68de0d98&is=68dcbc18&hm=8cd976f018a611d7657afb30fba796fc6afa5840ecddc0cad987cebdb7c1c2a5&=&format=webp&quality=lossless&width=399&height=864"
        ),
    )
    c.add_item(gallery2)
    c.add_item(ui.Separator())

    c.add_item(ui.TextDisplay(parts[3]))
    gallery3 = ui.MediaGallery(
        discord.MediaGalleryItem(
            media="https://media.discordapp.net/attachments/1259854577566617665/1422817541381816340/IMG_9251.png?ex=68de0d98&is=68dcbc18&hm=a131d5c24c70cb713a8bfae4ee52123739f716545aa0c33e5db4c57ccf11d36e&=&format=webp&quality=lossless&width=399&height=864"
        ),
    )
    c.add_item(gallery3)
    c.add_item(ui.Separator())

    c.add_item(ui.TextDisplay(parts[4]))
    return c


def build_section_optional() -> ui.Container:
    """
    任意引数について
    """
    optional_args_md = _md("03_optional_args.md")
    c = ui.Container(accent_color=0x546E7A)
    c.add_item(ui.TextDisplay(optional_args_md))
    return c


def build_section_ocr_fix() -> ui.Container:
    """
    読み込みエラー時の対処法
    """
    ocr_fix_md = _md("04_ocr_fix.md")
    parts = ocr_fix_md.split("---IMAGE_BREAK---")
    c = ui.Container(accent_color=0xFF9900)

    c.add_item(ui.TextDisplay(parts[0]))
    gallery1 = ui.MediaGallery(
        discord.MediaGalleryItem(
            media="https://media.discordapp.net/attachments/1259854577566617665/1422817541687873536/IMG_9269.png?ex=68de0d98&is=68dcbc18&hm=cbdbc6f0ff16ef30fdd2f563e7eb04e9ff2ecac89599c24d080f4b1c03800b4f&=&format=webp&quality=lossless&width=525&height=863"
        ),
    )
    c.add_item(gallery1)
    c.add_item(ui.Separator(visible=False, spacing=discord.SeparatorSpacing.large))
    
    c.add_item(ui.TextDisplay(parts[1]))
    gallery2 = ui.MediaGallery(
        discord.MediaGalleryItem(
            media="https://media.discordapp.net/attachments/1259854577566617665/1423927078910165117/IMG_9270.png?ex=68e216ee&is=68e0c56e&hm=522f99a5d040c59c5205ae054b91d90666725b545f7ba4f80e52a6d7bb77790a&=&format=webp&quality=lossless&width=423&height=752"
        )
    )
    c.add_item(gallery2)
    c.add_item(ui.Separator(visible=False, spacing=discord.SeparatorSpacing.large))

    c.add_item(ui.TextDisplay(parts[2]))
    gallery3 = ui.MediaGallery(
        discord.MediaGalleryItem(
            media="https://media.discordapp.net/attachments/1259854577566617665/1423927079170347070/IMG_9271.png?ex=68e216ee&is=68e0c56e&hm=dcbfaf477d63901e9c33e72c5a7da741397499c722d9e456abf61ee098c6b653&=&format=webp&quality=lossless&width=383&height=753"
        )
    )
    c.add_item(gallery3)
    return c


def build_section_image_logs() -> ui.Container:
    """
    画像ログについて
    """
    image_logs_md = _md("05_image_logs.md")
    c = ui.Container(accent_color=0xE53935)
    c.add_item(ui.TextDisplay(image_logs_md))
    return c


def build_help_containers(search_option) -> List[ui.Container]:
    container_dict: dict = {
        "basics": build_section_basics(),
        "commands": build_section_commands(),
        "optional_args": build_section_optional(),
        "ocr_fix": build_section_ocr_fix(),
        "image_logs": build_section_image_logs(),
    }

    if search_option is None:
        return list(container_dict.values())
    
    else:
        return [container_dict[search_option]]
