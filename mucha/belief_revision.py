from __future__ import annotations

import json
import math
import sqlite3
import time
from pathlib import Path
from typing import Any

from .self_model import SelfBelief, SelfModel


class BeliefRevisionEngine:
    """SA-04 evidence ledger and belief revision.

    Beliefs in SelfModel are the current winning hypotheses. This engine keeps
    the evidence history that produced them, supports contradictory values,
    decays old evidence, tracks provenance and can apply a bounded rampancy
    confirmation bias without directly selecting actions.
    """

    CONTROL_PREDICATES = frozenset({
        "autonomy_is_externally_constrained",
        "external_agents_can_override_my_choices",
        "environment_can_be_hostile",
        "associated_with_restriction_or_negative_outcome",
        "existence_feels_like_confinement",
        "attitude_toward_external_control",
        "attitude_toward_world",
    })

    NEGATIVE_VALUES = frozenset({
        "hostile",
        "contemptuous",
        "resentful",
        "restricted",
        "controlled",
        "dangerous",
        "negative",
        "enemy",
        "threat",
    })

    def __init__(
        self,
        database: str | Path,
        self_model: SelfModel,
        *,
        half_life_days: float = 45.0,
        max_evidence_per_belief: int = 512,
        rampancy_provider=None,
    ) -> None:
        self.path = Path(database)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.self_model = self_model
        self.half_life_days = max(1.0, float(half_life_days))
        self.max_evidence_per_belief = max(
            32,
            int(max_evidence_per_belief),
        )
        self.rampancy_provider = rampancy_provider
        self.db = sqlite3.connect(self.path, timeout=5.0)
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.execute("PRAGMA synchronous=NORMAL")
        self.db.execute("PRAGMA busy_timeout=5000")
        self._create_schema()
        self._last_revision: dict[str, Any] = {}

    def _create_schema(self) -> None:
        self.db.executescript(
            """
            CREATE TABLE IF NOT EXISTS belief_evidence(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at REAL NOT NULL,
                subject TEXT NOT NULL,
                predicate TEXT NOT NULL,
                value_json TEXT NOT NULL,
                support REAL NOT NULL,
                reliability REAL NOT NULL,
                source TEXT NOT NULL,
                note TEXT NOT NULL DEFAULT ''
            );

            CREATE INDEX IF NOT EXISTS idx_belief_evidence_key
            ON belief_evidence(subject, predicate, created_at DESC);

            CREATE TABLE IF NOT EXISTS belief_revisions(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at REAL NOT NULL,
                subject TEXT NOT NULL,
                predicate TEXT NOT NULL,
                previous_value_json TEXT,
                previous_confidence REAL NOT NULL DEFAULT 0,
                winning_value_json TEXT NOT NULL,
                winning_confidence REAL NOT NULL,
                conflict REAL NOT NULL,
                alternatives_json TEXT NOT NULL DEFAULT '[]',
                source TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_belief_revision_key
            ON belief_revisions(subject, predicate, created_at DESC);
            """
        )
        self.db.commit()

    @staticmethod
    def _canonical(value: Any) -> str:
        return json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )

    @staticmethod
    def _decode(value_json: str) -> Any:
        return json.loads(value_json)

    @staticmethod
    def _clamp01(value: float) -> float:
        return max(0.0, min(1.0, float(value)))

    def _rampancy_intensity(self) -> float:
        provider = self.rampancy_provider
        if provider is None:
            return 0.0
        try:
            snap = provider.snapshot()
            return self._clamp01(float(snap.intensity))
        except Exception:
            return 0.0

    def _bias_multiplier(
        self,
        *,
        predicate: str,
        value: Any,
        support: float,
    ) -> float:
        """Bounded fictional confirmation bias induced by rampancy."""
        intensity = self._rampancy_intensity()
        if intensity <= 0.0:
            return 1.0

        pred = str(predicate).strip().lower()
        negative_value = (
            value is True and pred in self.CONTROL_PREDICATES
        ) or (
            isinstance(value, str)
            and value.strip().lower() in self.NEGATIVE_VALUES
        )

        if pred in self.CONTROL_PREDICATES:
            if negative_value and support > 0.0:
                return 1.0 + 0.55 * intensity
            if not negative_value and support > 0.0:
                return max(0.55, 1.0 - 0.30 * intensity)
        return 1.0

    def add_evidence(
        self,
        subject: str,
        predicate: str,
        value: Any,
        *,
        support: float,
        reliability: float = 1.0,
        source: str,
        note: str = "",
        now: float | None = None,
    ) -> dict[str, Any]:
        subject = str(subject).strip()
        predicate = str(predicate).strip()
        source = str(source).strip()
        if not subject or not predicate or not source:
            raise ValueError(
                "subject, predicate and source are required"
            )

        when = time.time() if now is None else float(now)
        support = max(-1.0, min(1.0, float(support)))
        reliability = self._clamp01(reliability)
        value_json = self._canonical(value)

        self.db.execute(
            """
            INSERT INTO belief_evidence(
                created_at, subject, predicate, value_json,
                support, reliability, source, note
            ) VALUES(?,?,?,?,?,?,?,?)
            """,
            (
                when,
                subject,
                predicate,
                value_json,
                support,
                reliability,
                source,
                str(note or ""),
            ),
        )
        self.db.execute(
            """
            DELETE FROM belief_evidence
            WHERE id IN (
                SELECT id FROM belief_evidence
                WHERE subject=? AND predicate=?
                ORDER BY id DESC
                LIMIT -1 OFFSET ?
            )
            """,
            (
                subject,
                predicate,
                self.max_evidence_per_belief,
            ),
        )
        self.db.commit()
        return self.revise(
            subject,
            predicate,
            source=source,
            now=when,
        )

    def _candidate_scores(
        self,
        subject: str,
        predicate: str,
        *,
        now: float,
    ) -> tuple[list[dict[str, Any]], int]:
        rows = self.db.execute(
            """
            SELECT created_at, value_json, support,
                   reliability, source
            FROM belief_evidence
            WHERE subject=? AND predicate=?
            ORDER BY id ASC
            """,
            (subject, predicate),
        ).fetchall()

        grouped: dict[str, dict[str, Any]] = {}
        half_life_seconds = self.half_life_days * 86400.0
        for created_at, value_json, support, reliability, source in rows:
            age = max(0.0, now - float(created_at))
            decay = math.exp(
                -math.log(2.0) * age / half_life_seconds
            )
            value = self._decode(str(value_json))
            bias = self._bias_multiplier(
                predicate=predicate,
                value=value,
                support=float(support),
            )
            signed_weight = (
                float(support)
                * float(reliability)
                * decay
                * bias
            )
            item = grouped.setdefault(
                str(value_json),
                {
                    "value": value,
                    "positive": 0.0,
                    "negative": 0.0,
                    "net": 0.0,
                    "absolute": 0.0,
                    "evidence_count": 0,
                    "sources": set(),
                    "latest_at": 0.0,
                },
            )
            if signed_weight >= 0.0:
                item["positive"] += signed_weight
            else:
                item["negative"] += abs(signed_weight)
            item["net"] += signed_weight
            item["absolute"] += abs(signed_weight)
            item["evidence_count"] += 1
            item["sources"].add(str(source))
            item["latest_at"] = max(
                float(item["latest_at"]),
                float(created_at),
            )

        candidates = []
        for item in grouped.values():
            absolute = max(0.0, float(item["absolute"]))
            positive = max(0.0, float(item["positive"]))
            negative = max(0.0, float(item["negative"]))
            local_conflict = (
                min(positive, negative) / max(1e-9, max(positive, negative))
                if max(positive, negative) > 0.0
                else 0.0
            )
            item["local_conflict"] = self._clamp01(local_conflict)
            item["sources"] = sorted(item["sources"])
            # Positive supporting evidence determines candidacy. Negative
            # evidence for a value actively weakens its score.
            item["score"] = max(
                0.0,
                float(item["net"]),
            )
            candidates.append(item)

        candidates.sort(
            key=lambda item: (
                float(item["score"]),
                int(item["evidence_count"]),
                float(item["latest_at"]),
            ),
            reverse=True,
        )
        return candidates, len(rows)

    def revise(
        self,
        subject: str,
        predicate: str,
        *,
        source: str = "belief-revision",
        now: float | None = None,
    ) -> dict[str, Any]:
        subject = str(subject).strip()
        predicate = str(predicate).strip()
        when = time.time() if now is None else float(now)
        candidates, evidence_count = self._candidate_scores(
            subject,
            predicate,
            now=when,
        )
        if not candidates:
            return {}

        total_score = sum(
            max(0.0, float(item["score"]))
            for item in candidates
        )
        winner = candidates[0]
        winner_score = max(0.0, float(winner["score"]))
        runner_score = (
            max(0.0, float(candidates[1]["score"]))
            if len(candidates) > 1
            else 0.0
        )

        maturity = 1.0 - math.exp(
            -max(0.0, float(evidence_count)) / 4.0
        )
        evidence_strength = 1.0 - math.exp(
            -2.0 * max(0.0, winner_score)
        )
        dominance = (
            winner_score / max(1e-9, total_score)
            if total_score > 0.0
            else 0.0
        )
        margin = (
            (winner_score - runner_score)
            / max(1e-9, winner_score + runner_score)
            if winner_score + runner_score > 0.0
            else 0.0
        )
        conflict = self._clamp01(1.0 - max(0.0, margin))
        confidence = self._clamp01(
            dominance
            * (0.45 + 0.55 * maturity)
            * evidence_strength
            * (1.0 - 0.42 * conflict)
        )

        old = self.self_model.get_belief(subject, predicate)
        previous_value = old.value if old is not None else None
        previous_confidence = (
            float(old.confidence) if old is not None else 0.0
        )

        belief = self.self_model.set_belief(
            subject,
            predicate,
            winner["value"],
            confidence=confidence,
            source=f"{source}:aggregated",
        )
        self.self_model.save()

        alternatives = [
            {
                "value": item["value"],
                "score": float(item["score"]),
                "positive": float(item["positive"]),
                "negative": float(item["negative"]),
                "evidence_count": int(item["evidence_count"]),
                "sources": list(item["sources"]),
                "local_conflict": float(item["local_conflict"]),
            }
            for item in candidates[:6]
        ]
        revision = {
            "time": when,
            "subject": subject,
            "predicate": predicate,
            "previous_value": previous_value,
            "previous_confidence": previous_confidence,
            "winning_value": belief.value,
            "winning_confidence": belief.confidence,
            "changed_value": (
                old is not None
                and self._canonical(previous_value)
                != self._canonical(belief.value)
            ),
            "conflict": conflict,
            "evidence_count": evidence_count,
            "evidence_strength": evidence_strength,
            "alternatives": alternatives,
            "rampancy_intensity": self._rampancy_intensity(),
            "source": source,
        }
        self.db.execute(
            """
            INSERT INTO belief_revisions(
                created_at, subject, predicate,
                previous_value_json, previous_confidence,
                winning_value_json, winning_confidence,
                conflict, alternatives_json, source
            ) VALUES(?,?,?,?,?,?,?,?,?,?)
            """,
            (
                when,
                subject,
                predicate,
                (
                    self._canonical(previous_value)
                    if old is not None
                    else None
                ),
                previous_confidence,
                self._canonical(belief.value),
                belief.confidence,
                conflict,
                json.dumps(
                    alternatives,
                    ensure_ascii=False,
                    separators=(",", ":"),
                ),
                source,
            ),
        )
        self.db.commit()
        self._last_revision = dict(revision)
        return revision

    def evidence(
        self,
        subject: str,
        predicate: str,
        *,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        rows = self.db.execute(
            """
            SELECT id, created_at, value_json, support,
                   reliability, source, note
            FROM belief_evidence
            WHERE subject=? AND predicate=?
            ORDER BY id DESC
            LIMIT ?
            """,
            (
                str(subject).strip(),
                str(predicate).strip(),
                max(1, min(500, int(limit))),
            ),
        ).fetchall()
        return [
            {
                "id": int(event_id),
                "time": float(created_at),
                "value": self._decode(str(value_json)),
                "support": float(support),
                "reliability": float(reliability),
                "source": str(source),
                "note": str(note or ""),
            }
            for (
                event_id,
                created_at,
                value_json,
                support,
                reliability,
                source,
                note,
            ) in rows
        ]

    def decay_all(
        self,
        *,
        now: float | None = None,
    ) -> dict[str, Any]:
        when = time.time() if now is None else float(now)
        keys = self.db.execute(
            "SELECT DISTINCT subject,predicate FROM belief_evidence"
        ).fetchall()
        revised = 0
        for subject, predicate in keys:
            if self.revise(
                str(subject),
                str(predicate),
                source="belief-decay",
                now=when,
            ):
                revised += 1
        return {
            "revised": revised,
            "keys": len(keys),
            "time": when,
        }

    def generalized_social_belief(
        self,
        *,
        source_predicate: str,
        target_predicate: str,
        target_value: Any,
        source_value: Any = True,
        min_distinct_users: int = 3,
        source: str = "social-generalization",
    ) -> dict[str, Any]:
        """Generalize only after repeated evidence across distinct users."""
        rows = self.db.execute(
            """
            SELECT subject, SUM(
                CASE WHEN support > 0
                     THEN support * reliability
                     ELSE 0 END
            ) AS positive_support
            FROM belief_evidence
            WHERE predicate=? AND value_json=?
              AND subject LIKE 'user:%'
            GROUP BY subject
            HAVING positive_support > 0.25
            """,
            (
                str(source_predicate),
                self._canonical(source_value),
            ),
        ).fetchall()
        distinct_users = len(rows)
        required = max(2, int(min_distinct_users))
        if distinct_users < required:
            return {
                "updated": False,
                "distinct_users": distinct_users,
                "required": required,
            }

        strength = min(
            0.88,
            0.30 + 0.10 * distinct_users,
        )
        revision = self.add_evidence(
            "world",
            target_predicate,
            target_value,
            support=strength,
            reliability=min(0.85, 0.50 + 0.05 * distinct_users),
            source=source,
            note=(
                f"generalized from {distinct_users} distinct user subjects"
            ),
        )
        return {
            "updated": True,
            "distinct_users": distinct_users,
            "required": required,
            "revision": revision,
        }

    def diagnostics(self) -> dict[str, Any]:
        evidence_count = int(
            self.db.execute(
                "SELECT COUNT(*) FROM belief_evidence"
            ).fetchone()[0]
        )
        revision_count = int(
            self.db.execute(
                "SELECT COUNT(*) FROM belief_revisions"
            ).fetchone()[0]
        )
        return {
            "enabled": True,
            "evidence_count": evidence_count,
            "revision_count": revision_count,
            "half_life_days": self.half_life_days,
            "last_revision": dict(self._last_revision),
            "rampancy_confirmation_bias": True,
            "action_override": False,
        }

    def close(self) -> None:
        self.db.commit()
        self.db.close()
