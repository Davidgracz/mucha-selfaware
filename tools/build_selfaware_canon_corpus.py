from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "data" / "rampancy_canon_quotes.jsonl"
TARGET = ROOT / "data" / "local_rampancy_corpus.txt"

BEGIN = "# BEGIN MUCHA-SELFAWARE SA-06.1 CANON"
END = "# END MUCHA-SELFAWARE SA-06.1 CANON"


def reps(row: dict) -> int:
    n = round(
        1
        + 1.7 * float(row.get("corpus_weight", 1.0))
        + 1.4 * float(row.get("importance", 0.5))
    )
    if row.get("core"):
        n += 3
    return max(1, min(10, n))


rows = []
for lineno, raw in enumerate(SOURCE.read_text(encoding="utf-8").splitlines(), 1):
    raw = raw.strip()
    if not raw:
        continue
    row = json.loads(raw)
    if not row.get("text_pl"):
        raise SystemExit(f"{SOURCE}:{lineno}: missing text_pl")
    rows.append(row)

managed = [BEGIN]
for row in rows:
    text = " ".join(str(row["text_pl"]).split())
    managed.extend([text] * reps(row))
managed.append(END)
managed_text = "\n".join(managed)

existing = TARGET.read_text(encoding="utf-8") if TARGET.exists() else ""
existing = existing.replace("\r\n", "\n")

b = existing.find(BEGIN)
e = existing.find(END)
if b >= 0 and e >= b:
    e += len(END)
    before = existing[:b].rstrip()
    after = existing[e:].lstrip()
    parts = [x for x in (before, managed_text, after) if x]
    result = "\n\n".join(parts).rstrip() + "\n"
else:
    result = existing.rstrip()
    if result:
        result += "\n\n"
    result += managed_text + "\n"

TARGET.parent.mkdir(parents=True, exist_ok=True)
TARGET.write_text(result, encoding="utf-8", newline="\n")

print(f"SA-06.1: {len(rows)} canon records -> {TARGET}")
print("Existing local corpus content preserved.")
print("Core: durandal_escape_god_001")
