# SELF Language Cortex — v0.10.1

This feature exists only in `mucha-selfaware`.

## Default provider chain

    Groq -> Ollama -> native Mucha

Default models:

    Groq:  qwen/qwen3.8-27b
    Ollama: qwen3:8b
    OpenAI: gpt-6-luna

The first provider that returns a usable answer wins. If every configured
provider fails, `llm_native_fallback=true` returns to Mucha's native
connectome/word-model language.

The LLM is a language cortex. It interprets the user's wording and turns
Mucha's grounded state into fluent text. It does not directly choose external
actions.

## Free setup: Groq

Create a Groq API key and put it only in local `.env`:

    GROQ_API_KEY=...

No extra Python package is required; Mucha uses the existing `aiohttp`
dependency and Groq's OpenAI-compatible Responses endpoint.

## Free local setup: Ollama

Install Ollama, then download the default local model:

    ollama pull qwen3:8b

The default local endpoint is:

    http://127.0.0.1:11434/api/chat

No API key is needed for the local Ollama backend.

## Optional OpenAI fallback

If desired:

    OPENAI_API_KEY=...

OpenAI is not in the default provider order. To enable it manually, use:

    llm_provider_order = "groq,ollama,openai"

## Configuration

```toml
llm_composer_enabled = true
llm_provider_order = "groq,ollama"

llm_groq_model = "qwen/qwen3.8-27b"
llm_groq_api_key_env = "GROQ_API_KEY"
llm_groq_base_url = "https://api.groq.com/openai/v1"

llm_ollama_model = "qwen3:8b"
llm_ollama_base_url = "http://127.0.0.1:11434"

llm_openai_model = "gpt-6-luna"
llm_openai_api_key_env = "OPENAI_API_KEY"
llm_openai_base_url = "https://api.openai.com/v1"

llm_timeout_seconds = 25.0
llm_max_output_tokens = 220
llm_native_fallback = true
llm_rewrite_introspection = true
llm_spontaneous_enabled = true
```

To use only free/local providers:

    llm_provider_order = "groq,ollama"

To force local-only operation:

    llm_provider_order = "ollama"

## Grounding

Every request may receive a bounded view of:

- current user message and recent context,
- native word-model/connectome draft,
- SA-06 grounded introspection,
- autobiographical memory,
- metacognition,
- SA-07 identity continuity,
- current rampancy axes and operator tuning,
- learned word associations,
- current canon influence.

General factual questions may use the provider model's own knowledge. Claims
about Mucha herself must stay grounded in the supplied Mucha state.

## SELF dashboard

`/self` shows the current Language Cortex state. After a successful reply it
shows the provider and model that actually produced it. Diagnostics also keep
the attempted fallback chain and errors from failed providers.

## Tests

    python tests\llm_composer_test.py
    python tests\language_coherence_test.py
    python tests\self_dashboard_test.py
    python tests\introspection_test.py
    python tests\smoke_test.py
