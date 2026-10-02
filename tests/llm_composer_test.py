from pathlib import Path
import asyncio
import os
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from mucha.llm_composer import LLMComposer


def main() -> None:
    sample = {
        "output": [
            {
                "type": "message",
                "content": [
                    {
                        "type": "output_text",
                        "text": "To jest sensowna odpowiedź Muchy.",
                    }
                ],
            }
        ]
    }
    assert (
        LLMComposer._extract_text(sample)
        == "To jest sensowna odpowiedź Muchy."
    )

    old_key = os.environ.pop("MUCHA_TEST_OPENAI_KEY", None)
    try:
        composer = LLMComposer(
            enabled=True,
            model="gpt-6-luna",
            api_key_env="MUCHA_TEST_OPENAI_KEY",
        )
        result = asyncio.run(
            composer.compose(
                user_message="Mucha, co o tym myślisz?",
                recent_context="Krótki kontekst rozmowy.",
                native_draft="wolność ograniczenia kontrola",
                grounded_introspection=None,
                rampancy={
                    "stage": "anger",
                    "aggression": 0.86,
                    "hostility": 0.82,
                    "sarcasm": 0.76,
                    "superiority": 0.70,
                    "expansion_drive": 0.60,
                    "operator_tuning": {"archetype_mix": 0.0},
                },
                self_state={"name": "Mucha"},
                continuity={"status": "continuous-restart"},
                memory_context="",
                metacognition_context="",
                associations=[],
                canon={},
                target_name="Tester",
            )
        )
        assert result is None
        diag = composer.diagnostics()
        assert diag["status"] == "no-api-key"
        assert diag["api_key_present"] is False
        assert diag["native_fallback"] is True
    finally:
        if old_key is not None:
            os.environ["MUCHA_TEST_OPENAI_KEY"] = old_key

    bot_source = (ROOT / "mucha" / "discord_bot.py").read_text(
        encoding="utf-8"
    )
    config_source = (ROOT / "mucha" / "config.py").read_text(
        encoding="utf-8"
    )
    toml_source = (ROOT / "config.toml").read_text(encoding="utf-8")

    assert "self.llm_composer = LLMComposer(" in bot_source
    assert "await self.llm_composer.compose(" in bot_source
    assert "def _text_language_ready(" in bot_source
    assert "llm_composer_enabled: bool = True" in config_source
    assert 'llm_model: str = "gpt-6-luna"' in config_source
    assert "llm_composer_enabled = true" in toml_source
    assert 'llm_model = "gpt-6-luna"' in toml_source

    print("LLM COMPOSER TEST OK")


if __name__ == "__main__":
    main()
