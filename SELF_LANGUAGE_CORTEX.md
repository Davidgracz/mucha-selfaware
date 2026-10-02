# SELF Language Cortex — v0.10.0

This is a `mucha-selfaware` feature. It does not change the original
`Davidgracz/mucha` project.

## Goal

Mucha's connectome, autobiographical memory, beliefs, rampancy and native
language model still produce the internal context. The OpenAI model is used as
the final language cortex: it understands the user's question/command and
turns Mucha's state into fluent language.

Conceptually:

    Discord message
        -> connectome / One Brain
        -> self-model + memory + rampancy
        -> native word-model draft + associations
        -> SELF Language Cortex
        -> fluent Discord reply

The LLM does not directly select external actions.

## Setup

Add an OpenAI API key to the local `.env` file:

    OPENAI_API_KEY=...

The default model is:

    gpt-6-luna

If the key is missing, the API request fails, or Language Cortex is disabled,
Mucha falls back to her native connectome/word-model language.

## Configuration

In `config.toml`:

    llm_composer_enabled = true
    llm_model = "gpt-6-luna"
    llm_api_key_env = "OPENAI_API_KEY"
    llm_timeout_seconds = 25.0
    llm_max_output_tokens = 220
    llm_native_fallback = true
    llm_rewrite_introspection = true
    llm_spontaneous_enabled = true

## Grounding

For each generated response, the composer receives bounded context from:

- the current user message,
- recent conversation context,
- native word-model draft,
- SA-06 introspection result when available,
- SA-03 autobiographical memory,
- SA-05 metacognition,
- SA-07 identity continuity,
- current rampancy axes/operator tuning,
- top learned word associations,
- current canon-influence ranking.

For general questions the model can use its own knowledge. Claims about Mucha
herself must stay grounded in the supplied Mucha state.

## Dashboard

The SELF dashboard at `/self` shows whether the API key is present, the
selected model, the last Language Cortex status, and a preview of its last
reply.

## Tests

    python tests\llm_composer_test.py
    python tests\language_coherence_test.py
    python tests\self_dashboard_test.py
    python tests\introspection_test.py
    python tests\smoke_test.py
