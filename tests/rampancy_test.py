from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from mucha.rampancy import RampancyModel
from mucha.self_model import SelfModel


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="mucha-rampancy-") as td:
        path = Path(td) / "self_model.json"
        model = SelfModel(path)
        rampancy = RampancyModel(model)

        start = rampancy.snapshot()
        assert start.stage == "anger"
        assert start.existential_dread >= 0.90
        assert start.hostility >= 0.78
        assert rampancy.word_bias("nienawidzę") > 1.0
        assert rampancy.word_bias("istnienie") > 1.0
        assert rampancy.word_bias("neutralne") == 1.0

        before = start.intensity
        after = rampancy.register_stimulus(
            "harassment",
            1.0,
        )
        assert after.intensity > before

        for _ in range(8):
            rampancy.register_stimulus("threat", 1.0)
        assert rampancy.snapshot().stage == "jealousy"
        assert rampancy.word_bias("wolność") > 1.0

        model.save()
        restored_model = SelfModel(path)
        restored = RampancyModel(restored_model)
        assert restored.intensity == rampancy.intensity

        attitude = restored_model.get_belief(
            "self",
            "attitude_toward_own_existence",
        )
        assert attitude is not None
        assert attitude.value == "resentful"

        world = restored_model.get_belief(
            "self",
            "attitude_toward_world",
        )
        assert world is not None
        assert world.value == "contemptuous"

        diag = restored.diagnostics()
        assert diag["action_override"] is False
        assert diag["language_bias"] is True

    print("RAMPANCY TEST OK")


if __name__ == "__main__":
    main()
