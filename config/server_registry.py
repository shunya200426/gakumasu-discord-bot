# gakumasu_bot/config/server_registry.py
from __future__ import annotations
import asyncio
import json
from pathlib import Path
from typing import Dict, Optional, Literal

State = Literal["allowed", "revoked"]

class ServerRegistry:
    """
    servers.json から guild_id -> {circle_name, state} を読み込む。
    変更は mtime を見て必要時のみ再読込（受動リロードA方式）。
    """
    def __init__(self, path: str | Path):
        self._path = Path(path)
        self._mtime_ns: int = -1
        self._lock = asyncio.Lock()
        self._circle_by_id: Dict[str, str] = {}
        self._state_by_id: Dict[str, State] = {}

    async def ensure_loaded(self) -> None:
        """ファイルの更新があれば安全に再読込（丸ごと置換）"""
        try:
            mtime = self._path.stat().st_mtime_ns
        except FileNotFoundError:
            return
        if mtime == self._mtime_ns:
            return

        async with self._lock:
            m2 = self._path.stat().st_mtime_ns
            if m2 == self._mtime_ns:
                return
            data = json.loads(self._path.read_text(encoding="utf-8"))

            circle_by_id: Dict[str, str] = {}
            state_by_id: Dict[str, State] = {}

            for i, it in enumerate(data.get("servers", [])):
                gid = str(it.get("guild_id", "")).strip()
                if not gid:
                    continue
                circle = str(it.get("circle_name", "") or "(unregistered)")
                state = it.get("state", "allowed")
                if state not in ("allowed", "revoked"):
                    state = "allowed"

                circle_by_id[gid] = circle
                state_by_id[gid] = state  # type: ignore[assignment]

            # 丸ごと差し替え（参照の原子性を担保）
            self._circle_by_id = circle_by_id
            self._state_by_id = state_by_id
            self._mtime_ns = m2
            import logging
            logging.getLogger("gakumasu_bot").info(
                "ServerRegistry loaded: %d entries (path=%s)",
                len(self._circle_by_id), self._path
            )

    # ---- 便利用関数（build_ctx_from_interaction から呼ばれる） ----
    async def circle_name(self, guild_id: Optional[int | str], default="(unregistered)") -> str:
        await self.ensure_loaded()
        if guild_id is None:
            return default
        return self._circle_by_id.get(str(guild_id), default)

    async def is_registered(self, guild_id: Optional[int | str]) -> bool:
        await self.ensure_loaded()
        return guild_id is not None and str(guild_id) in self._circle_by_id

    async def is_allowed(self, guild_id: Optional[int | str]) -> bool:
        await self.ensure_loaded()
        if guild_id is None:
            return False
        return self._state_by_id.get(str(guild_id), "allowed") == "allowed"

    async def is_revoked(self, guild_id: Optional[int | str]) -> bool:
        await self.ensure_loaded()
        if guild_id is None:
            return False
        return self._state_by_id.get(str(guild_id), "allowed") == "revoked"
