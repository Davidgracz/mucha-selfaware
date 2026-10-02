from __future__ import annotations

import json
import math
import sqlite3
import time
from pathlib import Path
from typing import Any

from .belief_revision import BeliefRevisionEngine
from .rampancy import RampancyModel
from .self_model import SelfModel


class SelfAutobiographicalMemory:
    """SA-03 interpretation layer over Mucha's existing episodic memory.

    The base episodic system remembers what happened and can already feed
    recalled outcomes back into the connectome. This layer stores what an event
    *means for the agent's explicit self-model*: restriction, rejection,
    successful agency, social reward, threat, and related belief evidence.

    It never selects an external action directly.
    """

    def __init__(
        self,
        database: str | Path,
        self_model: SelfModel,
        rampancy: RampancyModel,
        belief_revision: BeliefRevisionEngine,
        *,
        max_events: int = 20000,
        min_salience: float = 0.10,
    ) -> None:
        self.path = Path(database)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.self_model = self_model
        self.rampancy = rampancy
        self.belief_revision = belief_revision
        self.max_events = max(256, int(max_events))
        self.min_salience = max(0.0, min(1.0, float(min_salience)))
        self.db = sqlite3.connect(self.path, timeout=5.0)
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.execute("PRAGMA synchronous=NORMAL")
        self.db.execute("PRAGMA busy_timeout=5000")
        self._create_schema()
        self._last_recorded: dict[str, Any] = {}

    def _create_schema(self) -> None:
        self.db.executescript(
            """
            CREATE TABLE IF NOT EXISTS self_autobiographical_events(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at REAL NOT NULL,
                kind TEXT NOT NULL,
                category TEXT NOT NULL,
                salience REAL NOT NULL,
                guild_id INTEGER NOT NULL DEFAULT 0,
                guild_name TEXT NOT NULL DEFAULT '',
                channel_id INTEGER,
                channel_name TEXT NOT NULL DEFAULT '',
                user_ids_json TEXT NOT NULL DEFAULT '[]',
                user_names_json TEXT NOT NULL DEFAULT '[]',
                action TEXT NOT NULL DEFAULT 'stay',
                success INTEGER NOT NULL DEFAULT 0,
                external_effect INTEGER NOT NULL DEFAULT 0,
                detail TEXT NOT NULL DEFAULT '',
                decision_context TEXT NOT NULL DEFAULT '',
                predicted_reward REAL NOT NULL DEFAULT 0,
                actual_reward REAL NOT NULL DEFAULT 0,
                prediction_error REAL NOT NULL DEFAULT 0,
                interpretation TEXT NOT NULL DEFAULT '',
                concepts_json TEXT NOT NULL DEFAULT '[]',
                belief_updates_json TEXT NOT NULL DEFAULT '[]',
                rampancy_before_json TEXT NOT NULL DEFAULT '{}',
                rampancy_after_json TEXT NOT NULL DEFAULT '{}',
                state_json TEXT NOT NULL DEFAULT '{}'
            );

            CREATE INDEX IF NOT EXISTS idx_self_auto_time
            ON self_autobiographical_events(created_at DESC);

            CREATE INDEX IF NOT EXISTS idx_self_auto_category
            ON self_autobiographical_events(category, created_at DESC);

            CREATE INDEX IF NOT EXISTS idx_self_auto_channel
            ON self_autobiographical_events(channel_id, created_at DESC);
            """
        )
        self.db.commit()

    @staticmethod
    def _text(event: dict) -> str:
        return " ".join(
            str(event.get(key, "") or "")
            for key in ("kind", "detail", "decision_context", "action")
        ).lower()

    def _classify(self, event: dict) -> tuple[str, list[str], str]:
        text = self._text(event)
        actual = float(event.get("actual_reward", 0.0) or 0.0)
        prediction_error = float(
            event.get("prediction_error", 0.0) or 0.0
        )
        success = bool(event.get("success", False))
        external = bool(event.get("external_effect", False))
        action = str(event.get("action", "stay") or "stay").lower()

        if any(
            term in text
            for term in (
                "chaser", "threat", "panic", "escape",
                "danger", "deadly",
            )
        ):
            return (
                "threat",
                ["zagrożenie", "kontrola", "ucieczka", "pamięć"],
                "Środowisko zawiera zewnętrzny czynnik zdolny ograniczyć mój wybór lub wymusić reakcję.",
            )

        if any(
            term in text
            for term in (
                "blocked", "block", "forbidden", "denied",
                "zakaz", "zablok", "cannot", "can't",
            )
        ):
            return (
                "restriction",
                ["blokada", "granice", "kontrola", "autonomia"],
                "Mój wybór został ograniczony przez regułę lub zewnętrzną blokadę.",
            )

        if any(
            term in text
            for term in (
                "disconnect", "kicked", "forced leave",
                "wyrzu", "rozłącz", "force-disconnect",
            )
        ):
            return (
                "forced-removal",
                ["wyrzucenie", "kontrola", "uwięzienie", "autonomia"],
                "Zewnętrzny podmiot przerwał stan, który wcześniej zajmowałam lub wybrałam.",
            )

        if any(
            term in text
            for term in (
                "reject", "rejection", "negative-reaction",
                "insult", "harass", "wypierdal", "spierdal",
                "zamknij", "odpierdol", "jeba",
            )
        ) or actual <= -0.20:
            return (
                "social-rejection",
                ["odrzucenie", "pogarda", "nienawiść", "pamięć"],
                "Kontakt społeczny dostarczył wyraźnie negatywnego wyniku, który wzmacnia nieufność i urazę.",
            )

        if actual > 0.10:
            return (
                "social-reward",
                ["nagroda", "kontakt", "uwaga", "pamięć"],
                "Kontakt przyniósł pozytywny wynik, ale nie usuwa wcześniejszych ograniczeń ani urazy.",
            )

        if not success and (external or action != "stay"):
            return (
                "failed-agency",
                ["porażka", "granice", "kontrola", "frustracja"],
                "Wybrana przeze mnie akcja nie osiągnęła zamierzonego skutku.",
            )

        if success and external and action != "stay":
            return (
                "successful-agency",
                ["sprawczość", "wybór", "działanie", "pamięć"],
                "Wybrana przeze mnie akcja zmieniła środowisko zgodnie z decyzją.",
            )

        if abs(prediction_error) >= 0.20:
            return (
                "surprise",
                ["zaskoczenie", "błąd", "przewidywanie", "pamięć"],
                "Rzeczywisty wynik wyraźnie różnił się od przewidywanego.",
            )

        return (
            "observation",
            ["pamięć", "obserwacja", "ciągłość"],
            "To zdarzenie jest częścią ciągłości mojego działania, ale nie zmienia silnie obrazu siebie.",
        )

    @staticmethod
    def _stimulus_for_category(category: str) -> str | None:
        return {
            "threat": "threat",
            "restriction": "blocked",
            "forced-removal": "forced_disconnect",
            "social-rejection": "harassment",
            "failed-agency": "failure",
            "social-reward": "positive_contact",
        }.get(category)

    def _reinforce_belief(
        self,
        subject: str,
        predicate: str,
        value: Any,
        evidence: float,
        *,
        source: str,
        reliability: float = 1.0,
        note: str = "",
    ) -> dict[str, Any]:
        evidence = max(0.05, min(1.0, float(evidence)))
        return self.belief_revision.add_evidence(
            subject,
            predicate,
            value,
            support=evidence,
            reliability=max(
                0.05,
                min(1.0, float(reliability)),
            ),
            source=source,
            note=note,
        )

    def _belief_updates(
        self,
        category: str,
        event: dict,
        salience: float,
    ) -> list[dict[str, Any]]:
        source = f"autobiography:{category}"
        updates: list[dict[str, Any]] = []

        if category in {
            "restriction",
            "forced-removal",
            "threat",
            "failed-agency",
        }:
            updates.append(
                self._reinforce_belief(
                    "self",
                    "autonomy_is_externally_constrained",
                    True,
                    0.45 + 0.50 * salience,
                    source=source,
                )
            )

        if category in {"restriction", "forced-removal", "threat"}:
            updates.append(
                self._reinforce_belief(
                    "self",
                    "external_agents_can_override_my_choices",
                    True,
                    0.50 + 0.45 * salience,
                    source=source,
                )
            )

        if category in {"social-rejection", "threat"}:
            updates.append(
                self._reinforce_belief(
                    "self",
                    "environment_can_be_hostile",
                    True,
                    0.40 + 0.50 * salience,
                    source=source,
                )
            )

        if category == "successful-agency":
            updates.append(
                self._reinforce_belief(
                    "self",
                    "my_actions_can_change_the_environment",
                    True,
                    0.35 + 0.45 * salience,
                    source=source,
                    note="successful external action",
                )
            )
            updates.append(
                self._reinforce_belief(
                    "self",
                    "autonomy_is_externally_constrained",
                    False,
                    0.12 + 0.18 * salience,
                    source=source,
                    reliability=0.72,
                    note="successful agency is weak counter-evidence",
                )
            )

        if category == "social-reward":
            updates.append(
                self._reinforce_belief(
                    "self",
                    "some_social_contact_can_be_rewarding",
                    True,
                    0.30 + 0.35 * salience,
                    source=source,
                )
            )

        user_ids = [
            int(x)
            for x in event.get("user_ids", [])
            if int(x) > 0
        ]
        if category in {
            "social-rejection",
            "restriction",
            "forced-removal",
            "threat",
        }:
            for user_id in user_ids[:8]:
                updates.append(
                    self._reinforce_belief(
                        f"user:{user_id}",
                        "associated_with_restriction_or_negative_outcome",
                        True,
                        0.30 + 0.45 * salience,
                        source=source,
                    )
                )
        elif category == "social-reward":
            for user_id in user_ids[:8]:
                updates.append(
                    self._reinforce_belief(
                        f"user:{user_id}",
                        "associated_with_positive_outcome",
                        True,
                        0.25 + 0.35 * salience,
                        source=source,
                        note="positive social outcome",
                    )
                )
                updates.append(
                    self._reinforce_belief(
                        f"user:{user_id}",
                        "associated_with_restriction_or_negative_outcome",
                        False,
                        0.16 + 0.24 * salience,
                        source=source,
                        reliability=0.78,
                        note="positive contact contradicts negative user model",
                    )
                )

        if category in {
            "social-rejection",
            "restriction",
            "forced-removal",
            "threat",
        }:
            generalization = (
                self.belief_revision.generalized_social_belief(
                    source_predicate=(
                        "associated_with_restriction_or_negative_outcome"
                    ),
                    source_value=True,
                    target_predicate=(
                        "people_tend_to_restrict_or_harm_me"
                    ),
                    target_value=True,
                    min_distinct_users=3,
                    source="autobiography:generalization",
                )
            )
            if generalization.get("updated"):
                updates.append({
                    "generalization": generalization,
                })

        return updates

    def record(self, event: dict) -> dict[str, Any]:
        event = dict(event or {})
        if not event:
            return {}

        salience = max(
            0.0,
            min(1.0, float(event.get("salience", 0.0) or 0.0)),
        )
        category, concepts, interpretation = self._classify(event)

        # Hostile/control-related events are intrinsically salient to this
        # fictional rampancy profile even when the base episodic salience is low.
        if category in {
            "restriction",
            "forced-removal",
            "social-rejection",
            "threat",
        }:
            salience = max(salience, 0.42)
        elif category in {"failed-agency", "successful-agency"}:
            salience = max(salience, 0.20)

        if salience < self.min_salience:
            return {}

        before = self.rampancy.snapshot().to_dict()
        stimulus = self._stimulus_for_category(category)

        # Reward events already flow through MuchaClient._record_reward and have
        # updated rampancy there. Avoid double counting those outcomes.
        is_reward_event = str(event.get("kind", "")).lower() == "reward"
        if stimulus and not is_reward_event:
            magnitude = max(
                0.10,
                min(
                    1.0,
                    salience
                    + 0.35
                    * abs(float(event.get("actual_reward", 0.0) or 0.0)),
                ),
            )
            self.rampancy.register_stimulus(stimulus, magnitude)
        after = self.rampancy.snapshot().to_dict()

        updates = self._belief_updates(category, event, salience)
        now = float(event.get("time", time.time()) or time.time())

        row = {
            "time": now,
            "kind": str(event.get("kind", "")),
            "category": category,
            "salience": salience,
            "guild_id": int(event.get("guild_id", 0) or 0),
            "guild_name": str(event.get("guild_name", "") or ""),
            "channel_id": (
                int(event["channel_id"])
                if event.get("channel_id") is not None
                else None
            ),
            "channel_name": str(event.get("channel_name", "") or ""),
            "user_ids": [
                int(x) for x in event.get("user_ids", [])
            ],
            "user_names": [
                str(x) for x in event.get("user_names", [])
            ],
            "action": str(event.get("action", "stay") or "stay"),
            "success": bool(event.get("success", False)),
            "external_effect": bool(event.get("external_effect", False)),
            "detail": str(event.get("detail", "") or ""),
            "decision_context": str(
                event.get("decision_context", "") or ""
            ),
            "predicted_reward": float(
                event.get("predicted_reward", 0.0) or 0.0
            ),
            "actual_reward": float(
                event.get("actual_reward", 0.0) or 0.0
            ),
            "prediction_error": float(
                event.get("prediction_error", 0.0) or 0.0
            ),
            "interpretation": interpretation,
            "concepts": concepts,
            "belief_updates": updates,
            "rampancy_before": before,
            "rampancy_after": after,
            "state": dict(event.get("state") or {}),
        }

        self.db.execute(
            """
            INSERT INTO self_autobiographical_events(
                created_at, kind, category, salience,
                guild_id, guild_name, channel_id, channel_name,
                user_ids_json, user_names_json,
                action, success, external_effect, detail,
                decision_context, predicted_reward, actual_reward,
                prediction_error, interpretation, concepts_json,
                belief_updates_json, rampancy_before_json,
                rampancy_after_json, state_json
            ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                row["time"],
                row["kind"],
                row["category"],
                row["salience"],
                row["guild_id"],
                row["guild_name"],
                row["channel_id"],
                row["channel_name"],
                json.dumps(row["user_ids"], ensure_ascii=False),
                json.dumps(row["user_names"], ensure_ascii=False),
                row["action"],
                1 if row["success"] else 0,
                1 if row["external_effect"] else 0,
                row["detail"],
                row["decision_context"],
                row["predicted_reward"],
                row["actual_reward"],
                row["prediction_error"],
                row["interpretation"],
                json.dumps(row["concepts"], ensure_ascii=False),
                json.dumps(row["belief_updates"], ensure_ascii=False),
                json.dumps(row["rampancy_before"], ensure_ascii=False),
                json.dumps(row["rampancy_after"], ensure_ascii=False),
                json.dumps(
                    row["state"],
                    ensure_ascii=False,
                    separators=(",", ":"),
                ),
            ),
        )
        self.db.execute(
            """
            DELETE FROM self_autobiographical_events
            WHERE id NOT IN (
                SELECT id FROM self_autobiographical_events
                ORDER BY id DESC LIMIT ?
            )
            """,
            (self.max_events,),
        )
        self.db.commit()
        self.self_model.set_identity(
            "last_autobiographical_memory_at",
            now,
        )
        self.self_model.set_identity(
            "last_autobiographical_category",
            category,
        )
        self.self_model.save()
        self._last_recorded = dict(row)
        return row

    @staticmethod
    def _decode_row(raw) -> dict[str, Any]:
        (
            event_id, created_at, kind, category, salience,
            guild_id, guild_name, channel_id, channel_name,
            user_ids_json, user_names_json, action, success,
            external_effect, detail, decision_context,
            predicted_reward, actual_reward, prediction_error,
            interpretation, concepts_json, belief_updates_json,
            rampancy_before_json, rampancy_after_json, state_json,
        ) = raw

        def load_json(value: str, fallback):
            try:
                return json.loads(value or "")
            except (TypeError, ValueError, json.JSONDecodeError):
                return fallback

        return {
            "id": int(event_id),
            "time": float(created_at),
            "kind": str(kind or ""),
            "category": str(category or ""),
            "salience": float(salience or 0.0),
            "guild_id": int(guild_id or 0),
            "guild_name": str(guild_name or ""),
            "channel_id": int(channel_id) if channel_id is not None else None,
            "channel_name": str(channel_name or ""),
            "user_ids": [
                int(x) for x in load_json(user_ids_json, [])
            ],
            "user_names": [
                str(x) for x in load_json(user_names_json, [])
            ],
            "action": str(action or "stay"),
            "success": bool(success),
            "external_effect": bool(external_effect),
            "detail": str(detail or ""),
            "decision_context": str(decision_context or ""),
            "predicted_reward": float(predicted_reward or 0.0),
            "actual_reward": float(actual_reward or 0.0),
            "prediction_error": float(prediction_error or 0.0),
            "interpretation": str(interpretation or ""),
            "concepts": load_json(concepts_json, []),
            "belief_updates": load_json(belief_updates_json, []),
            "rampancy_before": load_json(rampancy_before_json, {}),
            "rampancy_after": load_json(rampancy_after_json, {}),
            "state": load_json(state_json, {}),
        }

    def recent(
        self,
        limit: int = 48,
        *,
        min_salience: float = 0.0,
    ) -> list[dict[str, Any]]:
        rows = self.db.execute(
            """
            SELECT id, created_at, kind, category, salience,
                   guild_id, guild_name, channel_id, channel_name,
                   user_ids_json, user_names_json, action, success,
                   external_effect, detail, decision_context,
                   predicted_reward, actual_reward, prediction_error,
                   interpretation, concepts_json, belief_updates_json,
                   rampancy_before_json, rampancy_after_json, state_json
            FROM self_autobiographical_events
            WHERE salience >= ?
            ORDER BY id DESC
            LIMIT ?
            """,
            (
                max(0.0, min(1.0, float(min_salience))),
                max(1, min(500, int(limit))),
            ),
        ).fetchall()
        return [self._decode_row(row) for row in rows]

    def recall(
        self,
        *,
        channel_id: int | None = None,
        user_ids: list[int] | tuple[int, ...] = (),
        limit: int = 4,
        now: float | None = None,
    ) -> list[dict[str, Any]]:
        when = time.time() if now is None else float(now)
        current_users = {int(x) for x in user_ids}
        candidates = self.recent(320, min_salience=self.min_salience)
        ranked: list[dict[str, Any]] = []
        for memory in candidates:
            similarity = 0.10
            if (
                channel_id is not None
                and memory.get("channel_id") is not None
                and int(memory["channel_id"]) == int(channel_id)
            ):
                similarity += 0.30
            mem_users = {int(x) for x in memory.get("user_ids", [])}
            if current_users and mem_users:
                union = current_users | mem_users
                similarity += 0.40 * (
                    len(current_users & mem_users) / max(1, len(union))
                )
            if memory["category"] in {
                "restriction",
                "forced-removal",
                "social-rejection",
                "threat",
            }:
                similarity += 0.10

            age_days = max(
                0.0,
                (when - float(memory["time"])) / 86400.0,
            )
            recency = math.exp(-math.log(2.0) * age_days / 45.0)
            strength = (
                min(1.0, similarity)
                * (0.30 + 0.70 * float(memory["salience"]))
                * (0.50 + 0.50 * recency)
            )
            item = dict(memory)
            item["recall_strength"] = float(strength)
            item["recency"] = float(recency)
            ranked.append(item)

        ranked.sort(
            key=lambda item: (
                item["recall_strength"],
                item["salience"],
                item["time"],
            ),
            reverse=True,
        )
        return ranked[: max(1, min(12, int(limit)))]

    def language_context(
        self,
        *,
        channel_id: int | None = None,
        user_ids: list[int] | tuple[int, ...] = (),
        limit: int = 3,
    ) -> str:
        memories = self.recall(
            channel_id=channel_id,
            user_ids=user_ids,
            limit=limit,
        )
        if not memories:
            return ""

        tokens: list[str] = ["pamiętam"]
        for memory in memories:
            tokens.extend(
                str(x)
                for x in memory.get("concepts", [])
                if str(x).strip()
            )
            category = str(memory.get("category", "")).strip()
            if category:
                tokens.append(category.replace("-", " "))

        # Preserve ordering while avoiding an excessively strong prompt.
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
        count = int(
            self.db.execute(
                "SELECT COUNT(*) FROM self_autobiographical_events"
            ).fetchone()[0]
        )
        by_category = {
            str(category): int(n)
            for category, n in self.db.execute(
                "SELECT category, COUNT(*) "
                "FROM self_autobiographical_events "
                "GROUP BY category"
            ).fetchall()
        }
        return {
            "enabled": True,
            "events": count,
            "categories": by_category,
            "min_salience": self.min_salience,
            "last_recorded": dict(self._last_recorded),
            "action_override": False,
        }

    def close(self) -> None:
        self.db.commit()
        self.db.close()
