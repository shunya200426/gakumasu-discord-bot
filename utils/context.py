import discord
from config.server_registry import ServerRegistry
from pathlib import Path
import logging

log = logging.getLogger("gakumasu_bot")

_HERE = Path(__file__).resolve()
_DEFAULT = _HERE.parents[1] / "config" / "servers.json"
_FALLBACK = Path("servers.json")
_PATH = _DEFAULT if _DEFAULT.exists() else _FALLBACK
REGISTRY = ServerRegistry(_PATH)
log.info("ServerRegistry path resolved: %s (exists=%s)", _PATH, _PATH.exists())

async def build_ctx_from_interaction(interaction: discord.Interaction) -> dict:
    """
    INFO/ERROR ログに自動付与させるための文脈(dict)を構築
    """
    g = getattr(interaction, "guild", None)
    u = getattr(interaction, "user", None)
    gid = getattr(g, "id", None)
    gname = getattr(g, "name", "(DM)") or "(DM)"
    # circle_name は後で受動リロード版に差し替え予定。まずは未登録扱いでOK。
    try:
        circle = await REGISTRY.circle_name(gid)  # async 実装前なら同期版に置き換え可
    except Exception:
        circle = "(unregistered)"
    uid = getattr(u, "id", None)
    uname = getattr(u, "display_name", None) or getattr(u, "global_name", None) or getattr(u, "name", None) or "(unknown)"
    return {
        "guild_name": gname,
        "guild_id": str(gid) if gid else "-",
        "circle_name": circle,
        "user": u,
        "user_name": uname,
        "user_id": str(uid) if uid else "-",
    }