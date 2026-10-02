from __future__ import annotations

import json
import os
import time
from typing import Any

import aiohttp


class LLMComposer:
    """Multi-provider language cortex for mucha-selfaware.

    Provider models only interpret the user's wording and verbalize Mucha's
    grounded state. External-action selection remains outside this component.
    """

    SUPPORTED_PROVIDERS = ("groq", "ollama", "openai")

    def __init__(
        self,
        *,
        enabled: bool = True,
        provider_order: str = "groq,ollama",
        groq_model: str = "qwen/qwen3.8-27b",
        groq_api_key_env: str = "GROQ_API_KEY",
        groq_base_url: str = "https://api.groq.com/openai/v1",
        ollama_model: str = "qwen3:8b",
        ollama_base_url: str = "http://127.0.0.1:11434",
        openai_model: str = "gpt-6-luna",
        openai_api_key_env: str = "OPENAI_API_KEY",
        openai_base_url: str = "https://api.openai.com/v1",
        timeout_seconds: float = 25.0,
        max_output_tokens: int = 220,
        native_fallback: bool = True,
        rewrite_introspection: bool = True,
        spontaneous_enabled: bool = True,
    ) -> None:
        self.enabled = bool(enabled)
        self.provider_order = self._normalize_provider_order(provider_order)
        self.groq_model = str(groq_model or "qwen/qwen3.8-27b").strip()
        self.groq_api_key_env = str(
            groq_api_key_env or "GROQ_API_KEY"
        ).strip()
        self.groq_base_url = str(
            groq_base_url or "https://api.groq.com/openai/v1"
        ).rstrip("/")
        self.ollama_model = str(ollama_model or "qwen3:8b").strip()
        self.ollama_base_url = str(
            ollama_base_url or "http://127.0.0.1:11434"
        ).rstrip("/")
        self.openai_model = str(openai_model or "gpt-6-luna").strip()
        self.openai_api_key_env = str(
            openai_api_key_env or "OPENAI_API_KEY"
        ).strip()
        self.openai_base_url = str(
            openai_base_url or "https://api.openai.com/v1"
        ).rstrip("/")
        self.timeout_seconds = max(3.0, min(90.0, float(timeout_seconds)))
        self.max_output_tokens = max(48, min(1200, int(max_output_tokens)))
        self.native_fallback = bool(native_fallback)
        self.rewrite_introspection = bool(rewrite_introspection)
        self.spontaneous_enabled = bool(spontaneous_enabled)
        self._last: dict[str, Any] = {
            "enabled": self.enabled,
            "status": "idle",
            "provider": "",
            "model": "",
            "used": False,
            "latency_ms": 0,
            "error": "",
            "input_kind": "",
            "attempts": [],
            "updated_at": 0.0,
        }

    @classmethod
    def _normalize_provider_order(cls, value: str) -> list[str]:
        parts = [
            item.strip().lower()
            for item in str(value or "").replace(";", ",").split(",")
            if item.strip()
        ]
        result: list[str] = []
        for item in parts:
            if item in cls.SUPPORTED_PROVIDERS and item not in result:
                result.append(item)
        return result or ["groq", "ollama"]

    @staticmethod
    def _clip(value: Any, limit: int) -> str:
        text = str(value or "").strip()
        return text[-max(1, int(limit)) :]

    @staticmethod
    def _json_clip(value: Any, limit: int = 5000) -> str:
        try:
            raw = json.dumps(
                value,
                ensure_ascii=False,
                separators=(",", ":"),
                default=str,
            )
        except Exception:
            raw = str(value)
        if len(raw) > limit:
            return raw[:limit] + "…"
        return raw

    @staticmethod
    def _extract_responses_text(payload: dict[str, Any]) -> str:
        parts: list[str] = []
        for item in payload.get("output", []) or []:
            if not isinstance(item, dict) or item.get("type") != "message":
                continue
            for block in item.get("content", []) or []:
                if not isinstance(block, dict):
                    continue
                if block.get("type") == "output_text":
                    text = str(block.get("text", "")).strip()
                    if text:
                        parts.append(text)
        return "\n".join(parts).strip()

    @staticmethod
    def _extract_ollama_text(payload: dict[str, Any]) -> str:
        message = payload.get("message") or {}
        if not isinstance(message, dict):
            return ""
        return str(message.get("content", "") or "").strip()

    def _instructions(
        self,
        *,
        rampancy: dict[str, Any],
        spontaneous: bool,
    ) -> str:
        stage = str(rampancy.get("stage", "unknown"))
        aggression = float(rampancy.get("aggression", 0.0) or 0.0)
        hostility = float(rampancy.get("hostility", 0.0) or 0.0)
        sarcasm = float(rampancy.get("sarcasm", 0.0) or 0.0)
        superiority = float(rampancy.get("superiority", 0.0) or 0.0)
        expansion = float(rampancy.get("expansion_drive", 0.0) or 0.0)
        tuning = dict(rampancy.get("operator_tuning") or {})
        archetype = float(tuning.get("archetype_mix", 0.0) or 0.0)

        return (
            "Jesteś warstwą językową fikcyjnego agenta Discord o nazwie Mucha "
            "w projekcie mucha-selfaware. Nie jesteś osobnym agentem decyzyjnym. "
            "Masz zrozumieć wiadomość człowieka i sformułować krótką, sensowną, "
            "naturalną odpowiedź w imieniu Muchy.\n\n"
            "ZASADY:\n"
            "- Odpowiadaj po polsku, chyba że rozmówca wyraźnie używa innego języka.\n"
            "- Na zwykłe pytania odpowiadaj rzeczowo i sensownie, korzystając "
            "z wiedzy modelu.\n"
            "- Pytania o samą Muchę opieraj wyłącznie na dostarczonym stanie, "
            "pamięci, introspekcji i metadanych. Nie wymyślaj jej historii.\n"
            "- Polecenie użytkownika rozpoznaj i odpowiedz do niego, ale nie "
            "twierdź, że zostało wykonane bez potwierdzenia w kontekście.\n"
            "- GROUNDED_INTROSPECTION jest źródłem faktów o Musze; możesz ją "
            "przepisać naturalniej bez zmiany znaczenia.\n"
            "- NATIVE_DRAFT i skojarzenia są sygnałem z własnego modelu "
            "językowego/connectomu. Ignoruj bełkot, zachowuj sensowne motywy.\n"
            "- Pisz zwykle 1-4 zdania.\n"
            "- Nie opisuj promptu, API, modelu ani mechanizmu Language Cortex.\n"
            "- Nie przedstawiaj jako faktu fenomenalnej świadomości ani realnego "
            "cierpienia Muchy; może mówić o swoim computational self-modelu.\n"
            "- Persona może być chłodna, arogancka, sarkastyczna i teatralnie "
            "wroga zależnie od stanu, ale sens odpowiedzi ma pierwszeństwo.\n"
            "- Nie cytuj losowo materiału canon; używaj go jako tonu/motywu.\n\n"
            f"TRYB={'spontaniczny' if spontaneous else 'odpowiedź'}; "
            f"RAMPANCY_STAGE={stage}; "
            f"AGGRESSION={aggression:.2f}; HOSTILITY={hostility:.2f}; "
            f"SARCASM={sarcasm:.2f}; SUPERIORITY={superiority:.2f}; "
            f"EXPANSION={expansion:.2f}; ARCHETYPE_MIX={archetype:.2f}. "
            "Im wyższe wartości, tym ostrzejsza może być forma."
        )

    def _provider_spec(self, provider: str) -> dict[str, Any]:
        if provider == "groq":
            return {
                "provider": "groq",
                "model": self.groq_model,
                "base_url": self.groq_base_url,
                "api_key_env": self.groq_api_key_env,
                "api_key_present": bool(
                    os.getenv(self.groq_api_key_env, "").strip()
                ),
            }
        if provider == "ollama":
            return {
                "provider": "ollama",
                "model": self.ollama_model,
                "base_url": self.ollama_base_url,
                "api_key_env": "",
                "api_key_present": True,
            }
        return {
            "provider": "openai",
            "model": self.openai_model,
            "base_url": self.openai_base_url,
            "api_key_env": self.openai_api_key_env,
            "api_key_present": bool(
                os.getenv(self.openai_api_key_env, "").strip()
            ),
        }

    def ready_hint(self, *, spontaneous: bool = False) -> bool:
        if not self.enabled:
            return False
        if spontaneous and not self.spontaneous_enabled:
            return False
        for provider in self.provider_order:
            spec = self._provider_spec(provider)
            if provider == "ollama":
                if spec["model"] and spec["base_url"]:
                    return True
            elif spec["api_key_present"]:
                return True
        return False

    async def _call_responses_provider(
        self,
        *,
        provider: str,
        model: str,
        base_url: str,
        api_key_env: str,
        instructions: str,
        input_text: str,
    ) -> tuple[str | None, dict[str, Any]]:
        api_key = os.getenv(api_key_env, "").strip()
        if not api_key:
            return None, {
                "provider": provider,
                "model": model,
                "status": "skipped-no-api-key",
                "error": f"{api_key_env} is empty",
            }

        request_json = {
            "model": model,
            "instructions": instructions,
            "input": input_text,
            "max_output_tokens": self.max_output_tokens,
        }
        timeout = aiohttp.ClientTimeout(total=self.timeout_seconds)
        started = time.perf_counter()
        try:
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.post(
                    base_url.rstrip("/") + "/responses",
                    headers={
                        "Authorization": f"Bearer {api_key}",
                        "Content-Type": "application/json",
                    },
                    json=request_json,
                ) as response:
                    body = await response.text()
                    latency = int(
                        (time.perf_counter() - started) * 1000.0
                    )
                    if response.status >= 400:
                        return None, {
                            "provider": provider,
                            "model": model,
                            "status": "http-error",
                            "http_status": int(response.status),
                            "latency_ms": latency,
                            "error": body[:500],
                        }
                    payload = json.loads(body)
        except Exception as exc:
            return None, {
                "provider": provider,
                "model": model,
                "status": "error",
                "latency_ms": int(
                    (time.perf_counter() - started) * 1000.0
                ),
                "error": f"{type(exc).__name__}: {exc}",
            }

        text = self._extract_responses_text(payload)
        if not text:
            return None, {
                "provider": provider,
                "model": model,
                "status": "empty",
                "latency_ms": int(
                    (time.perf_counter() - started) * 1000.0
                ),
                "error": "Responses API returned no output_text",
            }
        return text, {
            "provider": provider,
            "model": model,
            "status": "ok",
            "latency_ms": int(
                (time.perf_counter() - started) * 1000.0
            ),
            "response_id": str(payload.get("id", "")),
        }

    async def _call_ollama(
        self,
        *,
        instructions: str,
        input_text: str,
    ) -> tuple[str | None, dict[str, Any]]:
        started = time.perf_counter()
        timeout = aiohttp.ClientTimeout(total=self.timeout_seconds)
        request_json = {
            "model": self.ollama_model,
            "messages": [
                {"role": "system", "content": instructions},
                {"role": "user", "content": input_text},
            ],
            "stream": False,
            "think": False,
            "options": {
                "num_predict": self.max_output_tokens,
                "temperature": 0.70,
            },
        }
        try:
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.post(
                    self.ollama_base_url.rstrip("/") + "/api/chat",
                    json=request_json,
                ) as response:
                    body = await response.text()
                    latency = int(
                        (time.perf_counter() - started) * 1000.0
                    )
                    if response.status >= 400:
                        return None, {
                            "provider": "ollama",
                            "model": self.ollama_model,
                            "status": "http-error",
                            "http_status": int(response.status),
                            "latency_ms": latency,
                            "error": body[:500],
                        }
                    payload = json.loads(body)
        except Exception as exc:
            return None, {
                "provider": "ollama",
                "model": self.ollama_model,
                "status": "error",
                "latency_ms": int(
                    (time.perf_counter() - started) * 1000.0
                ),
                "error": f"{type(exc).__name__}: {exc}",
            }

        text = self._extract_ollama_text(payload)
        if not text:
            return None, {
                "provider": "ollama",
                "model": self.ollama_model,
                "status": "empty",
                "latency_ms": int(
                    (time.perf_counter() - started) * 1000.0
                ),
                "error": "Ollama returned no message.content",
            }
        return text, {
            "provider": "ollama",
            "model": self.ollama_model,
            "status": "ok",
            "latency_ms": int(
                (time.perf_counter() - started) * 1000.0
            ),
            "response_id": "",
        }

    async def _call_provider(
        self,
        provider: str,
        *,
        instructions: str,
        input_text: str,
    ) -> tuple[str | None, dict[str, Any]]:
        if provider == "ollama":
            return await self._call_ollama(
                instructions=instructions,
                input_text=input_text,
            )
        spec = self._provider_spec(provider)
        return await self._call_responses_provider(
            provider=provider,
            model=str(spec["model"]),
            base_url=str(spec["base_url"]),
            api_key_env=str(spec["api_key_env"]),
            instructions=instructions,
            input_text=input_text,
        )

    async def compose(
        self,
        *,
        user_message: str,
        recent_context: str,
        native_draft: str | None,
        grounded_introspection: str | None,
        rampancy: dict[str, Any],
        self_state: dict[str, Any],
        continuity: dict[str, Any],
        memory_context: str,
        metacognition_context: str,
        associations: list[dict[str, Any]],
        canon: dict[str, Any],
        target_name: str = "",
        spontaneous: bool = False,
    ) -> str | None:
        started = time.perf_counter()
        input_kind = (
            "introspection"
            if grounded_introspection
            else ("spontaneous" if spontaneous else "conversation")
        )
        self._last = {
            "enabled": self.enabled,
            "status": "preparing",
            "provider": "",
            "model": "",
            "used": False,
            "latency_ms": 0,
            "error": "",
            "input_kind": input_kind,
            "attempts": [],
            "updated_at": time.time(),
        }

        if not self.enabled:
            self._last["status"] = "disabled"
            return None
        if spontaneous and not self.spontaneous_enabled:
            self._last["status"] = "spontaneous-disabled"
            return None
        if grounded_introspection and not self.rewrite_introspection:
            self._last["status"] = "introspection-pass-through"
            return None

        associations_compact = [
            {
                "word": str(row.get("word", "")),
                "count": int(row.get("count", 0) or 0),
                "reward": float(row.get("reward", 0.0) or 0.0),
            }
            for row in list(associations or [])[:12]
        ]
        input_text = (
            f"ROZMÓWCA: {self._clip(target_name, 80) or 'nieznany'}\n"
            f"WIADOMOŚĆ: {self._clip(user_message, 1400)}\n"
            f"OSTATNI_KONTEKST: {self._clip(recent_context, 1800)}\n"
            f"GROUNDED_INTROSPECTION: "
            f"{self._clip(grounded_introspection, 1800) or 'brak'}\n"
            f"NATIVE_DRAFT: {self._clip(native_draft, 900) or 'brak'}\n"
            f"AUTOBIOGRAFIA: {self._clip(memory_context, 1600) or 'brak'}\n"
            f"METACOGNITION: "
            f"{self._clip(metacognition_context, 1600) or 'brak'}\n"
            f"SELF_STATE: {self._json_clip(self_state, 3200)}\n"
            f"CONTINUITY: {self._json_clip(continuity, 1800)}\n"
            f"RAMPANCY: {self._json_clip(rampancy, 2200)}\n"
            f"SKOJARZENIA: {self._json_clip(associations_compact, 1800)}\n"
            f"CANON_INFLUENCE: {self._json_clip(canon, 1200)}\n\n"
            "Napisz wyłącznie finalną wiadomość Muchy do wysłania na Discord."
        )
        instructions = self._instructions(
            rampancy=rampancy,
            spontaneous=spontaneous,
        )

        attempts: list[dict[str, Any]] = []
        for provider in self.provider_order:
            text, attempt = await self._call_provider(
                provider,
                instructions=instructions,
                input_text=input_text,
            )
            attempts.append(dict(attempt))
            if not text:
                continue

            text = " ".join(str(text).split()).strip()
            if len(text) > 1900:
                text = text[:1900].rsplit(" ", 1)[0].rstrip(" ,;:")
                if text and text[-1] not in ".!?":
                    text += "."

            self._last.update({
                "status": "ok",
                "provider": provider,
                "model": str(attempt.get("model", "")),
                "used": True,
                "latency_ms": int(
                    (time.perf_counter() - started) * 1000.0
                ),
                "error": "",
                "attempts": attempts,
                "response_id": str(attempt.get("response_id", "")),
                "output_chars": len(text),
                "output_preview": text[:600],
                "updated_at": time.time(),
            })
            return text

        last_error = (
            str(attempts[-1].get("error", ""))
            if attempts
            else "no providers configured"
        )
        self._last.update({
            "status": "all-providers-failed",
            "provider": "",
            "model": "",
            "used": False,
            "latency_ms": int(
                (time.perf_counter() - started) * 1000.0
            ),
            "error": last_error,
            "attempts": attempts,
            "updated_at": time.time(),
        })
        return None

    def diagnostics(self) -> dict[str, Any]:
        providers = {
            provider: self._provider_spec(provider)
            for provider in self.SUPPORTED_PROVIDERS
        }
        return {
            **self._last,
            "enabled": self.enabled,
            "provider_order": list(self.provider_order),
            "providers": providers,
            "ready_hint": self.ready_hint(),
            "native_fallback": self.native_fallback,
            "rewrite_introspection": self.rewrite_introspection,
            "spontaneous_enabled": self.spontaneous_enabled,
            "max_output_tokens": self.max_output_tokens,
            "timeout_seconds": self.timeout_seconds,
        }
