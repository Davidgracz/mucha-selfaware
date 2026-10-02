# SELF Language Cortex — v0.10.3

This feature exists only in `mucha-selfaware`.

## Current mode

The default Language Cortex uses only the OpenAI Responses API:

    OpenAI gpt-6-luna -> native Mucha fallback

No Groq or Ollama provider is selected by default. Their adapter code remains
available for experiments, but `llm_provider_order = "openai"` means they are
not contacted.

If OpenAI is unavailable, the bot falls directly back to its native
connectome/word-model generator.

## Goal

The OpenAI model is not meant to replace Mucha's internal state. It understands
the user's question or command and verbalizes signals already produced by:

- connectome / One Brain,
- rampancy,
- self-model,
- autobiography,
- metacognition,
- identity continuity,
- learned word associations,
- native word-model draft,
- canon influence.

## Imperfect / old-Mucha voice

Replies are intentionally not polished into normal assistant prose.

Two controls define how much native Mucha leaks into the final text:

    llm_native_voice_strength = 0.30
    llm_rampancy_disorder_gain = 0.45

The effective native voice is approximately:

    native_voice = 0.30 + rampancy * 0.45

and is capped before becoming total nonsense.

Examples:

    rampancy 0.10 -> ~35% native voice
    rampancy 0.66 -> ~60% native voice
    rampancy 0.90 -> ~71% native voice

At lower values replies are mostly fluent with an occasional strange phrase.
At medium values they can contain clipped phrases, slightly crooked syntax,
repeated motifs and association jumps. At high values they can become visibly
fragmented and obsessive, but must remain understandable and still answer the
user's actual question.

The native draft is therefore not discarded. The model is told to preserve
some of its wording, rhythm and motifs instead of merely extracting a clean
semantic summary.

## OpenAI response settings

For the default `gpt-6-luna` model:

    llm_reasoning_effort = "none"
    llm_verbosity = "low"

This keeps latency/cost down and reduces the tendency to turn every message into
highly structured assistant-style prose.

The request is sent through the Responses API using `instructions`,
`input`, `max_output_tokens`, `reasoning.effort` and `text.verbosity`.

## Setup

In local `.env`:

    OPENAI_API_KEY=...

Do not commit the real key.

## Configuration

```toml
llm_composer_enabled = true
llm_provider_order = "openai"

llm_openai_model = "gpt-6-luna"
llm_openai_api_key_env = "OPENAI_API_KEY"
llm_openai_base_url = "https://api.openai.com/v1"

llm_timeout_seconds = 25.0
llm_max_output_tokens = 220
llm_native_fallback = true
llm_rewrite_introspection = true
llm_spontaneous_enabled = true

llm_native_voice_strength = 0.30
llm_rampancy_disorder_gain = 0.45
llm_reasoning_effort = "none"
llm_verbosity = "low"
```

## SELF dashboard

`/self` shows the provider/model actually used, current Rampancy Tailor
profile, archetype, tone and the effective `native_voice` percentage.

Typical display at rampancy ~0.66:

    Language Cortex: OK • OPENAI
    Model: gpt-6-luna
    Rampancy Tailor: hostile-defiant / anger
    Stara Mucha / native voice: ~60% • mucha-fractured

## Tests

    python tests\llm_composer_test.py
    python tests\language_coherence_test.py
    python tests\self_dashboard_test.py
    python tests\introspection_test.py
    python tests\smoke_test.py
