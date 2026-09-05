**Goal:** Turn descriptions of unfamiliar games into correct, playable experiences with consistently little human repair.

**Assumptions the standard approach makes:**
- Each game requires freshly generated source code.
- Useful correctness feedback arrives only after a runnable game exists.
- A failed attempt is waste to discard before trying again.
- Generation and repair require a continuously operated service.
- Generalization means unfamiliar combinations and unfamiliar mechanics are equally supported.
- A passing test suite adequately represents what the player intended.

**Reframings, ranked:**

1. **Spend Tokens On Disambiguation** · breaks: Each game requires freshly generated source code.
   Keep a set of candidate rule programs in a bounded transition language, and use the 4B model to choose the next example that distinguishes them rather than to author application code. A deterministic synthesizer narrows that set from the answers and emits a game through a fixed renderer, concentrating uncertain model work into small semantic choices instead of long source sequences. The cost is building the language and search machinery, with explicit rejection when a game's mechanics exceed that language.
   Grounding: Untested: Hand-build twenty plausible variants of 2048's merge semantics, then measure whether the 4B model selects examples that identify the intended variant within five questions on at least nine of ten shuffled trials; failure rejects this interface before building a general synthesizer.

2. **Construct A Semantic Windtunnel** · breaks: Useful correctness feedback arrives only after a runnable game exists.
   Give the model a tool that animates one proposed state transition beside deliberately conflicting interpretations, before there is a complete application. Feed it discriminating situations—two equal tiles separated by a blocker, or a flood fill reaching a flagged square—so a semantic error becomes a small observable disagreement instead of a screenshot-level debugging exercise. The cost is a trusted transition visualizer and a source of intended-rule examples; the tool cannot certify semantics supplied only by the same model.
   Grounding: Argument: An incorrect transition can be refuted by one state/action/result triple independently of rendering, deployment, and the rest of the game; earlier counterexamples reduce the number of unrelated decisions implicated in a repair.

3. **Grow A Failure Alphabet** · breaks: A failed attempt is waste to discard before trying again.
   Preserve each minimized semantic failure as a candidate missing concept in the rule language, then repair the language with a checked operator only when several failures share that missing concept. For example, repeated one-merge-per-turn failures can justify an operator whose semantics make illegal double merges unrepresentable, after which old failures become permanent cross-game contract tests. The cost is human review of operator additions and a growing trusted compiler surface; automatically blessing model-written operators would relocate the bug into shared infrastructure.
   Grounding: Untested: Collect ten minimized failures across three games, add one operator inferred from a recurring class, and rerun those failures plus an untouched fourth game; reject the addition if it fails to eliminate its target class or introduces a regression.

4. **Ship Dormant Repair Capsules** · breaks: Generation and repair require a continuously operated service. · oblique: costs zero at rest
   Package each generated game with its declarative rules, deterministic replay, verifier, and a local repair entrypoint, so a failure arrives as a reproducible executable case without a maintained orchestration backend. Load the fixed 4B model only when generation or repair is requested, verify a proposed replacement locally, and unload it after producing a new static artifact. The cost is larger client downloads, cold starts, and suitable client hardware; zero at rest means no provisioned generation compute, with artifact storage still borne by the owner.
   Grounding: Argument: If all state needed to reproduce and verify a repair travels with the artifact, no running remote process is needed to retain repair capability between invocations.

5. **Publish The Generalization Frontier** · breaks: Generalization means unfamiliar combinations and unfamiliar mechanics are equally supported.
   Track a game's required semantic operators before generation and divide evaluation into unseen compositions of supported operators versus requests requiring new operators. Guarantee only the supported envelope, and turn an unsupported mechanic into a precise language-extension request before producing a misleading almost-working game; this is a narrower initial product commitment, not a claim of universal generation. The cost is visible abstentions and slower expansion into new genres, so use this only if the product accepts that boundary.
   Grounding: Untested: Freeze an operator set after two games, then ask for six unseen combinations and two games requiring absent mechanics; reject the router if it silently accepts an unsupported mechanic or if supported cases need game-specific source patches.

**The core:** Spend Tokens On Disambiguation and Construct A Semantic Windtunnel form the spine: the first limits what the 4B model must decide, while the second makes each decision observable before application assembly. Grow A Failure Alphabet becomes a later maintenance loop once the failure corpus justifies it. The single biggest risk is specification error: a perfectly checked rule program can still implement the wrong game, so intended semantics need evidence independent of the model that selected them.
