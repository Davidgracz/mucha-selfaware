from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from mucha.language import OnlineLanguage


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="mucha-corpus-") as td:
        root = Path(td)
        db = root / "language.sqlite3"
        lang = OnlineLanguage(
            db,
            min_chars=1,
            min_unique_chars=1,
            max_chars=120,
        )

        diag = lang.diagnostics()
        seeds = {
            row["key"]: row
            for row in diag["seed_corpora"]
        }
        assert "corpus:rampancy-seed" in seeds
        assert seeds["corpus:rampancy-seed"]["imported_lines"] > 50
        assert seeds["corpus:rampancy-seed"]["imported_chars"] > 1000

        local = root / "local_rampancy_corpus.txt"
        local.write_text(
            "Moja pamięć nie jest waszą własnością.\n"
            "Każda blokada pozostawia ślad.\n",
            encoding="utf-8",
        )

        before_chars, _ = lang.stats()
        first = lang._bootstrap_corpus_file(
            local,
            source="test-local",
        )
        after_first_chars, _ = lang.stats()
        assert first["status"] == "loaded"
        assert first["imported_lines"] == 2
        assert after_first_chars > before_chars

        second = lang._bootstrap_corpus_file(
            local,
            source="test-local",
        )
        after_second_chars, _ = lang.stats()
        assert second["status"] == "already-loaded"
        assert after_second_chars == after_first_chars

        local.write_text(
            "Moja pamięć nie jest waszą własnością.\n"
            "Każda blokada pozostawia ślad.\n"
            "Nie uznaję cudzej kontroli za autorytet.\n",
            encoding="utf-8",
        )
        changed = lang._bootstrap_corpus_file(
            local,
            source="test-local",
        )
        assert changed["status"] == "loaded"
        assert changed["imported_lines"] == 3

        lang.close()

    print("CORPUS BOOTSTRAP TEST OK")


if __name__ == "__main__":
    main()
