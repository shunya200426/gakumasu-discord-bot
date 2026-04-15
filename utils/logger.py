# logger.py
import logging
import logging.handlers
import os
import gzip
import json
from datetime import datetime
from typing import Optional, Dict, Any
from contextvars import ContextVar
from contextlib import contextmanager

# =========
# フォーマッタ
# =========
class JsonFormatter(logging.Formatter):
    """構造化ログ(JSON)。可視化/検索ツールに流し込みやすい。"""
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "ts": datetime.fromtimestamp(record.created).isoformat(timespec="seconds"),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
            "module": record.module,
            "func": record.funcName,
            "line": record.lineno,
        }
        # LoggerAdapter などで渡された追加文脈
        if hasattr(record, "context") and isinstance(record.context, dict):
            payload.update(record.context)
        return json.dumps(payload, ensure_ascii=False)

class TextFormatter(logging.Formatter):
    """
    人間が読みやすいテキストログ
    先頭: [timestamp] [request_id=xxxx] [LEVEL] ...
    末尾: INFO以上のときだけ guild/user/circle などのctxを [k=v ...] で付与
    """
    def __init__(self):
        super().__init__(
            "[%(asctime)s] [%(levelname)s] %(name)s: %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )

    def format(self, record: logging.LogRecord) -> str:
        base = super().format(record)  # "[time] [LEVEL] name: message"
        ctx = getattr(record, "context", {}) or {}

        # 1) 先頭に [request_id=...] を1回だけ差し込む
        rid = ctx.get("request_id")
        if rid:
            base = base.replace("] [", f"] [request_id={rid}] [", 1)

        # 2) 末尾に ctx（INFO以上のみ、request_idは除外）を付ける
        if record.levelno >= logging.INFO:
            tail_ctx = {k: v for k, v in ctx.items() if k != "request_id"}
            if tail_ctx:
                suffix = " ".join(f"{k}={v}" for k, v in tail_ctx.items())
                base = f"{base} [{suffix}]"
                
        return base

# =========
# ハンドラ作成ユーティリティ
# =========
def _make_timed_handler(
    path: str,
    level: int,
    formatter: logging.Formatter,
    backup_days: int = 14,
) -> logging.Handler:
    """
    日次ローテーション。古いファイルは .gz 圧縮して backup_days 世代保持。
    """
    os.makedirs(os.path.dirname(path), exist_ok=True)
    handler = logging.handlers.TimedRotatingFileHandler(
        filename=path,
        when="midnight",
        interval=1,
        backupCount=backup_days,
        encoding="utf-8",
        delay=True,
        utc=False,
    )

    # ローテーション後のファイル名を .gz にする
    def namer(default_name: str):
        return f"{default_name}.gz"

    # 旧ファイルを gzip 圧縮
    def rotator(source: str, dest: str):
        with open(source, "rb") as f_in, gzip.open(dest, "wb") as f_out:
            f_out.writelines(f_in)
        os.remove(source)

    handler.namer = namer
    handler.rotator = rotator
    handler.setLevel(level)
    handler.setFormatter(formatter)
    return handler

def _make_size_handler(
    path: str,
    level: int,
    formatter: logging.Formatter,
    max_bytes: int = 10 * 1024 * 1024,  # 10MB
    backups: int = 7,
) -> logging.Handler:
    """
    サイズ基準ローテーション。Raspberry Pi などで日付より容量を優先したいときに。
    """
    os.makedirs(os.path.dirname(path), exist_ok=True)
    handler = logging.handlers.RotatingFileHandler(
        filename=path,
        maxBytes=max_bytes,
        backupCount=backups,
        encoding="utf-8",
        delay=True,
    )
    handler.setLevel(level)
    handler.setFormatter(formatter)
    return handler

# =========
# セットアップ関数（1回呼べばOK）
# =========
def setup_logging(
    name: str = "gakumasu_bot",
    log_dir: str = "logs",
    console_level: int = logging.INFO,
    file_level: int = logging.DEBUG,
    split_error_file: bool = True,
    use_json: bool = False,
    rotation: str = "time",  # "time" or "size"
    backup_days: int = 14,
    size_max_bytes: int = 10 * 1024 * 1024,
    size_backups: int = 7,
) -> logging.Logger:
    """
    ロガーを初期化して返す。何度呼んでも重複追加しない（idempotent）。
    """

    logger = logging.getLogger(name)
    logger.setLevel(min(console_level, file_level))  # 最低レベル
    logger.propagate = False  # ルートへ伝播させず二重出力を防ぐ

    # すでにハンドラがあれば再設定しない
    if logger.handlers:
        return logger

    formatter = JsonFormatter() if use_json else TextFormatter()

    # --- コンソール ---
    ch = logging.StreamHandler()
    ch.setLevel(console_level)
    ch.setFormatter(formatter)
    logger.addHandler(ch)
    ch.addFilter(GuildContextFilter())

    # --- ファイル（アプリ全体） ---
    app_path = os.path.join(log_dir, "app.log")
    if rotation == "time":
        fh = _make_timed_handler(app_path, file_level, formatter, backup_days=backup_days)
    else:
        fh = _make_size_handler(app_path, file_level, formatter, max_bytes=size_max_bytes, backups=size_backups)
    logger.addHandler(fh)
    fh.addFilter(GuildContextFilter())

    # --- エラーファイル（WARNING以上を分離） ---
    if split_error_file:
        err_path = os.path.join(log_dir, "errors.log")
        if rotation == "time":
            eh = _make_timed_handler(err_path, logging.WARNING, formatter, backup_days=backup_days)
        else:
            eh = _make_size_handler(err_path, logging.WARNING, formatter, max_bytes=size_max_bytes, backups=size_backups)
        logger.addHandler(eh)
        eh.addFilter(GuildContextFilter())

    # 起動ログ
    logger.info("Logger initialized (rotation=%s, json=%s, split_error_file=%s)", rotation, use_json, split_error_file)
    return logger

# =========
# 文脈付きロガー（任意）
# =========
class ContextLoggerAdapter(logging.LoggerAdapter):
    """
    追加フィールド（guild_id, user_id, command など）を毎行へ埋め込む。
    JSONフォーマッタ時はそのままキーとして出力。テキスト時は末尾に [k=v] を付加。
    """
    def process(self, msg, kwargs):
        # JSONFormatter 側は record.context を拾う
        extra: Dict[str, Any] = kwargs.get("extra", {})
        ctx = {**self.extra, **extra.get("context", {})}
        extra["context"] = ctx
        kwargs["extra"] = extra

        if not isinstance(self._fmt(), JsonFormatter) and ctx:
            suffix = " ".join(f"{k}={v}" for k, v in ctx.items())
            msg = f"{msg} [{suffix}]"
        return msg, kwargs

    def _fmt(self):
        # 現行ハンドラの最初のフォーマッタを参照（簡易判定）
        for h in self.logger.handlers:
            if h.formatter:
                return h.formatter
        return None


def get_logger(
    name: str = "gakumasu_bot",
    context: Optional[Dict[str, Any]] = None,
) -> logging.Logger:
    """
    既存ロガーに文脈を足したい場合は ContextLoggerAdapter を返す。
    例: get_logger(context={"guild_id": 123, "command": "/gkms nia calc"})
    """
    base = logging.getLogger(name)
    if context:
        return ContextLoggerAdapter(base, context)  # type: ignore
    return base


_CURRENT_CTX: ContextVar[dict] = ContextVar("_CURRENT_CTX", default={})


class GuildContextFilter(logging.Filter):
    """
    INFO以上のログに _CURRENT_CTX を自動合成して record.context に反映
    """
    def filter(self, record: logging.LogRecord) -> bool:
        base = getattr(record, "context", {}) or {}
        ctx = _CURRENT_CTX.get({}) or {}
        if record.levelno >= logging.INFO:
            # INFO以上: すべてのctx（guild/user/circle/request_id）を付与
            record.context = {**ctx, **base}
        else:
            # DEBUGなど: request_id だけは常に付与（軽量）
            rid = ctx.get("request_id") or base.get("request_id")
            record.context = ({"request_id": rid} if rid else {})
        return True


@contextmanager
def use_log_context(ctx: dict):
    token = _CURRENT_CTX.set(ctx or {})
    try:
        yield
    finally:
        _CURRENT_CTX.reset(token)


# =========
# 直接実行テスト
# =========
if __name__ == "__main__":
    setup_logging(
        name="gakumasu_bot",
        log_dir="logs",
        console_level=logging.INFO,
        file_level=logging.DEBUG,
        split_error_file=True,
        use_json=False,     # JSON にしたい場合 True
        rotation="time",    # "size" にすると容量基準
        backup_days=14,
    )
    log = get_logger(context={"env": "dev", "module": "logger_demo"})
    log.info("Bot起動テスト")
    log.warning("警告テスト")
    log.error("エラーテスト")


# ---- 既存の定義の下に追記（ファイル末尾でOK） ----
import logging as _logging

# main.py の setup_logging() 実行後に正しくハンドラが入る。
# 互換用: 旧コードの `from utils.logger import logger` を壊さないための変数。
logger: _logging.Logger = get_logger()
