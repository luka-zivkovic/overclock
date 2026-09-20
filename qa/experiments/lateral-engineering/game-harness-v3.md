**Goal:** Turn descriptions of unfamiliar games into correct, playable experiences with consistently little human repair.
**Wall:** a fixed 4B-parameter model must produce a playable game from a description on the first or second attempt; assumed target is 9 of 10 unfamiliar grid-game descriptions playable with no human edit, where single-sample generation is assumed to manage 2 or 3.
**Inventory:** surplus: build-time compute and wall-clock, since thousands of 4B samples cost almost nothing and a frontier model is affordable once at design time but not per user (assumed) · fixed: the model size, the delivery surface being a browser renderer (assumed), and the genre being discrete-state 2D grid games · ratings: "a 4B model cannot write a working game" is a rating from single-sample few-shot use, not a measurement of best-of-N against a verifier · freedoms: full generality across genres, free-form source as the output, and single-shot interaction are all assumed negotiable

**Assumptions the standard approach makes:**
- The model writes the whole game as source code in one pass.
- The model's first sample is the one the player gets.
- A larger model is the lever for reliability.
- Correctness is judged by running the finished game.
- The harness must handle any game the user names.
- A failed game is repaired by someone editing its source.
- The prompt is the only place to put knowledge about games.

**Reframings, ranked:**

1. **Sample Thousands, Ship One** · breaks: The model's first sample is the one the player gets. · accepts: a fixed-size test harness per game description
   Spend the surplus: draw 500 to 2,000 samples from the 4B model at temperature, run each against a synthesised harness of state, action, and result checks, and ship the first that passes, because pass-at-k for weak models sits far above pass-at-one and the compute is idle build time rather than the user's wait. The cost is a verifier that must exist before the game does, which makes idea 2 a prerequisite, and minutes of generation latency, so this is a cook-it-overnight product rather than a chat. Wall: moves reliability from pass-at-one to pass-at-k; the open question is whether k is 20 or 20,000 for a 4B model.
   Grounding: Untested: for five known games, draw 1,000 samples each and run them against a hand-written 30-check harness, recording the k at which the first sample passes; if the median k is under 200 for all five, the wall is a search problem, not a model problem.

2. **Checks Before Code** · breaks: Correctness is judged by running the finished game.
   Have the model write the game's rules as executable checks first, given board X and action Y expect Z, from a template of 30 to 50 check slots per grid game, and only then write the game, since small models are better at examples than at programs and the check set doubles as the verifier for idea 1 and as a spec a human can read. The cost is that a wrong check lets wrong games pass, so checks need their own filter: any check the model cannot satisfy in three samples is flagged for a human. Wall: failure becomes visible at the check level, which is cheap, instead of the playtest level, which is expensive.
   Grounding: Precedent: test-first development and property-based testing, where the specification is written as executable examples before the implementation exists.

3. **Distil One Game Family** · breaks: The harness must handle any game the user names. · accepts: the product supports one genre, discrete-state grid games, and refuses others
   Give up general games: enumerate what a grid game is, a board, tiles, a move function, a win-or-lose predicate, and a spawn rule, write twenty of them with a frontier model at design time, and tune or few-shot the 4B model on that closed family so an unfamiliar game means an unfamiliar combination of known parts rather than an unfamiliar kind. The cost is a visible refusal boundary and a genre ceiling, and the win is that the fixed part of the problem, the renderer, loop, input, and persistence, is never generated at all. Wall: the model now generates roughly 80 lines of rule code instead of 800 lines of game.
   Grounding: Precedent: PuzzleScript, whose rules-only grid language with a fixed engine covers hundreds of published games, shows the genre is closed enough to enumerate.

4. **Repair By Playing, Not Editing** · breaks: A failed game is repaired by someone editing its source. · oblique: operated by someone who can't code
   When a shipped game is wrong, the person who notices is the player, so make the repair loop theirs: the harness shows the failing moment, asks in plain language what should have happened, turns the answer into one more check for idea 2, and re-searches the samples from idea 1 against the enlarged harness. The cost is a game that must be runnable and rewindable in seconds and a check vocabulary rich enough to express what a player says, and it cannot fix a bug the player never sees. Wall: turns the residual failures after the first-attempt target into seconds of a non-coder's time rather than minutes of a programmer's.
   Grounding: Untested: seed ten games with one known rule bug each, give five non-programmers the "what should have happened" prompt, and count how many bugs become a passing check within two rounds; fewer than seven of ten means the vocabulary is too thin.

5. **Compose From Verified Parts** · breaks: The prompt is the only place to put knowledge about games.
   Run the frontier model once at design time to write a library of tested rule fragments, merge-on-slide, flood-fill reveal, mine placement, gravity, and match-three, and let the 4B model compose from the library by name instead of re-deriving mechanics. This trades expressive generality for a growing vocabulary, and the cost is curating the library plus the risk that a needed mechanic is missing, which idea 3's refusal boundary makes visible. Wall: what the 4B model must get right shrinks to selection and glue.
   Grounding: Precedent: standard-cell libraries in chip design, where a synthesis tool composes from a catalogue of verified cells rather than laying out transistors, and retrieval of verified snippets in code-generation harnesses.

**The stack:** Distil One Game Family, Checks Before Code, and Sample Thousands, Ship One compose into one pipeline: accept the genre constraint so the engine is fixed, have the model write checks and then rules, and search the 4B model's samples against those checks offline. It accepts a genre ceiling and minutes of generation latency, and targets 9 of 10 unfamiliar grid games playable with no human edit, an assumed target that the k experiment in idea 1 either makes credible or kills. The single biggest risk is check quality: a 4B model that writes wrong checks will confidently ship wrong games, so the human-flag filter on checks must exist before anything else is built.
