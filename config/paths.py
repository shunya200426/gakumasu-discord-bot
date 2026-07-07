"""
Bot全体で使用するファイル・ディレクトリパスを定義するモジュール。

このモジュールではPathオブジェクトのみを定義し、
ディレクトリ作成などの副作用を持つ処理は行わない。
"""

from pathlib import Path

# =========================
# Base Directories
# =========================

HOME_DIR = Path.home()

PROJECT_DIR = HOME_DIR / "projects" / "gakumasu-discord-bot"

DATA_DIR = HOME_DIR / "data" / "discord-bot"

LOG_DIR = HOME_DIR / "logs" / "discord-bot"

BACKUP_DIR = HOME_DIR / "backups" / "discord-bot"

# =========================
# Database
# =========================

DATABASE_PATH = DATA_DIR / "bot.db"

# =========================
# Uploads
# =========================

UPLOAD_DIR = DATA_DIR / "uploads"

INFERENCE_UPLOAD_DIR = UPLOAD_DIR / "inference"

CROP_UPLOAD_DIR = UPLOAD_DIR / "crops"

PROVIDED_UPLOAD_DIR = UPLOAD_DIR / "provided"

FAILED_UPLOAD_DIR = UPLOAD_DIR / "failed"

# =========================
# Exports
# =========================

EXPORT_DIR = DATA_DIR / "exports"

INFERENCE_EXPORT_DIR = EXPORT_DIR / "inference"

STATISTICS_EXPORT_DIR = EXPORT_DIR / "statistics"

CSV_EXPORT_DIR = EXPORT_DIR / "csv"

# =========================
# Managed Directories
# =========================

REQUIRED_DIRECTORIES = [
    DATA_DIR,
    LOG_DIR,
    BACKUP_DIR,
    UPLOAD_DIR,
    INFERENCE_UPLOAD_DIR,
    CROP_UPLOAD_DIR,
    PROVIDED_UPLOAD_DIR,
    FAILED_UPLOAD_DIR,
    EXPORT_DIR,
    INFERENCE_EXPORT_DIR,
    STATISTICS_EXPORT_DIR,
    CSV_EXPORT_DIR,
]