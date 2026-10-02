from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from mucha.rampancy import RampancyModel
from mucha.self_model import SelfModel


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="mucha-self-ui-") as td:
        root = Path(td)
        model = SelfModel(root / "self_model.json")
        rampancy = RampancyModel(model, initial_intensity=0.66)

        base = rampancy.snapshot()
        assert base.stage == "anger"

        tuned = rampancy.set_operator_tuning({
            "aggression": -0.20,
            "sarcasm": 0.10,
            "expansion_drive": 0.15,
            "archetype_mix": 1.0,
        })
        assert tuned.aggression < base.aggression
        assert tuned.sarcasm >= base.sarcasm
        assert tuned.expansion_drive >= base.expansion_drive

        rampancy.set_intensity(0.90)
        high = rampancy.snapshot()
        assert high.stage == "jealousy"

        restored_model = SelfModel(root / "self_model.json")
        restored = RampancyModel(restored_model)
        restored_diag = restored.diagnostics()
        assert restored_diag["operator_tuning"]["archetype_mix"] == 1.0
        assert restored_diag["operator_tuning"]["aggression"] == -0.20

        restored.reset_operator_tuning()
        reset = restored.diagnostics()["operator_tuning"]
        assert all(abs(float(v)) < 1e-9 for v in reset.values())

    web_source = (ROOT / "mucha" / "web_ui.py").read_text(encoding="utf-8")
    bot_source = (ROOT / "mucha" / "discord_bot.py").read_text(encoding="utf-8")

    assert 'SELF_HTML = r"""' in web_source
    assert 'app.router.add_get("/self", self._self_page)' in web_source
    assert 'app.router.add_get("/api/self", self._self_state)' in web_source
    assert 'app.router.add_post("/api/self", self._self_update)' in web_source
    assert "Rampancy intensity" in web_source
    assert "Archetyp" in web_source
    assert "Słownik / Language Brain" in web_source
    assert "selfaware_provider=self._selfaware_dashboard_snapshot" in bot_source
    assert "selfaware_updater=self._dashboard_update_selfaware" in bot_source

    print("SELF DASHBOARD TEST OK")


if __name__ == "__main__":
    main()
