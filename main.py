import os
import traceback
from dotenv import load_dotenv
import discord
from discord import Embed, ui
from discord.ext import commands
import asyncio
import importlib
from commands.groups import gkms
from config.server_registry import ServerRegistry
import time
from typing import Hashable
from datetime import datetime
import zoneinfo

# 追加: ロガー
from utils.logger import setup_logging, get_logger, use_log_context
from utils.context import build_ctx_from_interaction

# ===== ユーザー・ブロック機能（main.py側へ移設） =====
# from moderation.blocklist_manager import maybe_block_and_respond
from pathlib import Path
import json
BASE_DIR = Path(__file__).resolve().parent
SERVERS_JSON = str(BASE_DIR / "config" / "servers.json")
registry = ServerRegistry(SERVERS_JSON)

# ====== 起動前準備 ======
load_dotenv()
TOKEN = os.getenv("DISCORD_BOT_TOKEN")
SYNC_MODE = os.getenv("SYNC_MODE", "global").lower()
TEST_GUILD_ID = os.getenv("TEST_GUILD_ID")
DEV_USER_ID = int(os.getenv("DEV_USER_ID", "0") or 0)
ALERT_CHANNEL_ID = int(os.getenv("ALERT_CHANNEL_ID", "0") or 0)

# --- 開発者DMのクールダウン（秒） ---
# .env で上書き可能（例） DEV_DM_COOLDOWN_PER_GUILD=300
DEV_DM_COOLDOWN_PER_GUILD = int(os.getenv("DEV_DM_COOLDOWN_PER_GUILD", "300"))  # 同ギルドから5分
DEV_DM_COOLDOWN_PER_USER  = int(os.getenv("DEV_DM_COOLDOWN_PER_USER",  "180"))  # 同ユーザーから3分
DEV_DM_COOLDOWN_GLOBAL    = int(os.getenv("DEV_DM_COOLDOWN_GLOBAL",    "30"))   # 全体で30秒


_BLOCKLIST_PATH = Path(str(BASE_DIR / "config" / "blocklist.json"))
_blocklist_cache: dict[str, str] = {}
_blocklist_mtime_ns: int = -1

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)


class SimpleRateLimiter:
    def __init__(self):
        self._next_ok: dict[Hashable, float] = {}

    def allow(self, key: Hashable, interval_sec: float) -> bool:
        now = time.monotonic()
        nxt = self._next_ok.get(key, 0.0)
        if now >= nxt:
            self._next_ok[key] = now + interval_sec
            return True
        return False

    def remaining(self, key: Hashable) -> float:
        now = time.monotonic()
        nxt = self._next_ok.get(key, 0.0)
        return max(0.0, nxt - now)

_rate_limiter = SimpleRateLimiter()


def _load_user_blocklist() -> set[str]:
    """
    config/blocklist.json を軽量にホットリロード
    """
    global _blocklist_cache, _blocklist_mtime_ns
    try:
        st = _BLOCKLIST_PATH.stat()
    except FileNotFoundError:
        _blocklist_cache = {}
        _blocklist_mtime_ns = -1
        return _blocklist_cache

    if st.st_mtime_ns == _blocklist_mtime_ns:
        return _blocklist_cache  # 変更なし

    try:
        data = json.loads(_BLOCKLIST_PATH.read_text(encoding="utf-8"))
        # 形式に応じて判定（リストか旧フォーマットか）
        if isinstance(data, dict) and "user_ids" in data:
            # 旧形式サポート
            _blocklist_cache = {str(uid): "このユーザーは制限されています。" for uid in data["user_ids"]}
        elif isinstance(data, list):
            # 新形式: user_id + message
            _blocklist_cache = {str(entry["user_id"]): entry.get("message", "このユーザーは制限されています。") for entry in data}
        else:
            _blocklist_cache = {}
        _blocklist_mtime_ns = st.st_mtime_ns
        log.info("Blocklist loaded: %d users", len(_blocklist_cache))
    
    except Exception as e:
        log.warning("blocklist load failed: %s", e)
        _blocklist_cache = {}
        _blocklist_mtime_ns = st.st_mtime_ns
    return _blocklist_cache

