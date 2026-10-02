from __future__ import annotations

import os
import platform
import socket
import subprocess
import sys
import time
import uuid
from pathlib import Path
from typing import Any

from .self_model import SelfModel


class RuntimeAwareness:
    """SA-02: observable facts about the process Mucha is running inside.

    This component records only facts obtainable from the local runtime,
    repository and Discord client. It does not select actions.
    """

    def __init__(
        self,
        self_model: SelfModel,
        *,
        project_root: str | Path | None = None,
    ) -> None:
        self.self_model = self_model
        self.project_root = Path(
            project_root
            if project_root is not None
            else Path(__file__).resolve().parents[1]
        ).resolve()
        self.session_id = str(uuid.uuid4())
        self.started_at = time.time()
        self.started_monotonic = time.monotonic()
        self.pid = os.getpid()
        self.hostname = socket.gethostname()
        self._git = self._read_git_info()
        self._discord_ready = False
        self._discord_snapshot: dict[str, Any] = {}

    def _git_command(self, *args: str) -> str | None:
        try:
            result = subprocess.run(
                ["git", "-C", str(self.project_root), *args],
                capture_output=True,
                text=True,
                timeout=1.5,
                check=False,
            )
        except (OSError, subprocess.SubprocessError):
            return None
        if result.returncode != 0:
            return None
        value = result.stdout.strip()
        return value or None

    def _read_git_info(self) -> dict[str, Any]:
        commit = self._git_command("rev-parse", "HEAD")
        branch = self._git_command(
            "rev-parse",
            "--abbrev-ref",
            "HEAD",
        )
        status = self._git_command("status", "--porcelain")
        return {
            "commit": commit,
            "branch": branch,
            "dirty": bool(status) if status is not None else None,
            "available": commit is not None,
        }

    def observe_startup(self) -> dict[str, Any]:
        identity = self.self_model.identity
        try:
            previous_boots = int(identity.get("boot_count", 0))
        except (TypeError, ValueError):
            previous_boots = 0

        self.self_model.set_identity(
            "boot_count",
            previous_boots + 1,
        )
        self.self_model.set_identity(
            "last_boot_at",
            self.started_at,
        )
        self.self_model.set_identity(
            "current_session_id",
            self.session_id,
        )

        self.self_model.set_fact(
            "self",
            "runtime_state",
            "running",
            source="runtime",
        )
        self.self_model.set_fact(
            "self",
            "process_id",
            self.pid,
            source="runtime",
        )
        self.self_model.set_fact(
            "self",
            "host_name",
            self.hostname,
            source="runtime",
        )
        self.self_model.set_fact(
            "self",
            "python_version",
            platform.python_version(),
            source="runtime",
        )
        self.self_model.set_fact(
            "self",
            "python_executable",
            sys.executable,
            source="runtime",
        )
        self.self_model.set_fact(
            "self",
            "operating_system",
            platform.platform(),
            source="runtime",
        )
        self.self_model.set_fact(
            "self",
            "project_root",
            str(self.project_root),
            source="runtime",
        )
        self.self_model.set_fact(
            "self",
            "discord_ready",
            False,
            source="runtime",
        )

        if self._git.get("commit"):
            self.self_model.set_fact(
                "self",
                "git_commit",
                self._git["commit"],
                source="git",
            )
        if self._git.get("branch"):
            self.self_model.set_fact(
                "self",
                "git_branch",
                self._git["branch"],
                source="git",
            )
        if self._git.get("dirty") is not None:
            self.self_model.set_fact(
                "self",
                "working_tree_dirty",
                bool(self._git["dirty"]),
                source="git",
            )

        self.self_model.set_embodiment(
            "runtime",
            {
                "session_id": self.session_id,
                "pid": self.pid,
                "host_name": self.hostname,
                "started_at": self.started_at,
                "project_root": str(self.project_root),
            },
        )
        self.self_model.save()
        return self.snapshot()

    def observe_discord(self, client: Any) -> dict[str, Any]:
        user = getattr(client, "user", None)
        guilds = list(getattr(client, "guilds", ()) or ())

        text_channels = 0
        voice_channels = 0
        for guild in guilds:
            text_channels += len(
                list(getattr(guild, "text_channels", ()) or ())
            )
            voice_channels += len(
                list(getattr(guild, "voice_channels", ()) or ())
            )

        user_id = getattr(user, "id", None)
        user_name = str(user) if user is not None else None
        self._discord_ready = user is not None
        self._discord_snapshot = {
            "ready": self._discord_ready,
            "user_id": int(user_id) if user_id is not None else None,
            "user_name": user_name,
            "guild_count": len(guilds),
            "text_channel_count": text_channels,
            "voice_channel_count": voice_channels,
            "observed_at": time.time(),
        }

        self.self_model.set_fact(
            "self",
            "discord_ready",
            self._discord_ready,
            source="discord-runtime",
        )
        if user_id is not None:
            self.self_model.set_fact(
                "self",
                "discord_user_id",
                int(user_id),
                source="discord-runtime",
            )
        if user_name:
            self.self_model.set_fact(
                "self",
                "discord_identity",
                user_name,
                source="discord-runtime",
            )
        self.self_model.set_fact(
            "self",
            "discord_guild_count",
            len(guilds),
            source="discord-runtime",
        )
        self.self_model.set_fact(
            "self",
            "discord_text_channel_count",
            text_channels,
            source="discord-runtime",
        )
        self.self_model.set_fact(
            "self",
            "discord_voice_channel_count",
            voice_channels,
            source="discord-runtime",
        )

        self.self_model.set_embodiment(
            "discord",
            dict(self._discord_snapshot),
        )
        self.self_model.save()
        return self.snapshot()

    def observe_shutdown(
        self,
        *,
        reason: str = "client-close",
    ) -> None:
        now = time.time()
        self.self_model.set_fact(
            "self",
            "runtime_state",
            "stopped",
            source="runtime",
        )
        self.self_model.set_fact(
            "self",
            "discord_ready",
            False,
            source="runtime",
        )
        self.self_model.set_identity("last_shutdown_at", now)
        self.self_model.set_identity(
            "last_shutdown_reason",
            str(reason),
        )
        self.self_model.set_identity(
            "last_session_uptime_seconds",
            max(0.0, time.monotonic() - self.started_monotonic),
        )
        self.self_model.set_embodiment(
            "runtime",
            {
                **dict(
                    self.self_model.embodiment.get("runtime", {})
                ),
                "stopped_at": now,
            },
        )
        self.self_model.save()

    def snapshot(self) -> dict[str, Any]:
        uptime = max(
            0.0,
            time.monotonic() - self.started_monotonic,
        )
        return {
            "enabled": True,
            "session_id": self.session_id,
            "started_at": self.started_at,
            "uptime_seconds": uptime,
            "pid": self.pid,
            "host_name": self.hostname,
            "python_version": platform.python_version(),
            "python_executable": sys.executable,
            "operating_system": platform.platform(),
            "project_root": str(self.project_root),
            "git": dict(self._git),
            "discord": dict(self._discord_snapshot),
            "discord_ready": self._discord_ready,
            "self_model": self.self_model.diagnostics(),
        }
