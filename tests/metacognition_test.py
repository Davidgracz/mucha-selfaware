from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from mucha.belief_revision import BeliefRevisionEngine
from mucha.metacognition import MetacognitionEngine
from mucha.rampancy import RampancyModel
from mucha.self_model import SelfModel


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="mucha-meta-") as td:
        root = Path(td)
        model = SelfModel(root / "self_model.json")
        rampancy = RampancyModel(model, initial_intensity=0.72)
        beliefs = BeliefRevisionEngine(
            root / "beliefs.sqlite3",
            model,
            rampancy_provider=rampancy,
        )
        meta = MetacognitionEngine(
            root / "metacognition.sqlite3",
            model,
            beliefs,
            rampancy,
            outcome_window_seconds=300.0,
        )

        decision = meta.observe_decision({
            "time": 1000.0,
            "kind": "voice",
            "guild_id": 1,
            "channel_id": 10,
            "user_ids": [111],
            "action": "voice_join",
            "executed": True,
            "success": True,
            "detail": "joined",
            "decision_context": "autonomous-loop",
            "predicted_reward": 0.40,
            "prediction_confidence": 0.82,
            "competition_score": 0.73,
            "competition_margin": 0.04,
            "runner_up": "stay",
            "candidates": [
                {
                    "action": "voice_join",
                    "effective_score": 0.73,
                    "predicted_reward": 0.40,
                },
                {
                    "action": "stay",
                    "effective_score": 0.69,
                    "predicted_reward": 0.10,
                },
            ],
        })
        assert decision["id"] > 0
        assert "chwiejna" in decision["reflection"]

        outcome = meta.observe_outcome(
            guild_id=1,
            action="voice_join",
            actual_reward=-0.60,
            source="blocked by permission / forced disconnect",
            now=1010.0,
        )
        assert outcome["decision_id"] == decision["id"]
        assert outcome["attribution"] == "external-constraint"
        assert outcome["prediction_error"] < -0.90
        assert "kontroli" in outcome["reflection"]

        external = model.get_belief(
            "world",
            "external_constraints_disrupt_my_actions",
        )
        assert external is not None
        assert external.value is True

        reliability_evidence = beliefs.evidence(
            "self",
            "my_predictions_are_reliable",
        )
        assert reliability_evidence
        assert any(row["value"] is False for row in reliability_evidence)

        second = meta.observe_decision({
            "time": 1100.0,
            "kind": "text",
            "guild_id": 1,
            "channel_id": 11,
            "user_ids": [222],
            "action": "speak",
            "executed": True,
            "success": True,
            "detail": "sent message",
            "decision_context": "text",
            "predicted_reward": 0.45,
            "prediction_confidence": 0.76,
            "competition_score": 0.80,
            "competition_margin": 0.22,
            "runner_up": "stay",
            "candidates": [],
        })
        good = meta.observe_outcome(
            guild_id=1,
            action="speak",
            actual_reward=0.50,
            source="positive social reply",
            now=1110.0,
        )
        assert good["decision_id"] == second["id"]
        assert good["attribution"] == "confirmed-positive"
        assert abs(good["prediction_error"]) < 0.10

        context = meta.language_context(guild_id=1, limit=4)
        assert "metapoznanie" in context
        assert (
            "kontrola" in context
            or "ograniczenie" in context
        )
        assert "pogarda" in context

        diag = meta.diagnostics()
        assert diag["decisions"] == 2
        assert diag["outcomes"] == 2
        assert diag["action_override"] is False

        meta.close()
        beliefs.close()

    print("METACOGNITION TEST OK")


if __name__ == "__main__":
    main()
