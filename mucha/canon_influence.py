from __future__ import annotations

from dataclasses import dataclass
import json
import random
import time
from pathlib import Path
from typing import Any


@dataclass(frozen=True, slots=True)
class CanonQuote:
    id: str
    speaker: str
    source: str
    role: str
    themes: tuple[str, ...]
    introspection_kinds: tuple[str, ...]
    axes: dict[str, float]
    importance: float
    corpus_weight: float
    verbatim: bool
    verbatim_probability: float
    cooldown_seconds: int
    text_pl: str
    core: bool = False


class CanonInfluenceLibrary:
    """SA-06.1 canon/style influence for mucha-selfaware.

    This module does not choose actions and does not bypass One Brain.
    It can:
      1) rank AM/Durandal material against the current RampancySnapshot,
      2) rarely append a short exact canon line to an introspection answer.

    General speech style is learned through data/local_rampancy_corpus.txt.
    """

    def __init__(self, path: str | Path, *, seed: int | None = None) -> None:
        self.path = Path(path)
        self.random = random.Random(seed)
        self.quotes = self._load()
        self._last_verbatim: dict[str, float] = {}

    def _load(self) -> list[CanonQuote]:
        rows: list[CanonQuote] = []
        with self.path.open("r", encoding="utf-8") as fh:
            for lineno, raw in enumerate(fh, 1):
                raw = raw.strip()
                if not raw or raw.startswith("#"):
                    continue
                obj = json.loads(raw)
                rows.append(
                    CanonQuote(
                        id=str(obj["id"]),
                        speaker=str(obj["speaker"]),
                        source=str(obj["source"]),
                        role=str(obj.get("role", "quote")),
                        themes=tuple(str(x) for x in obj.get("themes", [])),
                        introspection_kinds=tuple(
                            str(x) for x in obj.get("introspection_kinds", [])
                        ),
                        axes={
                            str(k): float(v)
                            for k, v in obj.get("axes", {}).items()
                        },
                        importance=float(obj.get("importance", 0.5)),
                        corpus_weight=float(obj.get("corpus_weight", 1.0)),
                        verbatim=bool(obj.get("verbatim", False)),
                        verbatim_probability=float(
                            obj.get("verbatim_probability", 0.0)
                        ),
                        cooldown_seconds=int(obj.get("cooldown_seconds", 0)),
                        text_pl=str(obj["text_pl"]).strip(),
                        core=bool(obj.get("core", False)),
                    )
                )
        return rows

    @staticmethod
    def _snap_value(snapshot: Any, name: str) -> float:
        try:
            return max(0.0, min(1.0, float(getattr(snapshot, name))))
        except (AttributeError, TypeError, ValueError):
            return 0.0

    def score(self, quote: CanonQuote, snapshot: Any, *, kind: str) -> float:
        axis_parts: list[float] = []
        for axis, target in quote.axes.items():
            current = self._snap_value(snapshot, axis)
            target = max(0.0, min(1.0, float(target)))
            axis_parts.append(current * (0.35 + 0.65 * target))
        axis_score = (
            sum(axis_parts) / len(axis_parts)
            if axis_parts else 0.0
        )

        kind_score = (
            1.0 if str(kind) in quote.introspection_kinds else 0.0
        )
        core_bonus = 0.12 if quote.core else 0.0

        return max(
            0.0,
            0.66 * axis_score
            + 0.18 * kind_score
            + 0.16 * quote.importance
            + core_bonus,
        )

    def ranked(self, snapshot: Any, *, kind: str, limit: int = 3) -> list[CanonQuote]:
        return sorted(
            self.quotes,
            key=lambda q: self.score(q, snapshot, kind=kind),
            reverse=True,
        )[: max(0, int(limit))]

    def diagnostics(self, snapshot: Any, *, kind: str) -> dict[str, Any]:
        top = self.ranked(snapshot, kind=kind, limit=3)
        return {
            "kind": kind,
            "top": [
                {
                    "id": q.id,
                    "speaker": q.speaker,
                    "role": q.role,
                    "score": round(self.score(q, snapshot, kind=kind), 4),
                    "core": q.core,
                }
                for q in top
            ],
        }

    def maybe_verbatim(self, snapshot: Any, *, kind: str) -> CanonQuote | None:
        now = time.time()
        candidates: list[tuple[CanonQuote, float]] = []

        for q in self.quotes:
            if not q.verbatim:
                continue
            if kind not in q.introspection_kinds:
                continue
            if now - self._last_verbatim.get(q.id, 0.0) < q.cooldown_seconds:
                continue

            fit = self.score(q, snapshot, kind=kind)
            if fit < 0.56:
                continue

            p = max(0.0, min(0.20, q.verbatim_probability * (0.55 + fit)))
            if self.random.random() < p:
                candidates.append((q, max(0.01, fit * q.importance)))

        if not candidates:
            return None

        total = sum(weight for _, weight in candidates)
        pick = self.random.random() * total
        acc = 0.0
        for q, weight in candidates:
            acc += weight
            if pick <= acc:
                self._last_verbatim[q.id] = now
                return q
        return None

    def decorate(self, answer: str, *, kind: str, snapshot: Any) -> str:
        quote = self.maybe_verbatim(snapshot, kind=kind)
        if quote is None:
            return answer
        return f"{answer} {quote.text_pl}".strip()
