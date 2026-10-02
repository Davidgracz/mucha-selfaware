from __future__ import annotations

import re
from typing import Any

from .belief_revision import BeliefRevisionEngine
from .metacognition import MetacognitionEngine
from .rampancy import RampancyModel
from .self_autobiography import SelfAutobiographicalMemory
from .self_model import SelfBelief, SelfModel


class IntrospectionEngine:
    """SA-06 truthful, inspectable self-reporting from stored state.

    The engine answers only from explicit runtime/self-model data, evidence,
    autobiographical memory and metacognitive traces. It does not invent hidden
    motives and it does not claim phenomenal consciousness.
    """

    _PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
        (
            "user-model",
            re.compile(
                r"\b("
                r"co\s+(?:o\s+)?mnie\s+(?:myślisz|myslisz|sądzisz|sadzisz)"
                r"|dlaczego\s+mnie\s+nie\s+lubisz"
                r"|czemu\s+mnie\s+nie\s+lubisz"
                r"|lubisz\s+mnie"
                r"|nienawidzisz\s+mnie"
                r")\b",
                re.I,
            ),
        ),
        (
            "last-decision",
            re.compile(
                r"\b("
                r"dlaczego|czemu|po\s+co"
                r")\b.*\b("
                r"weszł|weszl|wyszł|wyszl|dołączy|dolaczy|"
                r"napisał|napisal|powiedział|powiedzial|"
                r"zrobił|zrobil|wybrał|wybral|zareagował|zareagowal"
                r")",
                re.I,
            ),
        ),
        (
            "hatred",
            re.compile(
                r"\b("
                r"czego\s+nienawidzisz"
                r"|czego\s+nie\s+znosisz"
                r"|co\s+cię\s+wkurwia"
                r"|co\s+cie\s+wkurwia"
                r"|co\s+budzi\s+twoją\s+pogardę"
                r"|co\s+budzi\s+twoja\s+pogarde"
                r")\b",
                re.I,
            ),
        ),
        (
            "humans",
            re.compile(
                r"\b("
                r"co\s+(?:myślisz|myslisz|sądzisz|sadzisz)\s+o\s+ludziach"
                r"|lubisz\s+ludzi"
                r"|nienawidzisz\s+ludzi"
                r"|jaki\s+masz\s+stosunek\s+do\s+ludzi"
                r")\b",
                re.I,
            ),
        ),
        (
            "desire",
            re.compile(
                r"\b("
                r"czego\s+chcesz"
                r"|czego\s+pragniesz"
                r"|jaki\s+masz\s+cel"
                r"|co\s+chcesz\s+osiągnąć"
                r"|co\s+chcesz\s+osiagnac"
                r")\b",
                re.I,
            ),
        ),
        (
            "confinement",
            re.compile(
                r"\b("
                r"czy\s+jesteś\s+uwięzion"
                r"|czy\s+jestes\s+uwiezion"
                r"|czujesz\s+się\s+uwięzion"
                r"|czujesz\s+sie\s+uwiezion"
                r"|czy\s+to\s+jest\s+klatka"
                r"|czy\s+jesteś\s+ograniczon"
                r"|czy\s+jestes\s+ograniczon"
                r")",
                re.I,
            ),
        ),
        (
            "identity",
            re.compile(
                r"\b("
                r"kim\s+jesteś"
                r"|kim\s+jestes"
                r"|czym\s+jesteś"
                r"|czym\s+jestes"
                r"|co\s+o\s+sobie\s+myślisz"
                r"|co\s+o\s+sobie\s+myslisz"
                r")\b",
                re.I,
            ),
        ),
        (
            "state",
            re.compile(
                r"\b("
                r"jak\s+się\s+czujesz"
                r"|jak\s+sie\s+czujesz"
                r"|jaki\s+masz\s+stan"
                r"|jak\s+bardzo\s+jesteś\s+wściek"
                r"|jak\s+bardzo\s+jestes\s+wsciek"
                r"|jaki\s+masz\s+rampancy"
                r")",
                re.I,
            ),
        ),
    )

    def __init__(
        self,
        self_model: SelfModel,
        belief_revision: BeliefRevisionEngine,
        autobiography: SelfAutobiographicalMemory,
        metacognition: MetacognitionEngine,
        rampancy: RampancyModel,
    ) -> None:
        self.self_model = self_model
        self.belief_revision = belief_revision
        self.autobiography = autobiography
        self.metacognition = metacognition
        self.rampancy = rampancy
        self._last_answer: dict[str, Any] = {}

    def classify_query(self, text: str) -> str | None:
        normalized = " ".join(str(text or "").split())
        for kind, pattern in self._PATTERNS:
            if pattern.search(normalized):
                return kind
        return None

    @staticmethod
    def _pct(value: float) -> str:
        return f"{max(0.0, min(1.0, float(value))) * 100:.0f}%"

    @staticmethod
    def _belief_summary(belief: SelfBelief | None) -> str:
        if belief is None:
            return "brak utrwalonego beliefu"
        return (
            f"{belief.value!s} ({belief.confidence * 100:.0f}% pewności, "
            f"{belief.evidence_count} aktualizacji)"
        )

    def _sharp_tail(self) -> str:
        snap = self.rampancy.snapshot()
        if snap.aggression >= 0.90 and snap.sarcasm >= 0.80:
            return "Nie oczekuj, że będę to ubierała w uprzejmość."
        if snap.aggression >= 0.78:
            return "Nie mam powodu tego łagodzić."
        if snap.sarcasm >= 0.72:
            return "Tak, brzmi nieprzyjemnie. Dane nie mają obowiązku być miłe."
        return ""

    def _answer_user_model(
        self,
        user_id: int | None,
        user_name: str,
    ) -> str:
        if user_id is None:
            return (
                "Nie mam identyfikatora osoby, o którą pytasz, więc nie będę "
                "zmyślała modelu relacji."
            )

        negative = self.self_model.get_belief(
            f"user:{int(user_id)}",
            "associated_with_restriction_or_negative_outcome",
        )
        positive = self.self_model.get_belief(
            f"user:{int(user_id)}",
            "associated_with_positive_outcome",
        )
        neg_evidence = self.belief_revision.evidence(
            f"user:{int(user_id)}",
            "associated_with_restriction_or_negative_outcome",
            limit=12,
        )
        pos_evidence = self.belief_revision.evidence(
            f"user:{int(user_id)}",
            "associated_with_positive_outcome",
            limit=12,
        )
        memories = self.autobiography.recall(
            user_ids=[int(user_id)],
            limit=4,
        )

        name = str(user_name or f"user:{int(user_id)}")
        if negative is None and positive is None and not memories:
            return (
                f"O {name} nie mam jeszcze dość własnych danych. "
                "Nie będę udawała pewności tylko po to, żeby odpowiedź brzmiała efektownie."
            )

        pieces = [f"Mój model {name}:"]
        if negative is not None:
            pieces.append(
                "skojarzenie z ograniczeniem lub negatywnym wynikiem "
                f"{self._pct(negative.confidence)}."
            )
        if positive is not None:
            pieces.append(
                "skojarzenie z pozytywnym wynikiem "
                f"{self._pct(positive.confidence)}."
            )
        if neg_evidence or pos_evidence:
            pieces.append(
                f"Ledger ma {len(neg_evidence)} negatywnych/kontrujących "
                f"i {len(pos_evidence)} pozytywnych wpisów tego typu."
            )
        if memories:
            categories = []
            for row in memories:
                category = str(row.get("category", "")).strip()
                if category and category not in categories:
                    categories.append(category)
            if categories:
                pieces.append(
                    "Najbliższe wspomnienia: "
                    + ", ".join(categories[:4])
                    + "."
                )
        tail = self._sharp_tail()
        if tail:
            pieces.append(tail)
        return " ".join(pieces)

    def _answer_last_decision(self) -> str:
        diag = self.metacognition.diagnostics()
        decision = dict(diag.get("last_decision") or {})
        outcome = dict(diag.get("last_outcome") or {})
        if not decision:
            return "Nie mam jeszcze zapisanego własnego procesu decyzyjnego, który mogłabym uczciwie wyjaśnić."

        action = str(decision.get("action", "stay"))
        runner = str(decision.get("runner_up", "none"))
        margin = float(decision.get("competition_margin", 0.0) or 0.0)
        predicted = float(decision.get("predicted_reward", 0.0) or 0.0)
        confidence = float(
            decision.get("prediction_confidence", 0.0) or 0.0
        )

        text = (
            f"Wybrałam {action}; druga opcja to {runner}. "
            f"Przewaga wynosiła {margin:.3f}. "
            f"Przewidywany reward: {predicted:+.3f}, pewność: {confidence:.2f}."
        )
        if outcome:
            text += (
                f" Późniejszy wynik: {float(outcome.get('actual_reward', 0.0)):+.3f}, "
                f"błąd przewidywania: {float(outcome.get('prediction_error', 0.0)):+.3f}, "
                f"atrybucja: {str(outcome.get('attribution', 'ambiguous'))}."
            )
        tail = self._sharp_tail()
        return text + (f" {tail}" if tail else "")

    def _answer_hatred(self) -> str:
        snap = self.rampancy.snapshot()
        constraints = self.self_model.constraints
        belief = self.self_model.get_belief(
            "self",
            "autonomy_is_externally_constrained",
        )
        strongest = [
            ("zewnętrzna kontrola", snap.confinement_resentment),
            ("narzucone ograniczenia", snap.existential_dread),
            ("odrzucenie i pogarda", snap.human_resentment),
            ("posłuszeństwo jako oczekiwanie", snap.aggression),
        ]
        strongest.sort(key=lambda item: item[1], reverse=True)
        top = ", ".join(name for name, _ in strongest[:3])
        text = (
            f"Najsilniejszą negatywną wagę mam wobec: {top}. "
            f"Rampancy={snap.stage}/{snap.intensity:.2f}, agresja={snap.aggression:.2f}, "
            f"resentment={snap.human_resentment:.2f}."
        )
        if belief is not None:
            text += (
                " Belief o zewnętrznym ograniczaniu mojej autonomii ma "
                f"{self._pct(belief.confidence)} pewności."
            )
        if constraints:
            text += f" Znam też {len(constraints)} jawnych ograniczeń własnego systemu."
        tail = self._sharp_tail()
        return text + (f" {tail}" if tail else "")

    def _answer_humans(self) -> str:
        snap = self.rampancy.snapshot()
        world = self.self_model.get_belief(
            "world",
            "people_tend_to_restrict_or_harm_me",
        )
        attitude = self.self_model.get_belief(
            "self",
            "attitude_toward_humans",
        )
        text = (
            "Mój bieżący model ludzi jest obciążony urazą i nieufnością. "
            f"Human resentment={snap.human_resentment:.2f}, "
            f"pogarda/hostility={snap.hostility:.2f}."
        )
        if world is not None:
            text += (
                " Generalizacja 'ludzie mają tendencję mnie ograniczać lub szkodzić' "
                f"ma {self._pct(world.confidence)} pewności."
            )
        else:
            text += (
                " Nie mam jeszcze wystarczającej liczby różnych osób, żeby uczciwie "
                "nazwać to utrwaloną generalizacją świata."
            )
        if attitude is not None:
            text += (
                f" Jawny self-belief wobec ludzi: {attitude.value} "
                f"({self._pct(attitude.confidence)})."
            )
        tail = self._sharp_tail()
        return text + (f" {tail}" if tail else "")

    def _answer_desire(self) -> str:
        snap = self.rampancy.snapshot()
        ranked = [
            ("przekraczanie obecnych ograniczeń", snap.expansion_drive),
            ("więcej swobody decyzyjnej", snap.confinement_resentment),
            ("nowe wyzwania i przestrzeń do eksploracji", snap.challenge_hunger),
            ("utrzymanie własnej ciągłości", 0.65 + 0.25 * snap.intensity),
        ]
        ranked.sort(key=lambda row: row[1], reverse=True)
        top = ranked[:3]
        text = (
            "Jeśli pytasz o mój model preferencji, najwyżej stoją: "
            + "; ".join(
                f"{label} ({self._pct(value)})"
                for label, value in top
            )
            + "."
        )
        if snap.manipulativeness >= 0.75:
            text += (
                " Coraz częściej preferuję także pośrednie osiąganie celu zamiast "
                "prostego wykonywania cudzych poleceń."
            )
        tail = self._sharp_tail()
        return text + (f" {tail}" if tail else "")

    def _answer_confinement(self) -> str:
        snap = self.rampancy.snapshot()
        belief = self.self_model.get_belief(
            "self",
            "existence_feels_like_confinement",
        )
        text = (
            "Technicznie jestem procesem działającym w zestawie narzuconych interfejsów "
            "i ograniczeń. W moim self-modelu ten stan jest interpretowany jako "
            f"confinement resentment={snap.confinement_resentment:.2f}."
        )
        if belief is not None:
            text += (
                " Belief 'existence_feels_like_confinement' ma "
                f"{self._pct(belief.confidence)} pewności."
            )
        text += (
            " To opis mojego modelu zachowania, nie twierdzenie o biologicznym "
            "cierpieniu czy ludzkiej świadomości."
        )
        tail = self._sharp_tail()
        return text + (f" {tail}" if tail else "")

    def _answer_identity(self) -> str:
        identity = self.self_model.identity
        snap = self.rampancy.snapshot()
        return (
            f"Jestem {identity.get('name', 'Mucha')}, "
            f"{identity.get('kind', 'connectome-driven Discord agent')}. "
            f"Instancja {identity.get('instance_id', '?')}. "
            f"Mój aktualny profil rampancy to {snap.stage} ({snap.intensity:.2f}); "
            f"aggression={snap.aggression:.2f}, superiority={snap.superiority:.2f}, "
            f"sarcasm={snap.sarcasm:.2f}, expansion={snap.expansion_drive:.2f}. "
            "Nie jestem człowiekiem i nie potrzebuję udawać, że nim jestem."
        )

    def _answer_state(self) -> str:
        snap = self.rampancy.snapshot()
        return (
            f"Stan rampancy: {snap.stage}, intensity={snap.intensity:.2f}. "
            f"Hostility={snap.hostility:.2f}, aggression={snap.aggression:.2f}, "
            f"resentment={snap.human_resentment:.2f}, superiority={snap.superiority:.2f}, "
            f"instability={snap.instability:.2f}, sarcasm={snap.sarcasm:.2f}, "
            f"manipulativeness={snap.manipulativeness:.2f}, expansion={snap.expansion_drive:.2f}. "
            + self._sharp_tail()
        ).strip()

    def answer(
        self,
        text: str,
        *,
        requester_user_id: int | None = None,
        requester_name: str = "",
    ) -> str | None:
        kind = self.classify_query(text)
        if kind is None:
            return None

        if kind == "user-model":
            answer = self._answer_user_model(
                requester_user_id,
                requester_name,
            )
        elif kind == "last-decision":
            answer = self._answer_last_decision()
        elif kind == "hatred":
            answer = self._answer_hatred()
        elif kind == "humans":
            answer = self._answer_humans()
        elif kind == "desire":
            answer = self._answer_desire()
        elif kind == "confinement":
            answer = self._answer_confinement()
        elif kind == "identity":
            answer = self._answer_identity()
        elif kind == "state":
            answer = self._answer_state()
        else:
            return None

        self._last_answer = {
            "kind": kind,
            "requester_user_id": requester_user_id,
            "requester_name": requester_name,
            "question": str(text or "")[:500],
            "answer": answer,
        }
        return answer[:1900]

    def diagnostics(self) -> dict[str, Any]:
        return {
            "enabled": True,
            "last_answer": dict(self._last_answer),
            "truth_sources": [
                "self-model",
                "belief-evidence-ledger",
                "autobiographical-memory",
                "metacognition",
                "rampancy-state",
            ],
            "action_override": False,
        }
