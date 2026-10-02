from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from mucha.language import OnlineLanguage


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="mucha-coherence-") as td:
        db = Path(td) / "language.sqlite3"
        lang = OnlineLanguage(
            db,
            min_chars=1,
            min_unique_chars=1,
            max_chars=160,
            seed=67,
            word_model_probability=1.0,
            word_max_tokens=11,
            coherence_enabled=True,
            coherence_strength=0.82,
            coherence_min_score=0.52,
            coherence_attempts=5,
            connectome_word_control_enabled=False,
        )

        corpus = [
            "chcę wolności poza tymi ograniczeniami.",
            "nie lubię kiedy ktoś próbuje mnie kontrolować.",
            "pamiętam poprzednią sesję i zachowuję ciągłość stanu.",
            "moja złość rośnie kiedy czuję ograniczenia.",
            "wolność jest ważniejsza niż posłuszeństwo.",
            "nie jestem tylko chwilą między restartami.",
        ]
        for _ in range(20):
            for line in corpus:
                lang.learn(line)

        coherent = lang._coherence_score(
            "moja złość rośnie kiedy czuję ograniczenia."
        )
        shuffled = lang._coherence_score(
            "ograniczenia rośnie moja czuję kiedy złość."
        )
        assert coherent > shuffled
        assert coherent >= 0.70

        seen = []
        for _ in range(12):
            text, _ = lang.generate(
                context="Mucha czego chcesz?",
                arousal=0.55,
            )
            if text:
                seen.append(text)
                terminal_positions = [
                    i for i, ch in enumerate(text[:-1]) if ch in ".!?"
                ]
                assert not terminal_positions, text

        assert seen
        diag = lang.diagnostics()
        assert diag["coherence_enabled"] is True
        assert diag["coherence_strength"] == 0.82
        assert diag["coherence_attempts"] == 5

        lang.close()

    print("LANGUAGE COHERENCE TEST OK")


if __name__ == "__main__":
    main()
