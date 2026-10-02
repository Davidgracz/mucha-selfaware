from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from mucha.identity_continuity import IdentityContinuity
from mucha.runtime_awareness import RuntimeAwareness
from mucha.self_model import SelfModel


def start_session(
    self_model_path: Path,
    continuity_path: Path,
    project_root: Path,
):
    model = SelfModel(self_model_path)
    continuity = IdentityContinuity(continuity_path, model)
    runtime = RuntimeAwareness(model, project_root=project_root)
    runtime.observe_startup()
    snap = continuity.observe_startup(runtime.snapshot())
    return model, runtime, continuity, snap


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="mucha-continuity-") as td:
        root = Path(td)
        state = root / "state"
        self_model_path = state / "self_model.json"
        continuity_path = state / "identity_continuity.json"

        model1, runtime1, continuity1, first = start_session(
            self_model_path,
            continuity_path,
            root,
        )
        lineage = first["lineage_id"]
        instance = first["instance_id"]

        assert first["enabled"] is True
        assert first["generation"] == 1
        assert first["status"] == "first-observation"
        assert lineage
        assert first["action_override"] is False
        assert first["phenomenal_consciousness_claim"] is False

        runtime1.observe_shutdown(reason="test-clean-close")
        continuity1.observe_shutdown(reason="test-clean-close")

        model2, runtime2, continuity2, second = start_session(
            self_model_path,
            continuity_path,
            root,
        )
        assert second["lineage_id"] == lineage
        assert second["instance_id"] == instance
        assert second["generation"] == 2
        assert second["status"] == "continuous-restart"
        assert second["previous_session_id"] == runtime1.session_id
        assert second["previous_clean_shutdown"] is True
        assert second["confidence"] >= 0.99

        belief = model2.get_belief(
            "self",
            "identity_continues_across_sessions",
        )
        assert belief is not None
        assert belief.value is True
        assert belief.confidence >= 0.99

        model3, runtime3, continuity3, third = start_session(
            self_model_path,
            continuity_path,
            root,
        )
        assert third["generation"] == 3
        assert third["lineage_id"] == lineage
        assert third["status"] == "recovered-after-unclean-stop"
        assert third["previous_session_id"] == runtime2.session_id
        assert third["previous_clean_shutdown"] is False

        runtime3.observe_shutdown(reason="before-move")
        continuity3.observe_shutdown(reason="before-move")

        moved_root = root / "restored-copy"
        moved_root.mkdir()
        model4, runtime4, continuity4, fourth = start_session(
            self_model_path,
            continuity_path,
            moved_root,
        )
        assert fourth["generation"] == 4
        assert fourth["lineage_id"] == lineage
        assert fourth["instance_id"] == instance
        assert fourth["status"] == "restored-or-moved-state"
        assert "techniczna ciągłość" in continuity4.describe().lower()

        runtime4.observe_shutdown(reason="test-finish")
        continuity4.observe_shutdown(reason="test-finish")

    print("IDENTITY CONTINUITY TEST OK")


if __name__ == "__main__":
    main()
