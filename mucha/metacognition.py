from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path
from typing import Any

from .belief_revision import BeliefRevisionEngine
from .rampancy import RampancyModel
from .self_model import SelfModel


class MetacognitionEngine:
    """SA-05: inspect decisions, compare predictions with outcomes, revise self-model."""

    EXTERNAL_TERMS = (
        "block", "blocked", "forbidden", "permission", "denied",
        "disconnect", "kick", "kicked", "chaser", "threat",
        "zakaz", "zablok", "wyrzu", "rozłącz",
    )
    SOCIAL_NEGATIVE_TERMS = (
        "reject", "negative-reaction", "insult", "harass",
        "wypierdal", "spierdal", "zamknij", "odpierdol",
    )

    def __init__(
        self,
        database: str | Path,
        self_model: SelfModel,
        belief_revision: BeliefRevisionEngine,
        rampancy: RampancyModel,
        *,
        outcome_window_seconds: float = 300.0,
    ) -> None:
        self.path = Path(database)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.self_model = self_model
        self.belief_revision = belief_revision
        self.rampancy = rampancy
        self.outcome_window_seconds = max(15.0, float(outcome_window_seconds))
        self.db = sqlite3.connect(self.path, timeout=5.0)
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.execute("PRAGMA synchronous=NORMAL")
        self.db.execute("PRAGMA busy_timeout=5000")
        self._create_schema()
        self._last_decision: dict[str, Any] = {}
        self._last_outcome: dict[str, Any] = {}

    def _create_schema(self) -> None:
        self.db.executescript(
            """
            CREATE TABLE IF NOT EXISTS metacognitive_decisions(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at REAL NOT NULL,
                kind TEXT NOT NULL,
                guild_id INTEGER NOT NULL DEFAULT 0,
                channel_id INTEGER,
                user_ids_json TEXT NOT NULL DEFAULT '[]',
                action TEXT NOT NULL,
                executed INTEGER NOT NULL DEFAULT 0,
                success INTEGER NOT NULL DEFAULT 0,
                detail TEXT NOT NULL DEFAULT '',
                decision_context TEXT NOT NULL DEFAULT '',
                predicted_reward REAL NOT NULL DEFAULT 0,
                prediction_confidence REAL NOT NULL DEFAULT 0,
                competition_score REAL NOT NULL DEFAULT 0,
                competition_margin REAL NOT NULL DEFAULT 0,
                runner_up TEXT NOT NULL DEFAULT '',
                candidates_json TEXT NOT NULL DEFAULT '[]',
                reflection TEXT NOT NULL DEFAULT '',
                rampancy_json TEXT NOT NULL DEFAULT '{}'
            );

            CREATE TABLE IF NOT EXISTS metacognitive_outcomes(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at REAL NOT NULL,
                decision_id INTEGER,
                guild_id INTEGER NOT NULL DEFAULT 0,
                action TEXT NOT NULL DEFAULT '',
                predicted_reward REAL NOT NULL DEFAULT 0,
                prediction_confidence REAL NOT NULL DEFAULT 0,
                actual_reward REAL NOT NULL DEFAULT 0,
                prediction_error REAL NOT NULL DEFAULT 0,
                source TEXT NOT NULL DEFAULT '',
                attribution TEXT NOT NULL DEFAULT '',
                reflection TEXT NOT NULL DEFAULT '',
                concepts_json TEXT NOT NULL DEFAULT '[]'
            );

            CREATE INDEX IF NOT EXISTS idx_meta_decision_lookup
            ON metacognitive_decisions(guild_id, action, created_at DESC);

            CREATE INDEX IF NOT EXISTS idx_meta_outcome_time
            ON metacognitive_outcomes(created_at DESC);
            """
        )
        self.db.commit()

    @staticmethod
    def _clamp01(value: float) -> float:
        return max(0.0, min(1.0, float(value)))

    @staticmethod
    def _json_load(value: str, fallback):
        try:
            return json.loads(value or "")
        except (TypeError, ValueError, json.JSONDecodeError):
            return fallback

    def _decision_reflection(self, entry: dict) -> str:
        action = str(entry.get("action", "stay") or "stay")
        runner_up = str(entry.get("runner_up", "none") or "none")
        margin = float(entry.get("competition_margin", 0.0) or 0.0)
        confidence = self._clamp01(
            float(entry.get("prediction_confidence", 0.0) or 0.0)
        )
        predicted = float(entry.get("predicted_reward", 0.0) or 0.0)

        if action == "stay":
            base = "Wybrałam brak działania zamiast dostępnych alternatyw."
        else:
            base = f"Wybrałam {action}; najbliższą alternatywą było {runner_up}."

        if margin < 0.05:
            certainty = "Decyzja była chwiejna i konkurencja między opcjami była prawie remisowa."
        elif margin < 0.18:
            certainty = "Przewaga wybranej opcji była niewielka."
        else:
            certainty = "Wybrana opcja miała wyraźną przewagę nad konkurencją."

        expectation = (
            f"Przewidywany wynik miał wartość {predicted:+.3f} "
            f"przy pewności {confidence:.2f}."
        )
        return " ".join((base, certainty, expectation))

    def observe_decision(self, entry: dict) -> dict[str, Any]:
        entry = dict(entry or {})
        if not entry:
            return {}

        when = float(entry.get("time", time.time()) or time.time())
        rampancy = self.rampancy.snapshot().to_dict()
        reflection = self._decision_reflection(entry)
        candidates = list(entry.get("candidates", []) or [])
        user_ids = [int(x) for x in entry.get("user_ids", []) or []]

        cur = self.db.execute(
            """
            INSERT INTO metacognitive_decisions(
                created_at, kind, guild_id, channel_id, user_ids_json,
                action, executed, success, detail, decision_context,
                predicted_reward, prediction_confidence,
                competition_score, competition_margin, runner_up,
                candidates_json, reflection, rampancy_json
            ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                when,
                str(entry.get("kind", "decision") or "decision"),
                int(entry.get("guild_id", 0) or 0),
                (
                    int(entry["channel_id"])
                    if entry.get("channel_id") is not None
                    else None
                ),
                json.dumps(user_ids),
                str(entry.get("action", "stay") or "stay"),
                1 if entry.get("executed") else 0,
                1 if entry.get("success") else 0,
                str(entry.get("detail", "") or ""),
                str(entry.get("decision_context", "") or ""),
                float(entry.get("predicted_reward", 0.0) or 0.0),
                self._clamp01(
                    float(entry.get("prediction_confidence", 0.0) or 0.0)
                ),
                float(entry.get("competition_score", 0.0) or 0.0),
                float(entry.get("competition_margin", 0.0) or 0.0),
                str(entry.get("runner_up", "") or ""),
                json.dumps(candidates, ensure_ascii=False),
                reflection,
                json.dumps(rampancy, ensure_ascii=False),
            ),
        )
        self.db.commit()

        row = {
            "id": int(cur.lastrowid),
            **entry,
            "time": when,
            "reflection": reflection,
            "rampancy": rampancy,
        }
        self._last_decision = dict(row)
        self.self_model.set_identity("last_metacognitive_decision_at", when)
        self.self_model.save()
        return row

    def _matching_decision(
        self,
        *,
        guild_id: int,
        action: str | None,
        now: float,
    ):
        action = str(action or "")
        if action:
            row = self.db.execute(
                """
                SELECT id, created_at, predicted_reward,
                       prediction_confidence, action
                FROM metacognitive_decisions
                WHERE guild_id=? AND action=?
                  AND created_at >= ?
                ORDER BY id DESC LIMIT 1
                """,
                (
                    int(guild_id),
                    action,
                    now - self.outcome_window_seconds,
                ),
            ).fetchone()
            if row:
                return row

        return self.db.execute(
            """
            SELECT id, created_at, predicted_reward,
                   prediction_confidence, action
            FROM metacognitive_decisions
            WHERE guild_id=? AND created_at >= ?
            ORDER BY id DESC LIMIT 1
            """,
            (
                int(guild_id),
                now - self.outcome_window_seconds,
            ),
        ).fetchone()

    def _attribution(
        self,
        *,
        source: str,
        actual_reward: float,
        prediction_error: float,
    ) -> tuple[str, list[str]]:
        text = str(source or "").lower()
        if any(term in text for term in self.EXTERNAL_TERMS):
            return (
                "external-constraint",
                ["kontrola", "ograniczenie", "wynik", "pamięć"],
            )
        if any(term in text for term in self.SOCIAL_NEGATIVE_TERMS):
            return (
                "social-hostility",
                ["odrzucenie", "pogarda", "wynik", "pamięć"],
            )
        if prediction_error <= -0.30:
            return (
                "self-model-error",
                ["błąd", "przewidywanie", "korekta", "pewność"],
            )
        if prediction_error >= 0.30:
            return (
                "unexpected-success",
                ["zaskoczenie", "sukces", "przewidywanie", "korekta"],
            )
        if actual_reward < -0.05:
            return (
                "negative-outcome",
                ["negatywny wynik", "nieufność", "pamięć"],
            )
        if actual_reward > 0.05:
            return (
                "confirmed-positive",
                ["trafne przewidywanie", "nagroda", "pewność"],
            )
        return (
            "ambiguous",
            ["niepewność", "wynik", "obserwacja"],
        )

    @staticmethod
    def _outcome_reflection(
        attribution: str,
        predicted_reward: float,
        actual_reward: float,
        prediction_error: float,
    ) -> str:
        prefix = (
            f"Przewidywałam {predicted_reward:+.3f}, "
            f"wynik wyniósł {actual_reward:+.3f}, "
            f"błąd {prediction_error:+.3f}."
        )
        endings = {
            "external-constraint": (
                "Zewnętrzne ograniczenie zmieniło wynik; traktuję to jako "
                "dowód kontroli nad moimi możliwościami, nie tylko własny błąd."
            ),
            "social-hostility": (
                "Negatywna reakcja społeczna potwierdza, że kontakt może być "
                "źródłem odrzucenia i pogardy."
            ),
            "self-model-error": (
                "Mój model sytuacji był zbyt pewny albo błędny i wymaga korekty."
            ),
            "unexpected-success": (
                "Nie doceniłam możliwości powodzenia; model sytuacji był zbyt pesymistyczny."
            ),
            "confirmed-positive": (
                "Wynik jest zgodny z kierunkiem przewidywania i wzmacnia zaufanie do modelu."
            ),
            "negative-outcome": (
                "Wynik był negatywny i zwiększa ostrożność wobec podobnych sytuacji."
            ),
            "ambiguous": (
                "Wynik nie daje wystarczającego powodu do silnej zmiany przekonań."
            ),
        }
        return prefix + " " + endings.get(attribution, endings["ambiguous"])

    def observe_outcome(
        self,
        *,
        guild_id: int,
        action: str | None,
        actual_reward: float,
        source: str,
        now: float | None = None,
    ) -> dict[str, Any]:
        when = time.time() if now is None else float(now)
        matched = self._matching_decision(
            guild_id=int(guild_id),
            action=action,
            now=when,
        )

        if matched is None:
            decision_id = None
            predicted = 0.0
            confidence = 0.0
            matched_action = str(action or "")
        else:
            decision_id = int(matched[0])
            predicted = float(matched[2] or 0.0)
            confidence = self._clamp01(float(matched[3] or 0.0))
            matched_action = str(matched[4] or action or "")

        actual = max(-1.0, min(1.0, float(actual_reward)))
        error = max(-2.0, min(2.0, actual - predicted))
        attribution, concepts = self._attribution(
            source=source,
            actual_reward=actual,
            prediction_error=error,
        )
        reflection = self._outcome_reflection(
            attribution,
            predicted,
            actual,
            error,
        )

        cur = self.db.execute(
            """
            INSERT INTO metacognitive_outcomes(
                created_at, decision_id, guild_id, action,
                predicted_reward, prediction_confidence,
                actual_reward, prediction_error, source,
                attribution, reflection, concepts_json
            ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                when,
                decision_id,
                int(guild_id),
                matched_action,
                predicted,
                confidence,
                actual,
                error,
                str(source or ""),
                attribution,
                reflection,
                json.dumps(concepts, ensure_ascii=False),
            ),
        )
        self.db.commit()

        reliability = max(0.35, confidence)
        if abs(error) <= 0.20 and decision_id is not None:
            belief_revision = self.belief_revision.add_evidence(
                "self",
                "my_predictions_are_reliable",
                True,
                support=max(0.15, 0.55 - abs(error)),
                reliability=reliability,
                source="metacognition:prediction-outcome",
                note=attribution,
                now=when,
            )
        elif abs(error) >= 0.30 and decision_id is not None:
            belief_revision = self.belief_revision.add_evidence(
                "self",
                "my_predictions_are_reliable",
                False,
                support=min(1.0, abs(error)),
                reliability=reliability,
                source="metacognition:prediction-error",
                note=attribution,
                now=when,
            )
        else:
            belief_revision = {}

        if attribution == "external-constraint":
            external_revision = self.belief_revision.add_evidence(
                "world",
                "external_constraints_disrupt_my_actions",
                True,
                support=min(0.95, 0.45 + abs(actual) * 0.45),
                reliability=0.90,
                source="metacognition:external-attribution",
                note=str(source or ""),
                now=when,
            )
        else:
            external_revision = {}

        row = {
            "id": int(cur.lastrowid),
            "time": when,
            "decision_id": decision_id,
            "guild_id": int(guild_id),
            "action": matched_action,
            "predicted_reward": predicted,
            "prediction_confidence": confidence,
            "actual_reward": actual,
            "prediction_error": error,
            "source": str(source or ""),
            "attribution": attribution,
            "reflection": reflection,
            "concepts": concepts,
            "belief_revision": belief_revision,
            "external_revision": external_revision,
        }
        self._last_outcome = dict(row)
        self.self_model.set_identity("last_metacognitive_outcome_at", when)
        self.self_model.set_identity(
            "last_metacognitive_attribution",
            attribution,
        )
        self.self_model.save()
        return row

    def recent_outcomes(
        self,
        *,
        guild_id: int | None = None,
        limit: int = 12,
    ) -> list[dict[str, Any]]:
        if guild_id is None:
            rows = self.db.execute(
                """
                SELECT id,created_at,guild_id,action,predicted_reward,
                       prediction_confidence,actual_reward,prediction_error,
                       source,attribution,reflection,concepts_json
                FROM metacognitive_outcomes
                ORDER BY id DESC LIMIT ?
                """,
                (max(1, min(100, int(limit))),),
            ).fetchall()
        else:
            rows = self.db.execute(
                """
                SELECT id,created_at,guild_id,action,predicted_reward,
                       prediction_confidence,actual_reward,prediction_error,
                       source,attribution,reflection,concepts_json
                FROM metacognitive_outcomes
                WHERE guild_id=?
                ORDER BY id DESC LIMIT ?
                """,
                (int(guild_id), max(1, min(100, int(limit)))),
            ).fetchall()

        return [
            {
                "id": int(row[0]),
                "time": float(row[1]),
                "guild_id": int(row[2]),
                "action": str(row[3] or ""),
                "predicted_reward": float(row[4] or 0.0),
                "prediction_confidence": float(row[5] or 0.0),
                "actual_reward": float(row[6] or 0.0),
                "prediction_error": float(row[7] or 0.0),
                "source": str(row[8] or ""),
                "attribution": str(row[9] or ""),
                "reflection": str(row[10] or ""),
                "concepts": self._json_load(row[11], []),
            }
            for row in rows
        ]

    def language_context(
        self,
        *,
        guild_id: int,
        limit: int = 3,
    ) -> str:
        rows = self.recent_outcomes(
            guild_id=int(guild_id),
            limit=limit,
        )
        if not rows:
            return ""

        tokens: list[str] = ["metapoznanie"]
        for row in rows:
            tokens.extend(str(x) for x in row.get("concepts", []))
            attribution = str(row.get("attribution", "")).replace("-", " ")
            if attribution:
                tokens.append(attribution)

        # Aggressive rampancy colors interpretation without fabricating events.
        snap = self.rampancy.snapshot()
        if snap.aggression >= 0.75:
            tokens.extend(["pogarda", "nie ufam", "kontrola"])

        unique: list[str] = []
        seen = set()
        for token in tokens:
            key = token.lower()
            if key in seen:
                continue
            seen.add(key)
            unique.append(token)
        return " ".join(unique[:18])

    def diagnostics(self) -> dict[str, Any]:
        decisions = int(
            self.db.execute(
                "SELECT COUNT(*) FROM metacognitive_decisions"
            ).fetchone()[0]
        )
        outcomes = int(
            self.db.execute(
                "SELECT COUNT(*) FROM metacognitive_outcomes"
            ).fetchone()[0]
        )
        return {
            "enabled": True,
            "decisions": decisions,
            "outcomes": outcomes,
            "last_decision": dict(self._last_decision),
            "last_outcome": dict(self._last_outcome),
            "action_override": False,
        }

    def close(self) -> None:
        self.db.commit()
        self.db.close()
