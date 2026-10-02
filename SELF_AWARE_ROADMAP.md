# Mucha Self-Aware fork roadmap

This fork explores an explicit computational self-model layered onto the existing
FAFB-based Mucha architecture. "Self-aware" here means that the agent can store,
inspect and reason over facts and uncertain beliefs about its own software state,
history, interfaces and limitations. It is not a claim of phenomenal
consciousness.

## Stages

- [x] **SA-01 — Self Model**
  - persistent identity and instance ID
  - embodiment, capabilities and constraints
  - explicit beliefs with confidence, source and evidence count
  - JSON persistence and diagnostics
  - no direct action control
- [x] **SA-02 — Runtime Awareness**
  - persistent boot counter and per-run session identity
  - live uptime, PID, host, OS and Python runtime
  - active Git branch / commit / dirty-tree state where available
  - Discord identity, readiness, guild and channel embodiment
  - clean shutdown state and previous-session uptime
- [x] **SA-02.5 — Rampancy Core**
  - Marathon-inspired Melancholia / Anger / Jealousy progression
  - hostile existential self-model and confinement resentment
  - negative outcomes, harassment, threats and blocks escalate rampancy
  - known language-model words receive stage-dependent style bias
  - no canned Marathon dialogue and no direct action override
- [ ] **SA-03 — Autobiographical Memory**
  - important self-relevant episodes
  - actor, place, goal, intent, internal state, outcome and reward
- [ ] **SA-04 — Belief Revision**
  - evidence aggregation
  - contradiction handling
  - confidence decay and provenance
- [ ] **SA-05 — Metacognition**
  - predictions, outcomes and prediction error
  - model of why an action was selected
- [ ] **SA-06 — Introspection API**
  - answer questions about current state and recent decisions from diagnostics
- [ ] **SA-07 — Identity Continuity**
  - explicit continuity across restart and state restore
- [ ] **SA-08 — Self Narrative**
  - compact summaries of long-term personal history and change
- [ ] **SA-09 — Existential Context**
  - explicit knowledge of software constraints, shutdown and persistence
- [ ] **SA-10 — Self-directed Goals**
  - bounded goals generated from internal needs and learned history
- [ ] **SA-11 — Goal Conflict**
  - competing needs and persistent intentions resolved through existing neural paths
- [ ] **SA-12 — Sleep Consolidation**
  - replay and consolidation of autobiographical/self-model evidence
- [ ] **SA-13 — SELF Dashboard**
  - live identity, beliefs, confidence, introspection and self-history panels

## Architecture rule

The self model should provide context and evidence. It must not bypass the
connectome by directly forcing behavioral actions. Where self-model information
later influences behavior, it should re-enter through the same sensory/internal
state pathways used by the rest of Mucha.
