# Standard library
import os

# Third-party
from dotenv import load_dotenv

from bot.events import register_events
from bot.gakumasu_bot import GakumasuBot

# Local application
from config.bot_settings import (
    DEFAULT_DEV_DM_COOLDOWN_GLOBAL,
    DEFAULT_DEV_DM_COOLDOWN_PER_GUILD,
    DEFAULT_DEV_DM_COOLDOWN_PER_USER,
)
from config.paths import LOG_DIR
from db.database import DatabaseManager
from utils.context import configure_context_repository
from utils.logger import (
    get_logger,
    setup_logging,
)

# ====== 起動前準備 ======
load_dotenv()
TOKEN = os.getenv("DISCORD_BOT_TOKEN")
TESSDATA_PATH = os.getenv("TESSDATA_PATH")
SYNC_MODE = os.getenv("SYNC_MODE", "global").lower()
TEST_GUILD_ID = os.getenv("TEST_GUILD_ID")
DEV_USER_ID = int(os.getenv("DEV_USER_ID", "0") or 0)
ALERT_CHANNEL_ID = int(os.getenv("ALERT_CHANNEL_ID", "0") or 0)

# --- 開発者DMのクールダウン（秒） ---
# .env で上書き可能（例） DEV_DM_COOLDOWN_PER_GUILD=300
DEV_DM_COOLDOWN_PER_GUILD = int(
    os.getenv(
        "DEV_DM_COOLDOWN_PER_GUILD",
        str(DEFAULT_DEV_DM_COOLDOWN_PER_GUILD),
    )
)

DEV_DM_COOLDOWN_PER_USER = int(
    os.getenv(
        "DEV_DM_COOLDOWN_PER_USER",
        str(DEFAULT_DEV_DM_COOLDOWN_PER_USER),
    )
)

DEV_DM_COOLDOWN_GLOBAL = int(
    os.getenv(
        "DEV_DM_COOLDOWN_GLOBAL",
        str(DEFAULT_DEV_DM_COOLDOWN_GLOBAL),
    )
)


# ログ初期化
setup_logging(
    name             = "gakumasu_bot",
    log_dir          = str(LOG_DIR),
    console_level    = __import__("logging").INFO,
    file_level       = __import__("logging").DEBUG,
    split_error_file = True,
    use_json         = False,     # JSONログにしたいときは True
    rotation         = "time",    # Raspberry Piで容量基準にしたいなら "size"
    backup_days      = 0,
)

log = get_logger()


# ====== DB初期化 ======
db = DatabaseManager()
db.initialize()

if db.guilds is None or db.users is None:
    raise RuntimeError("Repository initialization failed")

configure_context_repository(db.guilds)


bot = GakumasuBot(
    db,
    tessdata_path=TESSDATA_PATH,
    dev_user_id=DEV_USER_ID,
    alert_channel_id=ALERT_CHANNEL_ID,
    cooldown_per_guild=DEV_DM_COOLDOWN_PER_GUILD,
    cooldown_per_user=DEV_DM_COOLDOWN_PER_USER,
    cooldown_global=DEV_DM_COOLDOWN_GLOBAL,
)

register_events(
    bot,
    sync_mode=SYNC_MODE,
    test_guild_id=TEST_GUILD_ID,
)

bot.run(TOKEN)