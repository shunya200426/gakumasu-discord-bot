# gakumasu_bot/moderation/blocklist_manager.py
from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
import json
import discord
from typing import Dict, Optional, Any
from utils.logger import get_logger
logger = get_logger()

_BLOCKLIST_JSON = Path(__file__).with_name("blocklist.json")
_ALLOWED_MD_ROOT = Path(__file__).resolve().parent.joinpath("resources").resolve()
_DEFAULT_MD = _ALLOWED_MD_ROOT.joinpath("blocks/default.md")

@dataclass(frozen=True)
class BlockEntry:
    user_id: int
    md_path: Path
    accent_color: discord.Color
    ephemeral: bool

class BlocklistManager:
    def __init__(self, json_path: Path = _BLOCKLIST_JSON, allowed_root: Path = _ALLOWED_MD_ROOT):
        self.json_path = json_path
        self.allowed_root = allowed_root
        self._cache: Dict[int, BlockEntry] = {}
        self._mtime: float = 0.0

    def _parse_color(self, v: Any) -> discord.Color:
        """
        "#RRGGBB" or int を discord.Color に変換
        """
        if isinstance(v, int):
            return discord.Color(v)
        
        if isinstance(v, str):
            s = v.strip()
            if s.startswith("#"):
                s = s[1:]
            if s.lower().startswith("0x"):
                s = s[2:]

            try:
                return discord.Color(int(s, 16))
            except ValueError:
                pass

        return discord.Color.red()

    def _resolve_md_path(self, raw: str) -> Path:
        p = Path(raw)
        if not p.is_absolute():
            p = Path(__file__).resolve().parent.joinpath(p)
        p = p.resolve()
        if not str(p).startswith(str(self.allowed_root)):  # allowed_root は resolve 済み
            raise ValueError(f"Markdown path is outside allowed directory: {p}")
        return p

    def _load(self) -> None:
        if not self.json_path.exists():
            self._cache = {}
            self._mtime = 0.0
            return

        mtime = self.json_path.stat().st_mtime
        if mtime == self._mtime:
            return  # 変更なし
            

        data = json.loads(self.json_path.read_text(encoding="utf-8"))
        cache: Dict[int, BlockEntry] = {}

        for item in data:
            try:
                uid = int(item["user_id"])
                md_path = self._resolve_md_path(str(item["message_md"]))
                color = self._parse_color(item.get("accent_color"))
                ephemeral = self._parse_bool(item.get("ephemeral", True))

                # Markdownファイル存在チェック
                if not md_path.exists():
                    md_path = _DEFAULT_MD if _DEFAULT_MD.exists() else md_path

                cache[uid] = BlockEntry(
                    user_id=uid,
                    md_path=md_path,
                    accent_color=color,
                    ephemeral=ephemeral,
                )
            except Exception as e:
                # 壊れたエントリは読み飛ばし（ログは呼び出し側のロガーで）
                # print(f"[blocklist] skip invalid entry: {e}")
                continue

        self._cache = cache
        self._mtime = mtime

    def get(self, user_id: int) -> Optional[BlockEntry]:
        self._load()
        return self._cache.get(user_id)
    
    # 文字列/数値にも頑健なブール変換
    def _parse_bool(self, v: Any, default: bool = True) -> bool:
        if isinstance(v, bool):
            return v
        if v is None:
            return default
        if isinstance(v, (int,)):
            return bool(v)
        if isinstance(v, str):
            s = v.strip().lower()
            if s in {"true", "1", "yes", "y", "on"}:
                return True
            if s in {"false", "0", "no", "n", "off"}:
                return False
        return default


blocklist_manager = BlocklistManager()


def _render_markdown(md_path: Path, interaction: discord.Interaction, ctx: dict[str, str] | None = None) -> str:
    text = md_path.read_text(encoding="utf-8")
    base = {
        "user_mention": interaction.user.mention,
        "user_name": getattr(interaction.user, "display_name", str(interaction.user)),
        "guild_name": getattr(interaction.guild, "name", "DM"),
    }
    if ctx:
        base.update(ctx)
    try:
        return text.format(**base)
    except Exception:
        return text


async def maybe_block_and_respond(
    interaction: discord.Interaction,
    *,
    context: dict[str, str] | None = None,
) -> bool:
    entry = blocklist_manager.get(interaction.user.id)
    if not entry:
        return False

    text = _render_markdown(entry.md_path, interaction, context)
    if len(text) > 4096:
        text = text[:4093] + "..."
    embed = discord.Embed(description=text, color=entry.accent_color)
    try:
        await interaction.response.send_message(embed=embed, ephemeral=entry.ephemeral)
    except discord.InteractionResponded:
        await interaction.followup.send(embed=embed, ephemeral=entry.ephemeral)
    return True
