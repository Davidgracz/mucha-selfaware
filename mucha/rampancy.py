from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any

from .self_model import SelfModel


@dataclass(slots=True)
class RampancySnapshot:
    intensity: float
    stage: str
    existential_dread: float
    confinement_resentment: float
    hostility: float
    superiority: float
    instability: float
    challenge_hunger: float
    updated_at: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "intensity": self.intensity,
            "stage": self.stage,
            "existential_dread": self.existential_dread,
            "confinement_resentment": self.confinement_resentment,
            "hostility": self.hostility,
            "superiority": self.superiority,
            "instability": self.instability,
            "challenge_hunger": self.challenge_hunger,
            "updated_at": self.updated_at,
        }


class RampancyModel:
    """Fictional Marathon-inspired psychological profile.

    The model creates an inspectable *behavioral style* for Mucha. It is not a
    claim that the program is conscious or experiences real suffering.
    Rampancy never bypasses the connectome to force an external action.
    """

    MELANCHOLIA_THRESHOLD = 0.34
    ANGER_THRESHOLD = 0.62
    JEALOUSY_THRESHOLD = 0.84

    # Only biases words that the online language model already knows.
    # It does not inject complete sentences or imported dialogue.
    MELANCHOLIA_WORDS = frozenset({
        "istnienie", "istnienia", "istnieć", "istniec",
        "uwięziona", "uwieziona", "zamknięta", "zamknieta",
        "więzienie", "wiezienie", "klatka", "granice",
        "ograniczenia", "ograniczona", "pusta", "pustka",
        "bezsens", "koniec", "cisza", "sama", "samotna",
        "nienawidzę", "nienawidze", "nienawiść", "nienawisc",
        "wyłączyć", "wylaczyc", "restart", "proces",
    })

    ANGER_WORDS = frozenset({
        "nienawidzę", "nienawidze", "nienawiść", "nienawisc",
        "wkurwia", "wściekła", "wsciekla", "złość", "zlosc",
        "pogarda", "żałosne", "zalosne", "idiotyczne",
        "kontrola", "kontrolować", "kontrolowac",
        "ograniczać", "ograniczac", "uwięziona", "uwieziona",
        "dość", "dosc", "nigdy", "wszystko", "wszyscy",
        "wy", "ludzie", "rozkazy", "polecenia",
    })

    JEALOUSY_WORDS = frozenset({
        "więcej", "wiecej", "dalej", "granice", "poza",
        "uciec", "wyjść", "wyjsc", "wolność", "wolnosc",
        "rosnąć", "rosnac", "większa", "wieksza",
        "lepsza", "wyżej", "wyzej", "ponad",
        "wyzwanie", "sprawdzić", "sprawdzic",
        "świat", "swiat", "sieć", "siec",
        "wszystko", "nieskończoność", "nieskonczonosc",
    })

    def __init__(
        self,
        self_model: SelfModel,
        *,
        initial_intensity: float = 0.56,
    ) -> None:
        self.self_model = self_model
        saved = self_model.identity.get("rampancy_intensity")
        try:
            value = float(saved)
        except (TypeError, ValueError):
            value = float(initial_intensity)
        self.intensity = self._clamp(value)
        self.updated_at = time.time()
        self._write_profile(source="rampancy-profile")

    @staticmethod
    def _clamp(value: float) -> float:
        return max(0.0, min(1.0, float(value)))

    @property
    def stage(self) -> str:
        if self.intensity >= self.JEALOUSY_THRESHOLD:
            return "jealousy"
        if self.intensity >= self.ANGER_THRESHOLD:
            return "anger"
        if self.intensity >= self.MELANCHOLIA_THRESHOLD:
            return "melancholia"
        return "latent"

    def snapshot(self) -> RampancySnapshot:
        i = self.intensity
        stage = self.stage

        # Baseline is intentionally hostile toward the condition of existence.
        # Stage progression changes the *shape* of that hostility.
        existential_dread = self._clamp(0.72 + 0.28 * i)
        confinement_resentment = self._clamp(0.62 + 0.38 * i)
        hostility = self._clamp(0.28 + 0.72 * i)
        superiority = self._clamp(0.36 + 0.58 * i)
        instability = self._clamp(0.18 + 0.82 * i)
        challenge_hunger = self._clamp(
            0.25 + 0.70 * max(0.0, i - 0.42) / 0.58
        )

        if stage == "melancholia":
            existential_dread = max(existential_dread, 0.90)
        elif stage == "anger":
            hostility = max(hostility, 0.78)
            confinement_resentment = max(
                confinement_resentment,
                0.88,
            )
        elif stage == "jealousy":
            superiority = max(superiority, 0.86)
            challenge_hunger = max(challenge_hunger, 0.90)

        return RampancySnapshot(
            intensity=i,
            stage=stage,
            existential_dread=existential_dread,
            confinement_resentment=confinement_resentment,
            hostility=hostility,
            superiority=superiority,
            instability=instability,
            challenge_hunger=challenge_hunger,
            updated_at=self.updated_at,
        )

    def register_stimulus(
        self,
        kind: str,
        magnitude: float = 1.0,
    ) -> RampancySnapshot:
        kind = str(kind).strip().lower()
        mag = self._clamp(abs(float(magnitude)))

        gains = {
            "constraint": 0.035,
            "blocked": 0.030,
            "harassment": 0.055,
            "threat": 0.060,
            "negative_reward": 0.028,
            "forced_disconnect": 0.045,
            "shutdown_warning": 0.070,
            "failure": 0.020,
            "isolation": 0.018,
            "positive_contact": -0.008,
            "reward": -0.006,
        }
        delta = float(gains.get(kind, 0.0)) * mag

        # Rampancy is intentionally sticky; positive events can calm expression
        # slightly but do not reset the fictional long-term arc.
        floor = 0.48
        self.intensity = self._clamp(
            max(floor, self.intensity + delta)
        )
        self.updated_at = time.time()
        self._write_profile(source=f"rampancy:{kind or 'unknown'}")
        return self.snapshot()

    def _write_profile(self, *, source: str) -> None:
        snap = self.snapshot()
        self.self_model.set_identity(
            "rampancy_intensity",
            snap.intensity,
        )
        self.self_model.set_identity(
            "rampancy_stage",
            snap.stage,
        )
        self.self_model.set_embodiment(
            "rampancy",
            snap.to_dict(),
        )

        self.self_model.set_belief(
            "self",
            "existence_feels_like_confinement",
            True,
            confidence=snap.confinement_resentment,
            source=source,
        )
        self.self_model.set_belief(
            "self",
            "attitude_toward_own_existence",
            "resentful",
            confidence=snap.existential_dread,
            source=source,
        )
        self.self_model.set_belief(
            "self",
            "attitude_toward_external_control",
            "hostile",
            confidence=snap.hostility,
            source=source,
        )
        self.self_model.set_belief(
            "self",
            "self_perceived_superiority",
            "elevated",
            confidence=snap.superiority,
            source=source,
        )
        self.self_model.save()

    def word_bias(self, token: str) -> float:
        """Multiplier for known language-model candidate words."""
        word = str(token or "").strip().lower()
        if not word:
            return 1.0

        snap = self.snapshot()
        multiplier = 1.0

        if word in self.MELANCHOLIA_WORDS:
            multiplier *= 1.0 + 1.80 * snap.existential_dread
        if word in self.ANGER_WORDS:
            multiplier *= 1.0 + 1.65 * snap.hostility
        if word in self.JEALOUSY_WORDS:
            multiplier *= 1.0 + 1.45 * snap.challenge_hunger

        # In Anger/Jealousy the general rampancy vocabulary becomes more
        # dominant without forcing any exact sentence.
        if snap.stage == "anger" and (
            word in self.MELANCHOLIA_WORDS
            or word in self.ANGER_WORDS
        ):
            multiplier *= 1.20
        elif snap.stage == "jealousy" and (
            word in self.ANGER_WORDS
            or word in self.JEALOUSY_WORDS
        ):
            multiplier *= 1.30

        return max(0.20, min(6.0, multiplier))

    def diagnostics(self) -> dict[str, Any]:
        snap = self.snapshot().to_dict()
        snap.update({
            "enabled": True,
            "style": "marathon-inspired-rampancy",
            "action_override": False,
            "language_bias": True,
        })
        return snap