def _get_user_block_message(user_id: int | str) -> str | None:
    """
    ブロックされていればメッセージを返す
    """
    bl = _load_user_blocklist()
    return bl.get(str(user_id))


async def _notify_dev_about_block(reason: str, interaction: discord.Interaction) -> None:
    """
    未登録/停止/DM実行を検知した際の開発者通知。
    レートリミットでスパム防止＋DM失敗時はフォールバック投稿。
    """
    # --- レートリミット（順に締める） ---
    if not _rate_limiter.allow(("devdm:global", "any"), DEV_DM_COOLDOWN_GLOBAL):
        log.debug("Skip dev DM (global cooldown active)")
        return

    g = interaction.guild
    u = interaction.user
    ch = interaction.channel
    gid = getattr(g, "id", None)
    uid = getattr(u, "id", None)

    if gid is not None and not _rate_limiter.allow(("devdm:guild", gid), DEV_DM_COOLDOWN_PER_GUILD):
        log.debug("Skip dev DM (guild cooldown active) gid=%s", gid)
        return
    if uid is not None and not _rate_limiter.allow(("devdm:user", uid), DEV_DM_COOLDOWN_PER_USER):
        log.debug("Skip dev DM (user cooldown active) uid=%s", uid)
        return

    # --- ENVチェック（重複を1つに整理） ---
    if not DEV_USER_ID:
        log.warning("DEV_USER_ID is not set; skip developer DM.")
        return

    # --- 表示内容を作成（JST表記） ---
    JST = zoneinfo.ZoneInfo("Asia/Tokyo")
    now_jst = datetime.now(JST)
    ts = now_jst.strftime("%Y-%m-%d %H:%M:%S JST")
    cmd = getattr(getattr(interaction, "command", None), "qualified_name", None)

    lines = [
        f"# 【Bot警告】",
        f"### 未許可実行を検知__（{reason}）__",
        f"### 時刻: ",
        f"**{ts}**",
        f"### コマンド: ",
        f"</{cmd}:1417467125567848458>",
        f"### 実行者: ",
        f"**__`{getattr(interaction.user, 'name', None)}`__ ({getattr(interaction.user, 'id', None)})**",
        f"### サーバー: ",
        f"**__{getattr(g, 'name', '(DM/不明)')}__ ({getattr(g, 'id', None)})**",
        f"### チャンネル: ",
        f"**{getattr(ch, 'name', None)} ({getattr(ch, 'id', None)})**",
    ]
    content = "\n".join(lines)

    # 送信する埋め込みメッセージを構築
    view = ui.LayoutView()
    container = ui.Container(accent_color=0xE53935)
    container.add_item(ui.TextDisplay(content))
    view.add_item(container)

    # --- 開発者へDM（本文も付けて安定化） ---
    try:
        dev_user = bot.get_user(DEV_USER_ID) or await bot.fetch_user(DEV_USER_ID)
        if not dev_user:
            raise RuntimeError("developer user not found")
        dm = dev_user.dm_channel or await dev_user.create_dm()
        await dm.send(content=" ", view=view)  # ← ここを content 同梱に変更
        log.info("Developer DM sent for blocked use (%s).", reason)
        return
    except Exception:
        log.error("Failed to DM developer for blocked use.", exc_info=True)

    # --- フォールバック投稿（本文をそのまま再利用） ---
    if ALERT_CHANNEL_ID:
        try:
            alert_ch = bot.get_channel(ALERT_CHANNEL_ID)
            if alert_ch:
                await alert_ch.send(content)
                log.info("Alert posted to ALERT_CHANNEL_ID as fallback.")
        except Exception:
            log.error("Failed to post to alert channel as fallback.", exc_info=True)


