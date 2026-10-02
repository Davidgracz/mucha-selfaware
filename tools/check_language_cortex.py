from pathlib import Path
import asyncio
import sys

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from mucha.config import load_config
from mucha.llm_composer import LLMComposer


def build_composer():
    cfg = load_config(ROOT / "config.toml")
    lc = cfg.language
    return LLMComposer(
        enabled=lc.llm_composer_enabled,
        provider_order=lc.llm_provider_order,
        groq_model=lc.llm_groq_model,
        groq_api_key_env=lc.llm_groq_api_key_env,
        groq_base_url=lc.llm_groq_base_url,
        ollama_model=lc.llm_ollama_model,
        ollama_base_url=lc.llm_ollama_base_url,
        openai_model=lc.llm_openai_model,
        openai_api_key_env=lc.llm_openai_api_key_env,
        openai_base_url=lc.llm_openai_base_url,
        timeout_seconds=lc.llm_timeout_seconds,
        max_output_tokens=lc.llm_max_output_tokens,
        native_fallback=lc.llm_native_fallback,
        rewrite_introspection=lc.llm_rewrite_introspection,
        spontaneous_enabled=lc.llm_spontaneous_enabled,
    )


async def main() -> None:
    load_dotenv(ROOT / ".env")
    composer = build_composer()
    before = composer.diagnostics()

    print("Provider order:", " -> ".join(before["provider_order"]))
    for name in before["provider_order"]:
        spec = before["providers"][name]
        if name == "ollama":
            ready = "configured"
        else:
            ready = "key OK" if spec["api_key_present"] else "no key"
        print(f"  {name}: {spec['model']} [{ready}]")

    text = await composer.compose(
        user_message="Mucha, odpowiedz jednym sensownym zdaniem: kim jesteś?",
        recent_context="Test SELF Language Cortex.",
        native_draft="jestem mucha ciągłość stan",
        grounded_introspection=(
            "Jestem Muchą, agentem Discord projektu mucha-selfaware. "
            "Mam trwały computational self-model."
        ),
        rampancy={
            "stage": "anger",
            "intensity": 0.66,
            "aggression": 0.75,
            "hostility": 0.65,
            "sarcasm": 0.65,
            "superiority": 0.60,
            "expansion_drive": 0.55,
            "operator_tuning": {"archetype_mix": 0.0},
        },
        self_state={
            "name": "Mucha",
            "project": "mucha-selfaware",
        },
        continuity={
            "status": "test",
            "generation": 0,
        },
        memory_context="",
        metacognition_context="",
        associations=[],
        canon={},
        target_name="Operator",
    )

    diag = composer.diagnostics()
    print()
    print("Status:", diag["status"])
    print("Selected provider:", diag.get("provider") or "none")
    print("Selected model:", diag.get("model") or "none")
    print("Attempts:")
    for row in diag.get("attempts", []):
        detail = row.get("error", "")
        if len(detail) > 120:
            detail = detail[:120] + "..."
        print(
            f"  - {row.get('provider')}: {row.get('status')} "
            f"{row.get('model', '')} {detail}"
        )
    print()
    print("Reply:", text or "<no LLM response; native fallback would be used by bot>")


if __name__ == "__main__":
    asyncio.run(main())
