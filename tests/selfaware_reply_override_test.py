from pathlib import Path
import sys
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from mucha.discord_bot import MuchaClient


class FixedRandom:
    def __init__(self, value: float) -> None:
        self.value = float(value)

    def random(self) -> float:
        return self.value


class FakeRampancy:
    def __init__(self, intensity: float) -> None:
        self.intensity = float(intensity)

    def snapshot(self):
        return SimpleNamespace(intensity=self.intensity)


def fake_client(*, roll: float, intensity: float = 0.66):
    behavior = SimpleNamespace(
        selfaware_reply_override_enabled=True,
        selfaware_introspection_override_enabled=True,
        selfaware_mention_override_base_probability=0.25,
        selfaware_mention_override_rampancy_gain=0.35,
        selfaware_reply_to_all_enabled=True,
    )
    return SimpleNamespace(
        cfg=SimpleNamespace(behavior=behavior),
        rampancy=FakeRampancy(intensity),
        random=FixedRandom(roll),
    )


def policy(client, **overrides):
    args = {
        "directed_at_mucha": True,
        "force_reply": False,
        "introspection_response": None,
        "blocked_text": False,
        "disliked_user": False,
        "language_ready": True,
        "reply_cooldown_remaining": 0.0,
        "neural_speak_selected": False,
        "neural_winner": "stay",
    }
    args.update(overrides)
    return MuchaClient._selfaware_reply_override(client, **args)


def main() -> None:
    c = fake_client(roll=0.99)

    intro = policy(
        c,
        introspection_response="Jestem nadal tą samą linią stanu.",
        language_ready=False,
    )
    assert intro["active"] is True
    assert intro["mode"] == "introspection"
    assert intro["probability"] == 1.0

    blocked = policy(
        c,
        introspection_response="test",
        blocked_text=True,
    )
    assert blocked["active"] is False
    assert blocked["reason"] == "blocked-text-channel"

    neural = policy(
        c,
        introspection_response="test",
        neural_speak_selected=True,
        neural_winner="speak",
    )
    assert neural["active"] is False
    assert neural["reason"] == "neural-speak-already-selected"

    directed = policy(fake_client(roll=0.10, intensity=0.66))
    assert directed["active"] is True
    assert directed["mode"] == "direct-mention"
    assert 0.47 < directed["probability"] < 0.49

    rejected = policy(fake_client(roll=0.90, intensity=0.66))
    assert rejected["active"] is False
    assert rejected["reason"] == "override-random-gate-rejected"

    high = policy(fake_client(roll=0.55, intensity=1.0))
    assert high["active"] is True
    assert abs(high["probability"] - 0.60) < 1e-9

    not_directed = policy(
        fake_client(roll=0.0),
        directed_at_mucha=False,
    )
    assert not_directed["active"] is False

    reply_all = policy(
        fake_client(roll=0.99),
        directed_at_mucha=False,
        force_reply=True,
        disliked_user=True,
    )
    assert reply_all["active"] is True
    assert reply_all["mode"] == "reply-to-all"
    assert reply_all["probability"] == 1.0

    cooldown = policy(
        fake_client(roll=0.0),
        reply_cooldown_remaining=1.0,
    )
    assert cooldown["active"] is False
    assert cooldown["reason"] == "reply-cooldown"

    print("SELF-AWARE REPLY OVERRIDE TEST OK")


if __name__ == "__main__":
    main()