# ====== スラッシュ用チェックの実装（トップレベルに一つだけ配置） ======
async def _slash_server_check_impl(interaction: discord.Interaction) -> bool:
    log.debug("slash_server_check called: guild=%s id=%s user=%s cmd=%s",
              getattr(interaction.guild, "name", None),
              getattr(interaction.guild, "id", None),
              getattr(interaction.user, "id", None),
              getattr(getattr(interaction, "command", None), "qualified_name", None))

    # 1) ユーザー単位ブロック
    user_id = getattr(interaction.user, "id", None)
    if user_id is not None:
        block_msg = _get_user_block_message(user_id)
        if block_msg:
            asyncio.create_task(_notify_dev_about_block("user_blocked", interaction))
            
            try:
                embed = Embed(color=0xE74C3C, description=f"{block_msg}")
                await interaction.response.send_message(embed=embed, ephemeral=False)
            
            except Exception:
                log.debug("Failed to respond for user-blocked case", exc_info=True)
            log.info("Blocked (user): user_id=%s name=%s", user_id, getattr(interaction.user, "display_name", None))
            
            return False

    # 2) DM不可
    guild = interaction.guild
    guild_id = getattr(guild, "id", None)
    guild_name = getattr(guild, "name", "(DMまたは不明)")
    user = interaction.user
    user_name = getattr(user, "display_name", "不明")

    if guild_id is None:
        asyncio.create_task(_notify_dev_about_block("dm", interaction))
        try:
            embed = Embed(
                color=0xFF9900,
                description="### このコマンドはサーバー内でのみ使用できます"
            )
            await interaction.response.send_message(
                embed=embed,
                ephemeral=False
            )
        except Exception:
            log.debug("Failed to respond (already responded) for DM-case", exc_info=True)
        return False

    # 3) 未登録
    if not await registry.is_registered(guild_id):
        log.info("Blocked: unregistered guild %s(%s) user %s (%s)", guild_name, guild_id, user_name, user)

        # 開発者へ非同期で通知
        asyncio.create_task(_notify_dev_about_block("unregistered", interaction))

        try:
            embed = Embed(
                color=0xE53935,
                description=f"# ⚠️ このサーバーはまだ登録されていません。\n### 導入をご希望の場合は、運営までご連絡ください。"
            )
            await interaction.response.send_message(
                embed=embed,
                ephemeral=False
            )
        except Exception:
            log.debug("Failed to respond for unregistered case (already responded?)", exc_info=True)
        return False

    # 4) revoked（停止中）
    if await registry.is_revoked(guild_id):
        log.info("Blocked: revoked guild %s(%s)", guild_name, guild_id)
        asyncio.create_task(_notify_dev_about_block("revoked", interaction))

        try:
            embed = Embed(
                color=0xE53935,
                description="### 🚫 このサーバーでは現在Botの利用が停止されています。運営までお問い合わせください。"
            )
            await interaction.response.send_message(
                embed=embed,
                ephemeral=False
            )
        except Exception:
            log.debug("Failed to respond for revoked case (already responded?)", exc_info=True)
        return False

    # 5) 許可
    return True


MODULES = [
    "commands.nia_commands.final_grade.ui",
    "commands.nia_commands.final_grade_from_img.ui",
    "commands.nia_commands.get_final_status.ui",
    "commands.nia_commands.required_score.ui",
    "commands.nia_commands.required_score_from_img.ui",
    "commands.help_command.ui",
    "commands.hajime_commands.final_grade.ui",
    "commands.hajime_commands.required_score.ui",
    "commands.hajime_commands.required_score_from_img.ui",
    # "commands.dev.test_component_v2"
]

# 追加: ログ初期化（本番も開発もこれでOK）
setup_logging(
    name="gakumasu_bot",
    log_dir="logs",
    console_level=discord.utils.MISSING and None or  # 何もしないダミー：そのまま残してOK
    __import__("logging").INFO,
    file_level=__import__("logging").DEBUG,
    split_error_file=True,
    use_json=False,     # JSONログにしたいときは True
    rotation="time",    # Raspberry Piで容量基準にしたいなら "size"
    backup_days=30,
)
log = get_logger()


