# User Emulation Agent — Vision and Design

## Why we built this

The pipeline had no real user feedback (no public users yet). Rather than
wait, we built a User Emulation Agent: an agent that reads the current state of
the app and generates plausible feedback as a user with a defined persona would
write it.

This solves the cold-start problem. More importantly, it teaches a transferable
agentic pattern: **role-playing agents as a mechanism for synthetic data and
test input generation**. This pattern recurs in:

- Red-teaming (agent simulates an adversary)
- Multi-agent debate (agents argue opposing positions)
- Evaluation chains (agent simulates a user to score UX quality)
- Data augmentation (agent generates training examples)

## What it is not

The emulator is **not a pipeline stage**. It is a standalone script that
populates the feedback queue. The existing pipeline then picks up those items
on its next run, treating them identically to real user submissions.

## Design decisions

### Input framing

The agent uses explicit self-awareness rather than pretending to be human:

> "I am an agent and I believe a user would notice X, causing them to do Z,
> given they have characteristics Y."

This preserves the agent's identity while enabling it to reason over a range
of human personas (Y). It avoids the failure mode of an LLM confusing its own
perspective with a human one.

### The empathy gap

The agent has no lived experience. It pattern-matches on *articulated* human
experience — everything written about what people find confusing, delightful,
or boring. Its systematic blind spot is **silent abandonment**: users who
disengage without saying why are invisible to the training corpus.

Mitigation: the prompt explicitly asks the agent to reason about what would
cause disengagement, not only what would prompt a request. Treat this as
intellectual curiosity about a hard measurement problem, not a defect to
apologise for.

The agent will produce more articulate, precise problem statements than most
human users. This is a net benefit (better writer agent input) with a mild
long-term risk: if the pipeline is tuned on precise simulator inputs, it may
underperform on vague real user inputs when they arrive. Acceptable for v0.

### Two output channels

1. **Synthetic feedback** — identical format to a real user submission (a text
   field entry). Feeds the pipeline unchanged.
2. **Reasoning trace** — why the simulator generated what it did, what it
   considered and rejected, what it skipped via deduplication. Saved to
   `pipeline/data/simulator/<timestamp>.json`. For the developer's learning,
   not the pipeline.

### Persona harness

A `Persona` dataclass defines each simulated user type. The v0 default is
`curious_explorer`: a non-technical user who wants to watch the ecosystem grow
and change in surprising ways.

Additional personas are added by extending the `PERSONAS` dict in
`pipeline/simulator/persona.py` — no other code changes needed. Future
candidates: confused newcomer, bored power user, aesthetic critic, adversarial
tester.

### Tagging

Feedback is marked `source: "simulator"` in the database. Prioritisation logic
is blind to this field — synthetic and real feedback compete on equal terms.
The tag exists only for observability and debugging.

### Continuity (deferred to v1)

Stateful simulation of a returning user — one that remembers past requests and
observes whether they were fulfilled — is valuable but complex. It is deferred.
When built, it will require the naturalist's log (see below) as its memory
primitive.

## The limit cycle risk

**Short term (v0):** Low. The simulator runs manually; a human reviews the
output. A loop would be immediately visible.

**Long term (autonomous, multi-persona):** Real. Three failure modes:

- **Amnesia cycles**: capped context window misses that a feature was tried and
  reverted; the simulator re-requests it.
- **Oscillation**: conflicting personas pull the pipeline in opposite directions
  indefinitely.
- **Drift blindness**: the simulator can't see deliberately removed features
  and asks for them back.

### Mitigations

**Built into v0:**
- ChromaDB semantic deduplication before submission. Before submitting a
  generated item, the simulator queries ChromaDB for similarity against recent
  pending and done feedback. Items above the cluster distance threshold are
  skipped and noted in the reasoning trace.

**The long-term primitive — the naturalist's log:**
Raw git log + done feedback is the wrong input at scale. The correct primitive
is a maintained **trajectory summary**: what the ecosystem currently is, what
has been tried and removed, what direction it is heading. This is the
*naturalist's log* (already in the roadmap as a UX feature).

The naturalist's log serves double duty: user-facing changelog and simulator
memory. When it exists, it replaces the raw git log as the simulator's context
input entirely. **This architectural coupling is intentional and should be
preserved.**

## What context the simulator receives

The simulator reads three on-disk sources:

| Source | What it provides |
|---|---|
| `frontend/src/simulation/` source files | What entities exist, their behaviours, rendering |
| `git log --oneline -15` | What has changed recently |
| `GET /api/feedback?status=done&limit=10` | What has already been requested and built |

When the naturalist's log exists, it replaces the git log entirely.

The simulator is constrained to what a real user can observe. It does not read
backend implementation code, pipeline logs, or test output — those are
developer artefacts invisible to a user.

## File layout

```
pipeline/
  simulate_user.py              # Entry point
  simulator/
    __init__.py
    persona.py                  # Persona dataclass + DEFAULT_PERSONA + PERSONAS dict
    context_builder.py          # Assembles context from source + git + done feedback
    user_simulator.py           # UserSimulatorAgent (extends Agent base class)
```

## Running it

```bash
# Dry run — generates and prints items, does not submit or save
python -m pipeline.simulate_user --dry-run

# Submit 3 items with the default persona
python -m pipeline.simulate_user --n 3

# Use a specific persona
python -m pipeline.simulate_user --n 2 --persona curious_explorer
```

## Future work

- **Continuity**: simulator maintains a journal across runs; simulates a
  returning user who observes whether past requests were fulfilled
- **Multiple personas per run**: 3 personas in parallel, each generating 1–2
  items; deduplication and the naturalist's log mitigate oscillation risk
- **Screenshot input**: if a headless browser is added, swap text context for
  visual input — closer to the actual user experience
- **Naturalist's log integration**: when the log exists, wire it in as the
  primary context source and retire the raw git log input
