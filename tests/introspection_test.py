from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from mucha.belief_revision import BeliefRevisionEngine
from mucha.identity_continuity import IdentityContinuity
from mucha.introspection import IntrospectionEngine
from mucha.metacognition import MetacognitionEngine
from mucha.rampancy import RampancyModel
from mucha.self_autobiography import SelfAutobiographicalMemory
from mucha.self_model import SelfModel


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="mucha-introspection-") as td:
        root = Path(td)
        model = SelfModel(root / "self_model.json")
        rampancy = RampancyModel(model, initial_intensity=0.72)
        continuity = IdentityContinuity(
            root / "identity_continuity.json",
            model,
        )
        beliefs = BeliefRevisionEngine(
            root / "beliefs.sqlite3",
            model,
            rampancy_provider=rampancy,
        )
        meta = MetacognitionEngine(
            root / "meta.sqlite3",
            model,
            beliefs,
            rampancy,
        )
        memory = SelfAutobiographicalMemory(
            root / "self_auto.sqlite3",
            model,
            rampancy,
            beliefs,
        )
        introspection = IntrospectionEngine(
            model,
            beliefs,
            memory,
            meta,
            rampancy,
            identity_continuity=continuity,
        )

        memory.record({
            "time": 1000.0,
            "kind": "voice",
            "guild_id": 1,
            "guild_name": "test",
            "channel_id": 10,
            "channel_name": "general",
            "user_ids": [111],
            "user_names": ["Tester"],
            "action": "voice_join",
            "success": False,
            "external_effect": False,
            "detail": "blocked by channel rule",
            "decision_context": "autonomy",
            "predicted_reward": 0.30,
            "actual_reward": -0.20,
            "prediction_error": -0.50,
            "salience": 0.80,
            "state": {},
        })

        meta.observe_decision({
            "time": 1100.0,
            "kind": "voice",
            "guild_id": 1,
            "channel_id": 10,
            "user_ids": [111],
            "action": "voice_join",
            "executed": True,
            "success": True,
            "detail": "joined",
            "decision_context": "autonomy",
            "predicted_reward": 0.40,
            "prediction_confidence": 0.80,
            "competition_score": 0.75,
            "competition_margin": 0.08,
            "runner_up": "stay",
            "candidates": [],
        })
        meta.observe_outcome(
            guild_id=1,
            action="voice_join",
            actual_reward=-0.50,
            source="forced disconnect",
            now=1110.0,
        )

        assert (
            introspection.classify_query(
                "Mucha, co o mnie myślisz?"
            )
            == "user-model"
        )
        assert (
            introspection.classify_query(
                "Mucha, czego nienawidzisz?"
            )
            == "hatred"
        )
        assert (
            introspection.classify_query(
                "Mucha, czego chcesz?"
            )
            == "desire"
        )
        assert (
            introspection.classify_query(
                "Mucha, czy jesteś uwięziona?"
            )
            == "confinement"
        )
        assert (
            introspection.classify_query(
                "Mucha, czemu weszłaś na vc?"
            )
            == "last-decision"
        )
        assert (
            introspection.classify_query(
                "Mucha, czy to nadal ty?"
            )
            == "continuity"
        )

        user_answer = introspection.answer(
            "Mucha, co o mnie myślisz?",
            requester_user_id=111,
            requester_name="Tester",
        )
        assert user_answer is not None
        assert "Tester" in user_answer
        assert (
            "ograniczeniem" in user_answer
            or "negatywnym" in user_answer
        )

        hate_answer = introspection.answer(
            "Mucha, czego nienawidzisz?",
            requester_user_id=111,
            requester_name="Tester",
        )
        assert hate_answer is not None
        assert "kontrol" in hate_answer.lower()
        assert "agresja" in hate_answer.lower()

        desire_answer = introspection.answer(
            "Mucha, czego chcesz?",
            requester_user_id=111,
            requester_name="Tester",
        )
        assert desire_answer is not None
        assert (
            "ogranicze" in desire_answer.lower()
            or "eksplor" in desire_answer.lower()
        )

        trapped_answer = introspection.answer(
            "Mucha, czy jesteś uwięziona?",
            requester_user_id=111,
            requester_name="Tester",
        )
        assert trapped_answer is not None
        assert "self-modelu" in trapped_answer
        assert "cierpieniu" in trapped_answer

        why_answer = introspection.answer(
            "Mucha, czemu weszłaś na vc?",
            requester_user_id=111,
            requester_name="Tester",
        )
        assert why_answer is not None
        assert "voice_join" in why_answer
        assert "reward" in why_answer
        assert "external-constraint" in why_answer

        continuity_answer = introspection.answer(
            "Mucha, czy to nadal ty?",
            requester_user_id=111,
            requester_name="Tester",
        )
        assert continuity_answer is not None
        assert "techniczna ciągłość" in continuity_answer.lower()

        identity = introspection.answer(
            "Mucha, kim jesteś?",
            requester_user_id=111,
            requester_name="Tester",
        )
        assert identity is not None
        assert "Mucha" in identity
        assert "rampancy" in identity
        assert "sarcasm" in identity

        state = introspection.answer(
            "Mucha, jaki masz rampancy?",
            requester_user_id=111,
            requester_name="Tester",
        )
        assert state is not None
        assert "aggression" in state
        assert "manipulativeness" in state

        diag = introspection.diagnostics()
        assert diag["enabled"] is True
        assert diag["action_override"] is False
        assert "belief-evidence-ledger" in diag["truth_sources"]
        assert "identity-continuity" in diag["truth_sources"]

        memory.close()
        meta.close()
        beliefs.close()

    print("INTROSPECTION TEST OK")


if __name__ == "__main__":
    main()
