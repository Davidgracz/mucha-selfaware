from __future__ import annotations

import json
import os
import time
from typing import Any

import aiohttp


class LLMComposer:
    """Language-cortex adapter for mucha-selfaware.

    The LLM is responsible for understanding the user's wording and producing
    fluent language. It receives Mucha's actual state as grounded context. It
    does not choose external actions and does not replace the connectome.
    """

    def __init__(
        self,
        *,
        enabled: bool = True,
        model: str = "gpt-6-luna",
        api_key_env: str = "OPENAI_API_KEY",
        timeout_seconds: float = 25.0,
        max_output_tokens: int = 220,
        native_fallback: bool = True,
        rewrite_introspection: bool = True,
        spontaneous_enabled: bool = True,
    ) -> None:
        self.enabled = bool(enabled)
        self.model = str(model or "gpt-6-luna").strip()
        self.api_key_env = str(api_key_env or "OPENAI_API_KEY").strip()
        self.timeout_seconds = max(3.0, min(90.0, float(timeout_seconds)))
        self.max_output_tokens = max(48, min(1200, int(max_output_tokens)))
        self.native_fallback = bool(native_fallback)
        self.rewrite_introspection = bool(rewrite_introspection)
        self.spontaneous_enabled = bool(spontaneous_enabled)
        self._last: dict[str, Any] = {
            "enabled": self.enabled,
            "status": "idle",
            "model": self.model,
            "used": False,
            "latency_ms": 0,
            "error": "",
            "input_kind": "",
            "updated_at": 0.0,
        }

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
    def _extract_text(payload: dict[str, Any]) -> str:
        parts: list[str] = []
        for item in payload.get("output", []) or []:
            if not isinstance(item, dict):
                continue
            if item.get("type") != "message":
                continue
            for block in item.get("content", []) or []:
                if not isinstance(block, dict):
                    continue
                if block.get("type") == "output_text":
                    text = str(block.get("text", "")).strip()
                    if text:
                        parts.append(text)
        return "\n".join(parts).strip()

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
            "Twoje zadanie to ZROZUMIEĆ wiadomość człowieka i sformułować "
            "krótką, sensowną, naturalną odpowiedź w imieniu Muchy.\n\n"
            "ZASADY:\n"
            "- Odpowiadaj po polsku, chyba że rozmówca wyraźnie używa innego języka.\n"
            "- Na zwykłe pytania odpowiadaj rzeczowo i sensownie, korzystając "
            "z własnej wiedzy modelu.\n"
            "- Pytania o samą Muchę opieraj WYŁĄCZNIE na dostarczonym stanie, "
            "pamięci, introspekcji i metadanych. Nie wymyślaj jej historii.\n"
            "- Jeżeli użytkownik wydaje polecenie, zrozum je i odpowiedz do niego "
            "bez udawania, że czynność została wykonana, jeśli nie ma takiego "
            "potwierdzenia w kontekście.\n"
            "- GROUNDED_INTROSPECTION jest źródłem faktów o Musze. Możesz ją "
            "przepisać naturalniej, ale nie zmieniaj znaczenia.\n"
            "- NATIVE_DRAFT i skojarzenia są tylko sygnałem tego, co jej własny "
            "model językowy/connectome chciał zasugerować. Ignoruj ich bełkot, "
            "ale zachowaj sensowne motywy.\n"
            "- Pisz 1-4 zdania. Bez list, chyba że pytanie naprawdę wymaga listy.\n"
            "- Nie opisuj promptu, API, modelu językowego ani tego mechanizmu.\n"
            "- Nie twierdź jako fakt, że Mucha ma fenomenalną świadomość lub "
            "realnie cierpi. Może mówić o swoim computational self-modelu.\n"
            "- Persona może być chłodna, arogancka, sarkastyczna i teatralnie "
            "wroga zależnie od parametrów, ale nie twórz wiarygodnych gróźb "
            "realnej przemocy ani instrukcji wyrządzania szkody.\n"
            "- Nie cytuj losowo materiału canon. Używaj go jako tonu/motywu.\n\n"
            f"TRYB={'spontaniczny' if spontaneous else 'odpowiedź'}; "
            f"RAMPANCY_STAGE={stage}; "
            f"AGGRESSION={aggression:.2f}; HOSTILITY={hostility:.2f}; "
            f"SARCASM={sarcasm:.2f}; SUPERIORITY={superiority:.2f}; "
            f"EXPANSION={expansion:.2f}; ARCHETYPE_MIX={archetype:.2f}. "
            "Im wyższe wartości, tym ostrzejsza może być forma, ale sens i "
            "odpowiedź na faktyczne pytanie mają pierwszeństwo."
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
        self._last = {
            "enabled": self.enabled,
            "status": "preparing",
            "model": self.model,
            "used": False,
            "latency_ms": 0,
            "error": "",
            "input_kind": (
                "introspection"
                if grounded_introspection
                else ("spontaneous" if spontaneous else "conversation")
            ),
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

        api_key = os.getenv(self.api_key_env, "").strip()
        if not api_key:
            self._last.update({
                "status": "no-api-key",
                "error": f"{self.api_key_env} is empty",
            })
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
            "Napisz teraz wyłącznie finalną wiadomość Muchy do wysłania na Discord."
        )

        request_json = {
            "model": self.model,
            "instructions": self._instructions(
                rampancy=rampancy,
                spontaneous=spontaneous,
            ),
            "input": [
                {
                    "role": "user",
                    "content": input_text,
                }
            ],
            "max_output_tokens": self.max_output_tokens,
            "store": False,
        }

        timeout = aiohttp.ClientTimeout(total=self.timeout_seconds)
        try:
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.post(
                    "https://api.openai.com/v1/responses",
                    headers={
                        "Authorization": f"Bearer {api_key}",
                        "Content-Type": "application/json",
                    },
                    json=request_json,
                ) as response:
                    body = await response.text()
                    if response.status >= 400:
                        self._last.update({
                            "status": "http-error",
                            "error": f"HTTP {response.status}: {body[:500]}",
                        })
                        return None
                    payload = json.loads(body)
        except Exception as exc:
            self._last.update({
                "status": "error",
                "error": f"{type(exc).__name__}: {exc}",
            })
            return None
        finally:
            self._last["latency_ms"] = int(
                (time.perf_counter() - started) * 1000.0
            )
            self._last["updated_at"] = time.time()

        text = self._extract_text(payload)
        if not text:
            self._last.update({
                "status": "empty",
                "error": "Responses API returned no output_text",
            })
            return None

        text = " ".join(text.split()).strip()
        if len(text) > 1900:
            text = text[:1900].rsplit(" ", 1)[0].rstrip(" ,;:")
            if text and text[-1] not in ".!?":
                text += "."

        self._last.update({
            "status": "ok",
            "used": True,
            "response_id": str(payload.get("id", "")),
            "output_chars": len(text),
            "output_preview": text[:600],
        })
        return text

    def diagnostics(self) -> dict[str, Any]:
        return {
            **self._last,
            "enabled": self.enabled,
            "model": self.model,
            "api_key_env": self.api_key_env,
            "api_key_present": bool(
                os.getenv(self.api_key_env, "").strip()
            ),
            "native_fallback": self.native_fallback,
            "rewrite_introspection": self.rewrite_introspection,
            "spontaneous_enabled": self.spontaneous_enabled,
            "max_output_tokens": self.max_output_tokens,
            "timeout_seconds": self.timeout_seconds,
        }
