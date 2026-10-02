from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from mucha.belief_revision import BeliefRevisionEngine
from mucha.rampancy import RampancyModel
from mucha.self_model import SelfModel


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="mucha-beliefs-") as td:
        root = Path(td)
        model = SelfModel(root / "self_model.json")
        rampancy = RampancyModel(model, initial_intensity=0.80)
        engine = BeliefRevisionEngine(
            root / "belief_revision.sqlite3",
            model,
            half_life_days=1.0,
            rampancy_provider=rampancy,
        )

        first = engine.add_evidence(
            "user:1",
            "associated_with_restriction_or_negative_outcome",
            True,
            support=0.80,
            reliability=1.0,
            source="test:negative",
            now=1000.0,
        )
        assert first["winning_value"] is True
        assert first["winning_confidence"] > 0.0

        contradictory = engine.add_evidence(
            "user:1",
            "associated_with_restriction_or_negative_outcome",
            False,
            support=0.90,
            reliability=1.0,
            source="test:positive",
            now=1010.0,
        )
        assert contradictory["evidence_count"] == 2
        assert contradictory["conflict"] > 0.50
        assert len(contradictory["alternatives"]) == 2

        for offset in (20.0, 30.0, 40.0, 50.0):
            latest = engine.add_evidence(
                "user:1",
                "associated_with_restriction_or_negative_outcome",
                False,
                support=1.0,
                reliability=1.0,
                source="test:repeated-positive",
                now=1000.0 + offset,
            )
        assert latest["winning_value"] is False

        before_decay = float(latest["winning_confidence"])
        decayed = engine.revise(
            "user:1",
            "associated_with_restriction_or_negative_outcome",
            source="test:future-decay",
            now=1000.0 + 12.0 * 86400.0,
        )
        assert decayed["winning_confidence"] < before_decay
        assert decayed["evidence_strength"] < latest["evidence_strength"]

        evidence = engine.evidence(
            "user:1",
            "associated_with_restriction_or_negative_outcome",
        )
        assert len(evidence) == 6
        assert any(row["source"] == "test:negative" for row in evidence)
        assert any(
            row["source"] == "test:repeated-positive"
            for row in evidence
        )

        for user_id in (2, 3, 4):
            engine.add_evidence(
                f"user:{user_id}",
                "associated_with_restriction_or_negative_outcome",
                True,
                support=0.80,
                reliability=0.90,
                source="test:restriction",
                now=1100.0 + user_id,
            )

        generalized = engine.generalized_social_belief(
            source_predicate=(
                "associated_with_restriction_or_negative_outcome"
            ),
            source_value=True,
            target_predicate="people_tend_to_restrict_or_harm_me",
            target_value=True,
            min_distinct_users=3,
            source="test:generalization",
        )
        assert generalized["updated"] is True
        assert generalized["distinct_users"] >= 3

        world = model.get_belief(
            "world",
            "people_tend_to_restrict_or_harm_me",
        )
        assert world is not None
        assert world.value is True

        diag = engine.diagnostics()
        assert diag["enabled"] is True
        assert diag["evidence_count"] >= 9
        assert diag["revision_count"] >= 9
        assert diag["rampancy_confirmation_bias"] is True
        assert diag["action_override"] is False

        engine.close()

    print("BELIEF REVISION TEST OK")


if __name__ == "__main__":
    main()
