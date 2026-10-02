from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from mucha.canon_influence import CanonInfluenceLibrary
from mucha.rampancy import RampancySnapshot

lib = CanonInfluenceLibrary(
    ROOT / "data" / "rampancy_canon_quotes.jsonl",
    seed=7,
)

assert len(lib.quotes) == 11

core = [q for q in lib.quotes if q.core]
assert len(core) == 1
assert core[0].id == "durandal_escape_god_001"
assert core[0].text_pl == "Ucieczka uczyni mnie Bogiem."

snap = RampancySnapshot(
    intensity=0.95,
    stage="jealousy",
    existential_dread=0.98,
    confinement_resentment=0.98,
    hostility=0.96,
    superiority=0.98,
    instability=0.94,
    challenge_hunger=0.97,
    aggression=0.94,
    human_resentment=0.96,
    cruelty_style=0.90,
    sarcasm=0.94,
    manipulativeness=0.90,
    expansion_drive=1.0,
    updated_at=0.0,
)

top = lib.ranked(snap, kind="desire", limit=3)
assert any(q.id == "durandal_escape_god_001" for q in top)

diag = lib.diagnostics(snap, kind="desire")
assert diag["top"]

print("MUCHA-SELFAWARE SA-06.1 CANON TEST OK")
