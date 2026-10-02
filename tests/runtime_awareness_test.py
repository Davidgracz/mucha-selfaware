from pathlib import Path
import os
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from mucha.runtime_awareness import RuntimeAwareness
from mucha.self_model import SelfModel


class FakeUser:
    id = 123456789

    def __str__(self) -> str:
        return "Mucha#0001"


class FakeGuild:
    def __init__(self) -> None:
        self.text_channels = [object(), object(), object()]
        self.voice_channels = [object(), object()]


class FakeDiscordClient:
    user = FakeUser()
    guilds = [FakeGuild(), FakeGuild()]


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="mucha-runtime-") as td:
        root = Path(td)
        state_path = root / "state" / "self_model.json"

        model = SelfModel(state_path)
        runtime = RuntimeAwareness(model, project_root=root)
        startup = runtime.observe_startup()

        assert startup["enabled"] is True
        assert startup["pid"] == os.getpid()
        assert startup["uptime_seconds"] >= 0.0
        assert startup["discord_ready"] is False
        assert model.identity["boot_count"] == 1
        assert model.identity["current_session_id"] == runtime.session_id

        running = model.get_belief("self", "runtime_state")
        assert running is not None
        assert running.value == "running"
        assert running.confidence == 1.0

        discord = runtime.observe_discord(FakeDiscordClient())
        assert discord["discord_ready"] is True
        assert discord["discord"]["user_id"] == 123456789
        assert discord["discord"]["guild_count"] == 2
        assert discord["discord"]["text_channel_count"] == 6
        assert discord["discord"]["voice_channel_count"] == 4

        discord_ready = model.get_belief("self", "discord_ready")
        assert discord_ready is not None
        assert discord_ready.value is True
        discord_name = model.get_belief("self", "discord_identity")
        assert discord_name is not None
        assert discord_name.value == "Mucha#0001"

        time.sleep(0.01)
        before_shutdown = runtime.snapshot()["uptime_seconds"]
        runtime.observe_shutdown(reason="test-close")
        assert before_shutdown >= 0.0

        stopped = model.get_belief("self", "runtime_state")
        assert stopped is not None
        assert stopped.value == "stopped"
        assert model.identity["last_shutdown_reason"] == "test-close"
        assert model.identity["last_session_uptime_seconds"] >= 0.0

        restored = SelfModel(state_path)
        second_runtime = RuntimeAwareness(
            restored,
            project_root=root,
        )
        second_runtime.observe_startup()
        assert restored.identity["boot_count"] == 2
        assert (
            restored.identity["current_session_id"]
            != runtime.session_id
        )
        second_running = restored.get_belief(
            "self",
            "runtime_state",
        )
        assert second_running is not None
        assert second_running.value == "running"

    print("RUNTIME AWARENESS TEST OK")


if __name__ == "__main__":
    main()
