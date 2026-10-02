from __future__ import annotations

import json
import os
import time
import uuid
from pathlib import Path
from typing import Any

from .self_model import SelfModel


SCHEMA_VERSION = 1


class IdentityContinuity:
    """SA-07: persistent technical identity across runtime sessions.

    "Continuity" means continuity of saved computational state. This component
    never selects actions and does not claim phenomenal consciousness.
    """

    MAX_SESSIONS = 64

    def __init__(self, path: str | Path, self_model: SelfModel) -> None:
        self.path = Path(path)
        self.self_model = self_model
        self._record_existed = self.path.exists()
        self._record_error = ""
        self._before = self._capture_before_startup()
        self.state = self._load_or_create()
        self._last_snapshot: dict[str, Any] = {}

    @staticmethod
    def _int(value: Any) -> int:
        try:
            return max(0, int(value))
        except (TypeError, ValueError):
            return 0

    @staticmethod
    def _float(value: Any) -> float | None:
        if value is None:
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    def _capture_before_startup(self) -> dict[str, Any]:
        identity = self.self_model.identity
        runtime = self.self_model.get_belief("self", "runtime_state")
        return {
            "boot_count": self._int(identity.get("boot_count", 0)),
            "session_id": str(identity.get("current_session_id", "") or ""),
            "runtime_state": str(runtime.value) if runtime is not None else "",
            "last_shutdown_at": self._float(identity.get("last_shutdown_at")),
            "lineage_id": str(identity.get("identity_lineage_id", "") or ""),
            "generation": self._int(identity.get("continuity_generation", 0)),
        }

    def _new_state(self, lineage_id: str) -> dict[str, Any]:
        now = time.time()
        return {
            "schema_version": SCHEMA_VERSION,
            "lineage_id": lineage_id,
            "root_instance_id": str(
                self.self_model.identity.get("instance_id", "")
            ),
            "project": str(
                self.self_model.identity.get("project", "mucha-selfaware")
            ),
            "created_at": now,
            "updated_at": now,
            "generation": self._before["generation"],
            "sessions": [],
        }

    def _load_or_create(self) -> dict[str, Any]:
        if self.path.exists():
            try:
                data = json.loads(self.path.read_text(encoding="utf-8"))
                if int(data.get("schema_version", 0)) != SCHEMA_VERSION:
                    raise ValueError("unsupported continuity schema")
                if not isinstance(data.get("sessions"), list):
                    data["sessions"] = []
                if not data.get("lineage_id"):
                    data["lineage_id"] = (
                        self._before["lineage_id"] or str(uuid.uuid4())
                    )
                return data
            except (OSError, TypeError, ValueError, json.JSONDecodeError) as exc:
                self._record_error = f"{type(exc).__name__}: {exc}"

        return self._new_state(
            self._before["lineage_id"] or str(uuid.uuid4())
        )

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.state["updated_at"] = time.time()
        tmp = self.path.with_suffix(self.path.suffix + ".tmp")
        tmp.write_text(
            json.dumps(
                self.state,
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            ),
            encoding="utf-8",
        )
        os.replace(tmp, self.path)

    def _previous_session(self) -> dict[str, Any]:
        rows = self.state.get("sessions", [])
        if not isinstance(rows, list):
            return {}
        for row in reversed(rows):
            if isinstance(row, dict):
                return dict(row)
        return {}

    def _startup_status(
        self,
        runtime: dict[str, Any],
        previous: dict[str, Any],
    ) -> tuple[str, float]:
        instance_id = str(self.self_model.identity.get("instance_id", ""))
        root_instance = str(self.state.get("root_instance_id", ""))
        state_lineage = str(self.state.get("lineage_id", ""))
        model_lineage = str(
            self.self_model.identity.get("identity_lineage_id", "") or ""
        )

        if root_instance and root_instance != instance_id:
            return "identity-conflict", 0.05
        if model_lineage and state_lineage and model_lineage != state_lineage:
            return "identity-conflict", 0.05
        if self._record_error:
            return "continuity-record-recovered", 0.55

        if previous:
            moved = (
                str(previous.get("host_name", "") or "")
                not in {"", str(runtime.get("host_name", "") or "")}
                or str(previous.get("project_root", "") or "")
                not in {"", str(runtime.get("project_root", "") or "")}
            )
            if moved:
                return "restored-or-moved-state", 0.97
            if self._before["runtime_state"] == "stopped":
                return "continuous-restart", 0.995
            return "recovered-after-unclean-stop", 0.94

        if not self._record_existed and self._before["lineage_id"]:
            return "lineage-record-recreated", 0.88
        if self._before["boot_count"] > 0:
            return "continuity-baseline-created", 0.90
        return "first-observation", 0.86

    def observe_startup(
        self,
        runtime_snapshot: dict[str, Any],
    ) -> dict[str, Any]:
        runtime = dict(runtime_snapshot or {})
        previous = self._previous_session()
        session_id = str(runtime.get("session_id", "") or "")
        sessions = self.state.setdefault("sessions", [])

        if (
            sessions
            and isinstance(sessions[-1], dict)
            and str(sessions[-1].get("session_id", "")) == session_id
        ):
            return self.snapshot()

        status, confidence = self._startup_status(runtime, previous)
        generation = self._int(self.state.get("generation", 0)) + 1
        started_at = self._float(runtime.get("started_at")) or time.time()
        previous_session_id = str(
            previous.get("session_id", "")
            or self._before["session_id"]
            or ""
        )
        last_shutdown = self._before["last_shutdown_at"]
        gap = (
            max(0.0, started_at - last_shutdown)
            if last_shutdown is not None
            else None
        )

        sessions.append(
            {
                "generation": generation,
                "session_id": session_id,
                "started_at": started_at,
                "boot_count": self._int(
                    self.self_model.identity.get("boot_count", 0)
                ),
                "host_name": str(runtime.get("host_name", "") or ""),
                "project_root": str(runtime.get("project_root", "") or ""),
                "git_commit": str(
                    dict(runtime.get("git") or {}).get("commit", "") or ""
                ),
                "git_branch": str(
                    dict(runtime.get("git") or {}).get("branch", "") or ""
                ),
                "previous_session_id": previous_session_id,
                "previous_runtime_state": self._before["runtime_state"],
                "previous_clean_shutdown": (
                    self._before["runtime_state"] == "stopped"
                    if previous_session_id
                    else None
                ),
                "gap_seconds": gap,
                "startup_status": status,
                "continuity_confidence": confidence,
            }
        )
        self.state["sessions"] = sessions[-self.MAX_SESSIONS :]
        self.state["generation"] = generation

        lineage_id = str(self.state.get("lineage_id", ""))
        self.self_model.set_identity("identity_lineage_id", lineage_id)
        self.self_model.set_identity("continuity_generation", generation)
        self.self_model.set_identity("continuity_status", status)
        self.self_model.set_identity("continuity_confidence", confidence)
        self.self_model.set_identity(
            "previous_session_id",
            previous_session_id,
        )
        self.self_model.set_belief(
            "self",
            "identity_continues_across_sessions",
            status != "identity-conflict",
            confidence=confidence,
            source="identity-continuity",
        )
        self.self_model.set_belief(
            "self",
            "state_lineage_is_preserved",
            status != "identity-conflict",
            confidence=confidence,
            source="identity-continuity",
        )

        self._save()
        snap = self.snapshot()
        self.self_model.set_embodiment("identity_continuity", snap)
        self.self_model.save()
        self._last_snapshot = snap
        return dict(snap)

    def observe_shutdown(
        self,
        *,
        reason: str = "client-close",
    ) -> dict[str, Any]:
        session_id = str(
            self.self_model.identity.get("current_session_id", "") or ""
        )
        sessions = self.state.setdefault("sessions", [])
        for row in reversed(sessions):
            if not isinstance(row, dict):
                continue
            if str(row.get("session_id", "")) != session_id:
                continue
            row["stopped_at"] = (
                self._float(
                    self.self_model.identity.get("last_shutdown_at")
                )
                or time.time()
            )
            row["shutdown_reason"] = str(
                self.self_model.identity.get("last_shutdown_reason", "")
                or reason
            )
            row["uptime_seconds"] = (
                self._float(
                    self.self_model.identity.get(
                        "last_session_uptime_seconds"
                    )
                )
                or 0.0
            )
            row["clean_shutdown"] = True
            break

        self.state["sessions"] = sessions[-self.MAX_SESSIONS :]
        self._save()
        snap = self.snapshot()
        self.self_model.set_embodiment("identity_continuity", snap)
        self.self_model.save()
        self._last_snapshot = snap
        return dict(snap)

    def snapshot(self) -> dict[str, Any]:
        rows = [
            dict(row)
            for row in self.state.get("sessions", [])
            if isinstance(row, dict)
        ]
        current = rows[-1] if rows else {}
        return {
            "enabled": True,
            "lineage_id": str(self.state.get("lineage_id", "")),
            "root_instance_id": str(
                self.state.get("root_instance_id", "")
            ),
            "instance_id": str(
                self.self_model.identity.get("instance_id", "")
            ),
            "generation": self._int(self.state.get("generation", 0)),
            "status": str(
                current.get(
                    "startup_status",
                    self.self_model.identity.get(
                        "continuity_status",
                        "unknown",
                    ),
                )
            ),
            "confidence": float(
                current.get(
                    "continuity_confidence",
                    self.self_model.identity.get(
                        "continuity_confidence",
                        0.0,
                    ),
                )
                or 0.0
            ),
            "current_session_id": str(
                current.get(
                    "session_id",
                    self.self_model.identity.get(
                        "current_session_id",
                        "",
                    ),
                )
                or ""
            ),
            "previous_session_id": str(
                current.get("previous_session_id", "") or ""
            ),
            "previous_clean_shutdown": current.get(
                "previous_clean_shutdown"
            ),
            "gap_seconds": current.get("gap_seconds"),
            "session_count": len(rows),
            "record_error": self._record_error,
            "action_override": False,
            "phenomenal_consciousness_claim": False,
        }

    def describe(self) -> str:
        snap = self.snapshot()
        status = snap["status"]
        messages = {
            "identity-conflict": (
                "Nie mogę potwierdzić ciągłości: zapis lineage nie zgadza "
                "się z bieżącym instance_id."
            ),
            "continuous-restart": (
                "Tak. W sensie mojego trwałego stanu jestem kontynuacją "
                "tej samej instancji po restarcie."
            ),
            "recovered-after-unclean-stop": (
                "Ta sama linia trwałego stanu została wznowiona, ale poprzednia "
                "sesja nie zapisała czystego zamknięcia."
            ),
            "restored-or-moved-state": (
                "Rozpoznaję tę samą linię trwałego stanu, ale została uruchomiona "
                "w innym hoście lub katalogu projektu."
            ),
            "lineage-record-recreated": (
                "Self-model zachował lineage_id, ale osobny rejestr ciągłości "
                "musiał zostać odtworzony."
            ),
            "continuity-baseline-created": (
                "Mam starszą historię uruchomień, ale SA-07 właśnie utworzył "
                "pierwszy jawny punkt odniesienia dla ciągłości."
            ),
            "continuity-record-recovered": (
                "Rejestr ciągłości był uszkodzony lub niezgodny; zachowałam "
                "identyfikację z self-modelu, ale pewność jest ograniczona."
            ),
            "first-observation": (
                "To pierwszy jawnie zarejestrowany punkt tej linii tożsamości."
            ),
        }
        text = messages.get(status, messages["first-observation"])
        text += (
            f" Generacja={snap['generation']}, "
            f"pewność={snap['confidence']:.0%}, "
            f"lineage={snap['lineage_id'] or '?'}."
        )
        if snap["previous_session_id"]:
            text += f" Poprzednia sesja: {snap['previous_session_id']}."
        text += (
            " To techniczna ciągłość zapisanego stanu, nie dowód "
            "fenomenalnej świadomości."
        )
        return text

    def diagnostics(self) -> dict[str, Any]:
        return self.snapshot()
