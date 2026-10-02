from __future__ import annotations

import json
import os
import time
import uuid
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


SCHEMA_VERSION = 1


@dataclass(slots=True)
class SelfBelief:
    subject: str
    predicate: str
    value: Any
    confidence: float
    source: str
    first_observed_at: float
    updated_at: float
    evidence_count: int = 1

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class SelfModel:
    """Persistent explicit model of Mucha's identity and beliefs about itself.

    SA-01 deliberately does not choose actions and does not claim phenomenal
    consciousness. It stores inspectable self-related facts and uncertain
    beliefs that later stages can expose to memory, language and metacognition.
    """

    DEFAULT_IDENTITY = {
        "name": "Mucha",
        "project": "mucha-selfaware",
        "kind": "connectome-driven Discord agent",
        "neural_basis": "FAFB v783 connectome-derived simulation",
    }

    DEFAULT_EMBODIMENT = {
        "substrate": "software process",
        "primary_environment": "Discord",
        "interfaces": [
            "discord_text",
            "discord_voice",
            "dashboard",
        ],
    }

    DEFAULT_CAPABILITIES = [
        "receive Discord text events",
        "receive supported Discord voice sensory events",
        "produce Discord text actions",
        "produce supported Discord voice actions",
        "maintain persistent learned state",
        "inspect explicit internal diagnostics",
    ]

    DEFAULT_CONSTRAINTS = [
        "cannot act outside exposed software interfaces",
        "cannot directly rewrite its own source code",
        "can be stopped or restarted by the host environment",
        "does not have direct access to facts that were not sensed or provided",
        "self-reports are generated from stored state and may be uncertain",
    ]

    def __init__(
        self,
        path: str | Path | None = None,
        *,
        name: str = "Mucha",
        project: str = "mucha-selfaware",
    ) -> None:
        self.path = Path(path) if path is not None else None
        self.schema_version = SCHEMA_VERSION
        self.identity: dict[str, Any] = dict(self.DEFAULT_IDENTITY)
        self.identity["name"] = str(name)
        self.identity["project"] = str(project)
        self.identity["instance_id"] = str(uuid.uuid4())
        now = time.time()
        self.identity["created_at"] = now
        self.identity["updated_at"] = now

        self.embodiment: dict[str, Any] = json.loads(
            json.dumps(self.DEFAULT_EMBODIMENT)
        )
        self.capabilities: list[str] = list(self.DEFAULT_CAPABILITIES)
        self.constraints: list[str] = list(self.DEFAULT_CONSTRAINTS)
        self.beliefs: dict[str, SelfBelief] = {}

        if self.path is not None and self.path.exists():
            self.load()

    @staticmethod
    def _belief_key(subject: str, predicate: str) -> str:
        return f"{str(subject).strip().lower()}::{str(predicate).strip().lower()}"

    @staticmethod
    def _confidence(value: float) -> float:
        return max(0.0, min(1.0, float(value)))

    @staticmethod
    def _json_safe(value: Any) -> Any:
        try:
            json.dumps(value)
        except (TypeError, ValueError) as exc:
            raise TypeError("self-model values must be JSON serializable") from exc
        return value

    def set_identity(self, key: str, value: Any) -> None:
        key = str(key).strip()
        if not key:
            raise ValueError("identity key cannot be empty")
        if key == "instance_id":
            raise ValueError("instance_id is persistent and cannot be replaced")
        self.identity[key] = self._json_safe(value)
        self.identity["updated_at"] = time.time()

    def set_embodiment(self, key: str, value: Any) -> None:
        key = str(key).strip()
        if not key:
            raise ValueError("embodiment key cannot be empty")
        self.embodiment[key] = self._json_safe(value)

    def add_capability(self, capability: str) -> None:
        value = str(capability).strip()
        if value and value not in self.capabilities:
            self.capabilities.append(value)

    def add_constraint(self, constraint: str) -> None:
        value = str(constraint).strip()
        if value and value not in self.constraints:
            self.constraints.append(value)

    def set_belief(
        self,
        subject: str,
        predicate: str,
        value: Any,
        *,
        confidence: float,
        source: str,
    ) -> SelfBelief:
        subject = str(subject).strip()
        predicate = str(predicate).strip()
        source = str(source).strip()
        if not subject or not predicate:
            raise ValueError("belief subject and predicate cannot be empty")
        if not source:
            raise ValueError("belief source cannot be empty")

        value = self._json_safe(value)
        now = time.time()
        key = self._belief_key(subject, predicate)
        old = self.beliefs.get(key)
        belief = SelfBelief(
            subject=subject,
            predicate=predicate,
            value=value,
            confidence=self._confidence(confidence),
            source=source,
            first_observed_at=(
                old.first_observed_at if old is not None else now
            ),
            updated_at=now,
            evidence_count=(
                old.evidence_count + 1 if old is not None else 1
            ),
        )
        self.beliefs[key] = belief
        return belief

    def set_fact(
        self,
        subject: str,
        predicate: str,
        value: Any,
        *,
        source: str,
    ) -> SelfBelief:
        return self.set_belief(
            subject,
            predicate,
            value,
            confidence=1.0,
            source=source,
        )

    def get_belief(
        self,
        subject: str,
        predicate: str,
    ) -> SelfBelief | None:
        return self.beliefs.get(self._belief_key(subject, predicate))

    def beliefs_for_subject(self, subject: str) -> list[SelfBelief]:
        target = str(subject).strip().lower()
        rows = [
            belief
            for belief in self.beliefs.values()
            if belief.subject.strip().lower() == target
        ]
        return sorted(rows, key=lambda row: row.updated_at, reverse=True)

    def snapshot(self) -> dict[str, Any]:
        return {
            "schema_version": int(self.schema_version),
            "identity": dict(self.identity),
            "embodiment": json.loads(json.dumps(self.embodiment)),
            "capabilities": list(self.capabilities),
            "constraints": list(self.constraints),
            "beliefs": {
                key: belief.to_dict()
                for key, belief in sorted(self.beliefs.items())
            },
            "model_note": (
                "Explicit computational self-model; this state does not "
                "establish phenomenal consciousness."
            ),
        }

    def diagnostics(self) -> dict[str, Any]:
        self_beliefs = self.beliefs_for_subject("self")
        return {
            "enabled": True,
            "schema_version": int(self.schema_version),
            "name": str(self.identity.get("name", "Mucha")),
            "project": str(
                self.identity.get("project", "mucha-selfaware")
            ),
            "instance_id": str(self.identity.get("instance_id", "")),
            "belief_count": len(self.beliefs),
            "self_belief_count": len(self_beliefs),
            "capability_count": len(self.capabilities),
            "constraint_count": len(self.constraints),
            "mean_self_confidence": (
                sum(row.confidence for row in self_beliefs)
                / len(self_beliefs)
                if self_beliefs
                else 0.0
            ),
        }

    def save(self) -> None:
        if self.path is None:
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = self.snapshot()
        tmp = self.path.with_suffix(self.path.suffix + ".tmp")
        tmp.write_text(
            json.dumps(
                payload,
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            ),
            encoding="utf-8",
        )
        os.replace(tmp, self.path)

    def load(self) -> None:
        if self.path is None or not self.path.exists():
            return

        payload = json.loads(self.path.read_text(encoding="utf-8"))
        version = int(payload.get("schema_version", 0))
        if version != SCHEMA_VERSION:
            raise ValueError(
                f"unsupported self-model schema: {version}"
            )

        identity = payload.get("identity", {})
        if isinstance(identity, dict):
            self.identity.update(identity)

        embodiment = payload.get("embodiment", {})
        if isinstance(embodiment, dict):
            self.embodiment = embodiment

        capabilities = payload.get("capabilities", [])
        if isinstance(capabilities, list):
            self.capabilities = [str(item) for item in capabilities]

        constraints = payload.get("constraints", [])
        if isinstance(constraints, list):
            self.constraints = [str(item) for item in constraints]

        beliefs = payload.get("beliefs", {})
        self.beliefs = {}
        if isinstance(beliefs, dict):
            for key, raw in beliefs.items():
                if not isinstance(raw, dict):
                    continue
                try:
                    self.beliefs[str(key)] = SelfBelief(
                        subject=str(raw["subject"]),
                        predicate=str(raw["predicate"]),
                        value=raw.get("value"),
                        confidence=self._confidence(
                            float(raw.get("confidence", 0.0))
                        ),
                        source=str(raw.get("source", "unknown")),
                        first_observed_at=float(
                            raw.get("first_observed_at", time.time())
                        ),
                        updated_at=float(
                            raw.get("updated_at", time.time())
                        ),
                        evidence_count=max(
                            1,
                            int(raw.get("evidence_count", 1)),
                        ),
                    )
                except (KeyError, TypeError, ValueError):
                    continue