# ====== スラッシュコマンド登録 ======
@bot.event
async def setup_hook():
    try:
        bot.tree.add_command(gkms)
        for m in MODULES:
            importlib.import_module(m)
        log.info("Command tree prepared (groups added, modules imported)")

        # ツリーの中身をDEBUGで詳細記録（開発時に便利）
        from discord import app_commands
        try:
            cmds = bot.tree.get_commands()
            log.debug("Top-level cmds=%d", len(cmds))
            # gkms直下の構成（存在すれば）
            nia_grp = next(
                (c for c in gkms.commands
                 if isinstance(c, app_commands.Group) and c.name == "nia"),
                None
            )
            if nia_grp:
                log.debug("gkms.nia subcmds=%s", [c.name for c in nia_grp.commands])
        except Exception:
            log.debug("Command tree introspection failed", exc_info=True)

        log.info("Slash command registration scheduled")

        # --- ここに追加（setup_hook 内） ---
        # 確実にスラッシュコマンドの実行前チェックを Tree に登録する
        # 実際のチェック実装は下で定義しますが、ここで add_check を呼ぶと確実に動きます
        bot.tree.interaction_check = _slash_server_check_impl
        log.info("Assigned global slash server check to command tree (via interaction_check)")

    except Exception:
        log.error("setup_hook failed:\n%s", traceback.format_exc())

@bot.event
async def on_ready():
    log.info("✅ Logged in as %s (%s)", bot.user, bot.user.id if bot.user else "unknown")
    try:
        if SYNC_MODE == "guild" and TEST_GUILD_ID:
            synced = await bot.tree.sync(guild=discord.Object(id=int(TEST_GUILD_ID)))
            log.info("🔄 Synced %d commands to guild %s", len(synced), TEST_GUILD_ID)
        else:
            synced = await bot.tree.sync()
            log.info("🔄 Synced %d commands globally", len(synced))
    except Exception:
        log.error("Command sync failed:\n%s", traceback.format_exc())

# ====== 運用で役立つ基本イベント ======
@bot.event
async def on_disconnect():
    # 正常切断(コード1000)も来るためINFOでもOK。頻度を見るならINFO、異常検知寄りならWARNING。
    log.info("WebSocket disconnected (will auto-reconnect)")

@bot.event
async def on_resumed():
    log.info("WebSocket session resumed")

@bot.event
async def on_error(event, *args, **kwargs):
    # 想定外例外の最終受け皿
    log.error("on_error event=%s\n%s", event, traceback.format_exc())

# Prefixコマンド（!sync）用のエラー・完了ログ
@bot.event
async def on_command_error(ctx, error):
    log.warning(
        "Prefix command error: cmd=%s user=%s(%s) guild=%s(%s) err=%s",
        getattr(ctx.command, "qualified_name", None),
        getattr(ctx.author, "name", None), getattr(ctx.author, "id", None),
        getattr(ctx.guild, "name", None), getattr(ctx.guild, "id", None),
        repr(error)
    )

@bot.event
async def on_command_completion(ctx):
    log.info(
        "Prefix command done: cmd=%s user=%s(%s) guild=%s(%s)",
        getattr(ctx.command, "qualified_name", None),
        getattr(ctx.author, "name", None), getattr(ctx.author, "id", None),
        getattr(ctx.guild, "name", None), getattr(ctx.guild, "id", None),
    )

# ====== スラッシュ（app_commands）共通エラーハンドラ ======
@bot.tree.error
async def on_app_command_error(interaction: discord.Interaction, error):
    # ここで全slashコマンドの例外を一括ロギング（ctx 付与で guild/user も自動記録）
    cmd = getattr(getattr(interaction, "command", None), "qualified_name", None)
    ctx = await build_ctx_from_interaction(interaction)
    with use_log_context(ctx):
        log.warning("Slash command error: cmd=%s err=%s", cmd, repr(error))

# 任意：成功時の共通ログ（頻度が多ければINFO→DEBUG推奨）
# discord.pyに汎用のcompletionイベントがないため、各コマンド側で logger を使うのが確実です。

# ====== 管理用コマンド ======
@bot.command()
async def sync(ctx):
    synced = await bot.tree.sync()
    await ctx.send(f"✅ Synced {len(synced)} commands")
    log.info("Manual sync invoked by %s(%s) in guild %s(%s): %d commands",
             getattr(ctx.author, "name", None), getattr(ctx.author, "id", None),
             getattr(ctx.guild, "name", None), getattr(ctx.guild, "id", None),
             len(synced))

bot.run(TOKEN)
