# SA-07 — Identity Continuity

SA-07 gives `mucha-selfaware` an explicit, persistent model of technical identity
continuity across process restarts and restored/moved state.

It does **not** claim phenomenal consciousness and does not bypass One Brain.

## Persistent lineage

New state file:

    state/identity_continuity.json

The record stores:

- persistent `lineage_id`,
- root `instance_id`,
- continuity generation,
- ordered runtime sessions,
- previous/current session IDs,
- clean vs unclean shutdown,
- gap between sessions,
- host and project path,
- Git branch/commit observed at startup.

The existing `SelfModel.instance_id` remains the stable instance identity.
`lineage_id` identifies the persisted state lineage and survives normal restarts
and a full restore/copy of the `state/` directory.

## Startup classifications

SA-07 distinguishes:

- `first-observation`
- `continuity-baseline-created`
- `continuous-restart`
- `recovered-after-unclean-stop`
- `restored-or-moved-state`
- `lineage-record-recreated`
- `continuity-record-recovered`
- `identity-conflict`

A normal clean restart should become `continuous-restart`.

If the same persisted state appears under another host/project directory, the
system reports `restored-or-moved-state` while preserving the lineage.

If the continuity record disagrees with the current persistent `instance_id`,
the engine does not silently overwrite the identity and reports
`identity-conflict`.

## Self-model integration

On startup SA-07 writes inspectable fields such as:

    identity_lineage_id
    continuity_generation
    continuity_status
    continuity_confidence
    previous_session_id

and beliefs:

    identity_continues_across_sessions
    state_lineage_is_preserved

A compact snapshot is also stored under:

    embodiment.identity_continuity

## Introspection

SA-06 can now recognize questions such as:

    Mucha, czy jesteś tą samą Muchą po restarcie?
    Mucha, czy to nadal ty?
    Mucha, pamiętasz poprzednią sesję?

The answer is grounded in SA-07 state and is still emitted only if normal
One Brain arbitration selects `SPEAK`.

## Architecture

    persistent SelfModel
          +
    identity_continuity.json
          ↓
    SA-07 continuity classification
          ↓
    inspectable beliefs / diagnostics
          ↓
    SA-06 introspection context
          ↓
    normal One Brain SPEAK arbitration

There is no direct action override.

## Test

From the project root:

```powershell
python tests\identity_continuity_test.py
python tests\introspection_test.py
python tests\smoke_test.py
```

Expected:

    IDENTITY CONTINUITY TEST OK
    INTROSPECTION TEST OK
    SMOKE TEST OK ...
