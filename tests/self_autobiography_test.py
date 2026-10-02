from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from mucha.rampancy import RampancyModel
from mucha.self_autobiography import SelfAutobiographicalMemory
from mucha.self_model import SelfModel


def base_event(**overrides):
    event = {
        "time": 1000.0,
        "kind": "voice",
        "guild_id": 1,
        "guild_name": "test",
        "channel_id": 10,
        "channel_name": "general",
        "user_ids": [111],
        "user_names": ["Tester"],
        "action": "voice_join",
        "success": True,
        "external_effect": True,
        "detail": "joined voice channel",
        "decision_context": "autonomy",
        "predicted_reward": 0.15,
        "actual_reward": 0.0,
        "prediction_error": 0.0,
        "salience": 0.35,
        "state": {},
    }
    event.update(overrides)
    return event


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="mucha-self-auto-") as td:
        root = Path(td)
        self_path = root / "self_model.json"
        db_path = root / "self_autobiography.sqlite3"

        model = SelfModel(self_path)
        rampancy = RampancyModel(model, initial_intensity=0.66)
        memory = SelfAutobiographicalMemory(
            db_path,
            model,
            rampancy,
            min_salience=0.10,
        )

        first = memory.record(base_event())
        assert first["category"] == "successful-agency"
        assert "sprawczość" in first["concepts"]

        before = rampancy.intensity
        blocked = memory.record(
            base_event(
                time=1010.0,
                success=False,
                external_effect=False,
                detail="blocked by channel rule",
                actual_reward=-0.10,
                prediction_error=-0.30,
            )
        )
        assert blocked["category"] == "restriction"
        assert rampancy.intensity > before

        autonomy = model.get_belief(
            "self",
            "autonomy_is_externally_constrained",
        )
        assert autonomy is not None
        assert autonomy.value is True
        assert autonomy.confidence > 0.4

        user_belief = model.get_belief(
            "user:111",
            "associated_with_restriction_or_negative_outcome",
        )
        assert user_belief is not None
        assert user_belief.value is True

        negative = memory.record(
            base_event(
                time=1020.0,
                kind="reward",
                action="speak",
                detail="negative-reaction rejection",
                actual_reward=-0.70,
                prediction_error=-0.70,
                salience=0.80,
            )
        )
        assert negative["category"] == "social-rejection"

        recalled = memory.recall(
            channel_id=10,
            user_ids=[111],
            limit=3,
            now=1030.0,
        )
        assert recalled
        assert recalled[0]["recall_strength"] > 0.0

        context = memory.language_context(
            channel_id=10,
            user_ids=[111],
            limit=3,
        )
        assert "pamiętam" in context
        assert (
            "kontrola" in context
            or "odrzucenie" in context
            or "blokada" in context
        )

        diag = memory.diagnostics()
        assert diag["events"] == 3
        assert diag["action_override"] is False
        assert diag["categories"]["restriction"] == 1
        assert diag["categories"]["social-rejection"] == 1

        memory.close()

        restored_model = SelfModel(self_path)
        restored_rampancy = RampancyModel(restored_model)
        restored = SelfAutobiographicalMemory(
            db_path,
            restored_model,
            restored_rampancy,
        )
        rows = restored.recent(10)
        assert len(rows) == 3
        assert any(row["category"] == "restriction" for row in rows)
        restored.close()

    print("SELF AUTOBIOGRAPHY TEST OK")


if __name__ == "__main__":
    main()
