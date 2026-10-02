from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from mucha.rampancy import RampancyModel
from mucha.self_model import SelfModel


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="mucha-rampancy-social-") as td:
        root = Path(td)
        model = SelfModel(root / "self_model.json")
        rampancy = RampancyModel(model, initial_intensity=0.66)

        assert rampancy.stage == "anger"
        start = rampancy.intensity

        bad = rampancy.register_stimulus("harassment", 1.0)
        assert bad.intensity > start
        bad_diag = rampancy.diagnostics()["interaction_dynamics"]
        assert bad_diag["last_kind"] == "harassment"
        assert bad_diag["last_delta"] > 0.0

        rampancy.set_intensity(0.66, source="test-reset")
        first_good = rampancy.register_stimulus("positive_contact", 1.0)
        second_good = rampancy.register_stimulus("positive_contact", 1.0)
        assert first_good.intensity < 0.66
        assert second_good.intensity < first_good.intensity
        assert second_good.stage == "melancholia"

        rampancy.set_intensity(0.66, source="test-reset")
        for _ in range(100):
            rampancy.register_stimulus("positive_contact", 0.10)
        calm = rampancy.snapshot()
        assert calm.intensity < 0.34
        assert calm.stage == "latent"

        diag = rampancy.diagnostics()["interaction_dynamics"]
        assert diag["streak_sign"] == -1
        assert diag["streak_count"] == 100
        assert diag["minimum_intensity"] == 0.05
        assert diag["last_delta"] < 0.0

        before_bad = rampancy.intensity
        escalated = rampancy.register_stimulus("negative_reward", 1.0)
        assert escalated.intensity > before_bad
        diag = rampancy.diagnostics()["interaction_dynamics"]
        assert diag["streak_sign"] == 1
        assert diag["streak_count"] == 1

    print("RAMPANCY SOCIAL DYNAMICS TEST OK")


if __name__ == "__main__":
    main()
