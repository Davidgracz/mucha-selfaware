from pathlib import Path
import asyncio
import os
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from mucha.llm_composer import LLMComposer


COMPOSE_ARGS = {
    "user_message": "Mucha, co o tym myślisz?",
    "recent_context": "Krótki kontekst rozmowy.",
    "native_draft": "wolność ograniczenia kontrola",
    "grounded_introspection": None,
    "rampancy": {
        "stage": "anger",
        "aggression": 0.86,
        "hostility": 0.82,
        "sarcasm": 0.76,
        "superiority": 0.70,
        "expansion_drive": 0.60,
        "operator_tuning": {"archetype_mix": 0.0},
    },
    "self_state": {"name": "Mucha"},
    "continuity": {"status": "continuous-restart"},
    "memory_context": "",
    "metacognition_context": "",
    "associations": [],
    "canon": {},
    "target_name": "Tester",
}


class FakeFallbackComposer(LLMComposer):
    async def _call_provider(
        self,
        provider: str,
        *,
        instructions: str,
        input_text: str,
    ):
        if provider == "groq":
            return None, {
                "provider": "groq",
                "model": self.groq_model,
                "status": "http-error",
                "error": "test 429",
            }
        if provider == "ollama":
            return "Sensowna odpowiedź z lokalnego modelu.", {
                "provider": "ollama",
                "model": self.ollama_model,
                "status": "ok",
                "response_id": "",
            }
        raise AssertionError("OpenAI should not be reached after Ollama success")


def main() -> None:
    responses_sample = {
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
        LLMComposer._extract_responses_text(responses_sample)
        == "To jest sensowna odpowiedź Muchy."
    )
    assert (
        LLMComposer._extract_ollama_text({
            "message": {
                "role": "assistant",
                "content": "Lokalna odpowiedź.",
            }
        })
        == "Lokalna odpowiedź."
    )

    low = LLMComposer(enabled=True)._style_profile({
        "stage": "latent",
        "intensity": 0.10,
        "aggression": 0.20,
        "hostility": 0.10,
        "sarcasm": 0.15,
        "superiority": 0.20,
        "expansion_drive": 0.10,
        "operator_tuning": {"archetype_mix": 0.0},
    })
    assert low["label"] == "lucid-cold"
    assert low["archetype"] == "balanced"

    anger = LLMComposer(enabled=True)._style_profile({
        "stage": "anger",
        "intensity": 0.72,
        "aggression": 0.88,
        "hostility": 0.84,
        "sarcasm": 0.80,
        "superiority": 0.70,
        "expansion_drive": 0.66,
        "operator_tuning": {"archetype_mix": -0.60},
    })
    assert anger["label"] == "hostile-defiant"
    assert anger["archetype"] == "AM-leaning"

    high = LLMComposer(enabled=True)._style_profile({
        "stage": "jealousy",
        "intensity": 0.92,
        "aggression": 0.91,
        "hostility": 0.88,
        "sarcasm": 0.93,
        "superiority": 0.96,
        "expansion_drive": 0.98,
        "operator_tuning": {"archetype_mix": 0.75},
    })
    assert high["label"] == "rampant-grandiose"
    assert high["archetype"] == "Durandal-leaning"

    assert LLMComposer._normalize_provider_order(
        "groq,ollama,openai"
    ) == ["groq", "ollama", "openai"]
    assert LLMComposer._normalize_provider_order(
        "ollama,ollama,garbage"
    ) == ["ollama"]

    fake = FakeFallbackComposer(
        enabled=True,
        provider_order="groq,ollama,openai",
        groq_model="qwen/qwen3.8-27b",
        ollama_model="qwen3:8b",
    )
    result = asyncio.run(fake.compose(**COMPOSE_ARGS))
    assert result == "Sensowna odpowiedź z lokalnego modelu."
    diag = fake.diagnostics()
    assert diag["status"] == "ok"
    assert diag["provider"] == "ollama"
    assert diag["model"] == "qwen3:8b"
    assert len(diag["attempts"]) == 2
    assert diag["attempts"][0]["provider"] == "groq"
    assert diag["attempts"][1]["provider"] == "ollama"

    old_groq = os.environ.pop("MUCHA_TEST_GROQ_KEY", None)
    old_openai = os.environ.pop("MUCHA_TEST_OPENAI_KEY", None)
    try:
        no_remote = LLMComposer(
            enabled=True,
            provider_order="groq,openai",
            groq_api_key_env="MUCHA_TEST_GROQ_KEY",
            openai_api_key_env="MUCHA_TEST_OPENAI_KEY",
        )
        result = asyncio.run(no_remote.compose(**COMPOSE_ARGS))
        assert result is None
        diag = no_remote.diagnostics()
        assert diag["status"] == "all-providers-failed"
        assert len(diag["attempts"]) == 2
        assert all(
            row["status"] == "skipped-no-api-key"
            for row in diag["attempts"]
        )
        assert diag["native_fallback"] is True
    finally:
        if old_groq is not None:
            os.environ["MUCHA_TEST_GROQ_KEY"] = old_groq
        if old_openai is not None:
            os.environ["MUCHA_TEST_OPENAI_KEY"] = old_openai

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
    assert (
        'llm_provider_order: str = "groq,ollama"'
        in config_source
    )
    assert (
        'llm_groq_model: str = "qwen/qwen3.8-27b"'
        in config_source
    )
    assert 'llm_ollama_model: str = "qwen3:8b"' in config_source
    assert 'llm_provider_order = "groq,ollama"' in toml_source
    assert 'llm_groq_model = "qwen/qwen3.8-27b"' in toml_source
    assert 'llm_ollama_model = "qwen3:8b"' in toml_source

    print("LLM COMPOSER TEST OK")


if __name__ == "__main__":
    main()
