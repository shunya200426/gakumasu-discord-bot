from abc import ABC, abstractmethod
from discord import Interaction, Embed, ui
from commands.announcements.container_builder import build_container
from commands.announcements.embed_builder import build_embed
from utils.logger import get_logger, use_log_context
from utils.context import build_ctx_from_interaction
from contextlib import asynccontextmanager
import asyncio, os, json, hashlib
import uuid
from pathlib import Path
from datetime import datetime, timedelta, timezone
import zoneinfo


DATASET_ROOT = Path("data_inputs")  # 例: プロジェクト直下 data_inputs/
KEEP_DAYS = 30
UTC = timezone.utc
JST = zoneinfo.ZoneInfo("Asia/Tokyo")


def _utc_now_str(fmt="%Y%m%dT%H%M%S.%fZ"):
    return datetime.now(UTC).strftime(fmt)

# ログと揃えるためのローカル（JST）時刻フォーマッタ
def _local_now_str(fmt="%Y%m%dT%H%M%S"):
    return datetime.now(JST).strftime(fmt)

def _today_str():
    # ログ（JST）に合わせてフォルダ日付もJSTで切る
    return datetime.now(JST).strftime("%Y-%m-%d")

def _short_hash(b: bytes, n: int = 8) -> str:
    return hashlib.sha256(b).hexdigest()[:n]

def _safe_ext(filename: str) -> str:
    ext = os.path.splitext(filename or "")[1].lower()
    return ext if ext in {".png", ".jpg", ".jpeg", ".webp"} else (ext or ".bin")

logger = get_logger()

