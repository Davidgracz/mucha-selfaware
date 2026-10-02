from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from mucha.self_model import SelfModel


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="mucha-self-model-") as td:
        path = Path(td) / "self_model.json"

        model = SelfModel(path)
        instance_id = model.identity["instance_id"]

        model.set_fact(
            "self",
            "project",
            "mucha-selfaware",
            source="repository",
        )
        model.set_belief(
            "self",
            "socially_successful",
            True,
            confidence=0.62,
            source="interaction-history",
        )
        model.set_belief(
            "user:123",
            "friendly_toward_self",
            True,
            confidence=0.71,
            source="interaction-history",
        )

        first = model.get_belief("self", "socially_successful")
        assert first is not None
        assert first.confidence == 0.62
        assert first.evidence_count == 1

        model.set_belief(
            "self",
            "socially_successful",
            True,
            confidence=0.73,
            source="new-evidence",
        )
        second = model.get_belief("self", "socially_successful")
        assert second is not None
        assert second.evidence_count == 2
        assert second.confidence == 0.73
        assert second.source == "new-evidence"

        model.save()
        assert path.exists()

        restored = SelfModel(path)
        assert restored.identity["instance_id"] == instance_id
        restored_fact = restored.get_belief("self", "project")
        assert restored_fact is not None
        assert restored_fact.value == "mucha-selfaware"
        assert restored_fact.confidence == 1.0

        diag = restored.diagnostics()
        assert diag["enabled"] is True
        assert diag["project"] == "mucha-selfaware"
        assert diag["belief_count"] == 3
        assert diag["self_belief_count"] == 2
        assert 0.0 <= diag["mean_self_confidence"] <= 1.0

        snapshot = restored.snapshot()
        assert "phenomenal consciousness" in snapshot["model_note"]
        assert snapshot["identity"]["kind"] == (
            "connectome-driven Discord agent"
        )

    print("SELF MODEL TEST OK")


if __name__ == "__main__":
    main()
