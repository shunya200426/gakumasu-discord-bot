import os
import traceback
from dotenv import load_dotenv
import discord
from discord import Embed, ui
from discord.ext import commands
import asyncio
import importlib
from commands.groups import gkms
import time
from typing import Hashable
from datetime import datetime
import zoneinfo
from db.database import DatabaseManager
from utils.logger import setup_logging, get_logger, use_log_context
from utils.context import (
    build_ctx_from_interaction,
    configure_context_repository,
)
from config.paths import YOLO_MODEL_PATH
from inference.yolo_detector import YoloDetector

# ====== 起動前準備 ======
load_dotenv()
TOKEN = os.getenv("DISCORD_BOT_TOKEN")
SYNC_MODE = os.getenv("SYNC_MODE", "global").lower()
TEST_GUILD_ID = os.getenv("TEST_GUILD_ID")
DEV_USER_ID = int(os.getenv("DEV_USER_ID", "0") or 0)
ALERT_CHANNEL_ID = int(os.getenv("ALERT_CHANNEL_ID", "0") or 0)

# ====== DB初期化 ======
db = DatabaseManager()
db.initialize()

if db.guilds is None or db.users is None:
    raise RuntimeError("Repository initialization failed")

guild_repository = db.guilds
user_repository = db.users

configure_context_repository(guild_repository)

# --- 開発者DMのクールダウン（秒） ---
# .env で上書き可能（例） DEV_DM_COOLDOWN_PER_GUILD=300
DEV_DM_COOLDOWN_PER_GUILD = int(os.getenv("DEV_DM_COOLDOWN_PER_GUILD", "300"))  # 同ギルドから5分
DEV_DM_COOLDOWN_PER_USER  = int(os.getenv("DEV_DM_COOLDOWN_PER_USER",  "180"))  # 同ユーザーから3分
DEV_DM_COOLDOWN_GLOBAL    = int(os.getenv("DEV_DM_COOLDOWN_GLOBAL",    "30"))   # 全体で30秒


intents = discord.Intents.default()
intents.message_content = True


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
]


class GakumasuBot(commands.Bot):
    def __init__(self):
        super().__init__(
            command_prefix="!",
            intents=intents,
        )

        # 後で setup_hook() で初期化する
        self.detector: YoloDetector | None = None
        self.tesseract_engine = None
        self.ocr_service = None
        self.inference_service = None

    async def setup_hook(self) -> None:
        try:
            # ====== 推論基盤の初期化 ======
            log.info("Initializing YOLO detector...")

            self.detector = YoloDetector(
                model_path=YOLO_MODEL_PATH,
                confidence_threshold=0.25,
                image_size=(640, 640),
                device=None,
            )

            log.info(
                "YOLO detector initialized: "
                "model=%s format=%s classes=%d",
                self.detector.model_name,
                self.detector.model_format,
                len(self.detector.class_names),
            )

            log.info("Running YOLO warmup...")

            self.detector.warmup()

            log.info("YOLO warmup completed.")

            # ====== スラッシュコマンド登録 ======
            for module_name in MODULES:
                importlib.import_module(module_name)
            
            # サブコマンドが追加されたgkmsをTreeへ登録する
            self.tree.add_command(gkms)

            log.info(
                "Command tree prepared "
                "(groups added, modules imported)"
            )

            # コマンドツリーの確認
            from discord import app_commands

            try:
                commands_list = self.tree.get_commands()

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
                            for command in nia_group.commands
                        ],
                    )

            except Exception:
                log.debug(
                    "Command tree introspection failed",
                    exc_info=True,
                )

            log.info("Slash command registration scheduled")

            self.tree.interaction_check = (
                _slash_server_check_impl
            )

            log.info(
                "Assigned global slash server check "
                "to command tree"
            )

        except Exception:
            log.error(
                "setup_hook failed:\n%s",
                traceback.format_exc(),
            )
            raise



bot = GakumasuBot()


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
async def _slash_server_check_impl(
    interaction: discord.Interaction
) -> bool:
    guild = interaction.guild
    user = interaction.user

    guild_id = getattr(guild, "id", None)
    guild_name = getattr(guild, "name", "(DMまたは不明)")
    user_id = getattr(user, "id", None)
    user_name = getattr(user, "display_name", "不明")

    log.debug(
        "slash_server_check called: guild=%s id=%s user=%s cmd=%s",
        guild_name,
        guild_id,
        user_id,
        getattr(
            getattr(interaction, "command", None),
            "qualified_name",
            None,
        ),
    )

    # 1) ユーザー単位ブロック
    block_info = (
        user_repository.get_block(user_id)
        if user_id is not None
        else None
    )
    
    if block_info is not None:
        user_message = (
            block_info["user_message"]
            or "このアカウントでは現在Botを利用できません。詳細は運営までお問い合わせください。"
        )

        reason = (
            block_info["reason"]
            or "テスト用ブロック"
        )

        asyncio.create_task(
            _notify_dev_about_block(
                "user_blocked", 
                interaction
            )
        )
        
        try:
            embed = Embed(
                color=0xE74C3C, 
                description=user_message
            )
            await interaction.response.send_message(
                embed=embed, 
                ephemeral=False
            )
        
        except Exception:
            log.debug(
                "Failed to respond for user-blocked case", 
                exc_info=True
            )

        log.info(
            "Blocked (user): user_id=%s name=%s reason=%s", 
            user_id, 
            getattr(interaction.user, "display_name", None),
            reason,
        )
        
        return False

    # 2) DM不可
    if guild_id is None:
        asyncio.create_task(
            _notify_dev_about_block(
                "dm",
                interaction,
            )
        )

        try:
            embed = Embed(
                color=0xFF9900,
                description=(
                    "### このコマンドは"
                    "サーバー内でのみ使用できます"
                ),
            )
            await interaction.response.send_message(
                embed=embed,
                ephemeral=False,
            )

        except Exception:
            log.debug(
                "Failed to respond for DM-case",
                exc_info=True,
            )

        return False

    # DMでないことを確認してからDBを参照
    guild_info = guild_repository.get_by_guild_id(guild_id)

    # 3) 未登録
    if guild_info is None:
        log.info(
            "Blocked: unregistered guild %s(%s) user %s (%s)", 
            guild_name, 
            guild_id, 
            user_name, 
            user
        )

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
    if not guild_info["enabled"]:
        log.info(
            "Blocked: revoked guild %s(%s)",
            guild_name,
            guild_id,
        )

        asyncio.create_task(
            _notify_dev_about_block(
                "revoked",
                interaction,
            )
        )

        try:
            embed = Embed(
                color=0xE53935,
                description=(
                    "### 🚫 このサーバーでは現在"
                    "Botの利用が停止されています。"
                    "運営までお問い合わせください。"
                ),
            )
            await interaction.response.send_message(
                embed=embed,
                ephemeral=False,
            )

        except Exception:
            log.debug(
                "Failed to respond for revoked case",
                exc_info=True,
            )

        return False

    # 5) 許可
    return True


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