class BaseCommand(ABC):
    """
    全コマンド共通の基底クラス
    """

    def __init__(self, interaction: Interaction):
        self.interaction = interaction
        self.embed = self._init_embed()
        self._request_id: str | None = None
    
    def _init_embed(self) -> Embed:
        return Embed(color=0x5DADE2)

    def log_command_start(self, command_name: str):
        logger.info(f"コマンド実行開始: {command_name}")

    def log_command_end(self, command_name: str):
        logger.info(f"コマンド実行完了: {command_name}")

    # --- 再計算用の共通ログ ---
    def log_recompute_start(self, command_name: str):
        logger.info(f"再計算実行開始: {command_name}")

    def log_recompute_end(self, command_name: str):
        logger.info(f"再計算実行完了: {command_name}")

    # --- 任意の Interaction 区間に ctx を張るためのヘルパ ---
    @asynccontextmanager
    async def scoped_ctx(self, interaction):
        """
        再計算（モーダル/ボタン/メニュー）など execute() 以外の入口でも
        INFO/ERROR に guild/user/circle を自動付与できるようにする。
        """
        try:
            ctx = await build_ctx_from_interaction(interaction)
        except Exception:
            ctx = {}
        # 既に発行済みの request_id をマージ（再計算など別Interactionでも同一IDで追える）
        if self._request_id:
            ctx = {"request_id": self._request_id, **ctx}
        with use_log_context(ctx):
            yield

    async def send_embed(self):
        """
        EmbedメッセージをDiscordに送信
        """
        await self._safe_send(embed=self.embed)


    # --- 一度だけ安全に送る共通関数 ---
    async def _safe_send(self, *, content: str | None = None, embed: Embed | None = None, 
                         view: ui.View | None = None, ephemeral: bool = False):
        try:
            if getattr(self.interaction.response, "is_done", lambda: False)():
                await self.interaction.followup.send(content=content, embed=embed, view=view, ephemeral=ephemeral)
            else:
                await self.interaction.response.send_message(content=content, embed=embed, view=view, ephemeral=ephemeral)
        except Exception as e:
            logger.warning("send failed: %s", e)

    # BaseCommand クラスの中に追記
    # ===== 画像保存（共通） =====
    @staticmethod
    def _purge_old_days():
        cutoff = datetime.now(JST) - timedelta(days=KEEP_DAYS)
        if DATASET_ROOT.exists():
            for sub in DATASET_ROOT.iterdir():
                if not sub.is_dir():
                    continue
                try:
                    dt = datetime.strptime(sub.name, "%Y-%m-%d").replace(tzinfo=JST)
                except ValueError:
                    continue
                if dt < cutoff:
                    import shutil
                    shutil.rmtree(sub, ignore_errors=True)

    @staticmethod
    def _archive_sync(*, guild_id: int, user_id: int, command: str,
                      images: dict[str, tuple[str, bytes]], meta: dict,
                      request_id: str | None = None):
        """
        images: {"schedule": (filename, bytes), "party": (...), "score": (...)} のような任意集合
        meta  : JSONL に追記する任意メタ（dict）
        """
        day_dir = DATASET_ROOT / _today_str() / str(guild_id) / str(user_id)
        day_dir.mkdir(parents=True, exist_ok=True)

        ts = _local_now_str()
        saved_names = {}

        for key, (fname, blob) in images.items():
            ext = _safe_ext(fname)
            rid = request_id or _short_hash(blob)
            path = day_dir / f"{ts}_{rid}_{key}{ext}"
            with open(path, "wb") as f:
                f.write(blob)
            saved_names[f"{key}_file"] = path.name  # 例: "schedule_file": "...png"

        record = {
            "ts_local": datetime.now(JST).isoformat(timespec="seconds"),
            "ts_utc": _utc_now_str("%Y-%m-%dT%H:%M:%SZ"),
            "guild_id": guild_id,
            "user_id": user_id,
            "command": command,
            "keep_policy": f"{KEEP_DAYS}days",
            **saved_names,
            **meta,
        }
        with open(day_dir / "metadata.jsonl", "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")

        BaseCommand._purge_old_days()

        try:
            logger.info("archive saved: %s", str(day_dir))
        except Exception:
            pass

    @staticmethod
    async def _archive_async(**kwargs):
        # 同期I/Oをスレッドプールへ
        await asyncio.to_thread(BaseCommand._archive_sync, **kwargs)

    async def maybe_archive_inputs(self, *,
                                   interaction,
                                   save_agree: bool,
                                   command: str,
                                   images: dict[str, tuple[str, bytes]],
                                   meta: dict,
                                   thank_you: str = "ご協力ありがとうございます！精度向上のため入力画像を保存します。保存期間は30日で自動的に破棄します。"):
        """
        送信“後”に呼ぶ想定。save_agree が True のときだけ保存・お礼を実施。
        """
        if not save_agree:
            return
        try:
            await interaction.followup.send(thank_you, ephemeral=True)
        except Exception:
            # followup が使えない状況でも保存だけは走らせる
            pass

        try:
            await BaseCommand._archive_async(
                guild_id=interaction.guild_id,
                user_id=interaction.user.id,
                command=command,
                images=images,
                meta=meta,
                request_id=self._request_id,
            )
        except Exception as e:
            # 保存失敗はコマンドの成否に影響させない
            logger.warning(f"バックグラウンド保存に失敗: {e}")

    # ====== ここから：利用停止（剥奪）ロジック（Base に集約） ======
    _BLOCKLIST_PATH = Path("config/blocklist.json")  # 例 {"user_ids": ["123", "456"]}

    @classmethod
    def _load_blocklist(cls) -> set[str]:
        try:
            data = json.loads(cls._BLOCKLIST_PATH.read_text(encoding="utf-8"))
            return {str(u) for u in data.get("user_ids", [])}
        except FileNotFoundError:
            return set()
        except Exception as e:
            logger.warning("blocklist load failed: %s", e)
            return set()

    def _is_blocked(self) -> bool:
        return str(self.interaction.user.id) in self._load_blocklist()


    # ====== サブクラスの execute() を自動でラップする ======
    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        orig = getattr(cls, "execute", None)
        if orig is None or not asyncio.iscoroutinefunction(orig):
            return

        async def _wrapped(self, *a, **kw):
            # 1) 相関IDを発行（1回のexecute全体で共有）
            if getattr(self, "_request_id", None) is None:
                self._request_id = uuid.uuid4().hex[:8]

            # 2) ctx 構築 → 以降の INFO/ERROR に自動付与
            interaction = getattr(self, "interaction", None)
            try:
                ctx = await build_ctx_from_interaction(interaction) if interaction else {}
            except Exception:
                ctx = {}

            # request_id をctxへ統合（DEBUG含む全レベルで先頭に表示される）
            if self._request_id:
                ctx = {"request_id": self._request_id, **ctx}

            with use_log_context(ctx):
                # 3) 新キャラショートサーキット（params.character を検査）
                try:
                    params = a[0] if a else kw.get("params")
                    char_key = getattr(params, "character", None)
                except Exception:
                    char_key = None
                if await BaseCommand._short_circuit_if_new_character(self, character_key=char_key):
                    return
                
                # 4) 元の実装へ
                return await orig(self, *a, **kw)

        setattr(cls, "execute", _wrapped)


    async def _short_circuit_if_new_character(self, *, character_key: str | None, ephemeral: bool = False) -> bool:
        """
        レジストリに“告知定義”があるキャラなら、告知UIだけ送って True を返す（＝以降を中断）。
        レジストリに無ければ False を返して通常処理を続行。
        """
        if not character_key:
            return False
        key = str(character_key)

        # 1) v2（Container）優先：ここでViewを作る
        container = build_container(key)
        if container is not None:
            view = ui.LayoutView(timeout=None)
            view.add_item(container)
            if self.interaction.response.is_done():
                await self.interaction.followup.send(view=view)
            else:
                await self.interaction.response.send_message(view=view)
            return True

        # 2) Embed フォールバック
        embed = build_embed(key)
        if embed is not None:
            await self._safe_send(embed=embed, ephemeral=ephemeral)
            return True

        return False
    

    @abstractmethod
    async def execute(self):
        """
        コマンドのメイン処理
        各コマンドで必ず実装
        """
        pass
