# Moves for lateral engineering

Use precedents to make each move concrete, not to require that the proposed idea already
exists. The best output may apply a move somewhere it has not been applied before.
These are analogies for transformations, not claims that the systems are interchangeable
or that every idea descended historically from its neighbor. Transfer the mechanism,
name the assumption it breaks, and account for the new cost. Precedents here are not a source
list: an idea's grounding must come from the user's problem, a field that genuinely shares the
mechanism, or a cheap experiment. Citing a catalog example because it is in the catalog is not
grounding.

## Remove

### Delete the mandatory middle
Remove a coordinator, intermediary, or representation whose obligation can disappear or live elsewhere.
- **Precedents:** SQLite embeds the database instead of requiring a server; Git permits local commits without a central coordinator; transformers remove recurrence from sequence modeling; Netflix's subscription rental model [removed due dates and late fees](https://about.netflix.com/en/news/netflix-com-transforms-dvd-business-eliminating-late-fees-and-due-dates-from).
- **Ask:** If this layer were forbidden, which part of its job would still need doing, and which part only exists because we introduced it?

### Delete expressive power
Remove capabilities that create more implementation burden than user value.
- **Precedents:** JSON offers a smaller data interchange surface than XML; [PuzzleScript](https://www.puzzlescript.net/Documentation/rules.html) expresses puzzle behavior with pattern-replacement rules; SQLite avoids a separate server administration surface; flat-pack furniture reduces the volume shipped by deferring assembly.
- **Ask:** What generality are we paying for that the actual outcome never uses?

## Relocate

### Move the actor
Give work to the actor with the information, incentive, or capability to do it cheaply.
- **Precedents:** flat-pack moves assembly to the customer; local-first software keeps useful work on the user's device; Stripe moves payment infrastructure work behind a service interface; eBPF places constrained programs at kernel observation and execution points.
- **Ask:** Who already knows the answer, owns the relevant state, or benefits enough to do this work?

### Move the time
Do expensive work before demand, after demand, or only once demand becomes real.
- **Precedents:** materialized views precompute reads; speculative decoding drafts before verification; Toyota pull/kanban schedules replenishment from downstream demand; Git performs work locally before synchronization.
- **Ask:** Which deadline is real, and which work could happen before or after it without changing the outcome?

### Move the layer
Solve the bottleneck in the layer controlling its actual resource cost.
- **Precedents:** [FlashAttention](https://arxiv.org/abs/2205.14135) treats exact attention as an IO problem; eBPF observes behavior in the kernel; llama.cpp and GGUF put inference and model packaging within local hardware constraints; Borg and Kubernetes place resource scheduling above individual processes.
- **Ask:** Which layer controls the scarce resource, and why are we fixing symptoms two layers away?

## Invert

### Pull instead of push
Let demand acquire work or state rather than having producers force it downstream.
- **Precedents:** [Toyota's pull and replenishment systems](https://www.toyota-global.com/company/history_of_toyota/75years/common/pdf/production_system.pdf); consumers pulling messages; demand-driven lazy evaluation; Kubernetes controllers repeatedly reconciling observed and desired state.
- **Ask:** What disappears if the consumer decides when and how much work exists?

### Reverse truth ownership
Change what is authoritative: operations rather than snapshots, content rather than location, or local intent rather than central approval.
- **Precedents:** event sourcing derives current views from events; Git identifies objects by content; content-addressed storage derives identity from bytes; local-first systems retain local writes; CRDTs define mergeable state instead of serializing every update through one writer.
- **Ask:** What are we synchronizing only because we picked the wrong source of truth?

### Trade exactness and work
Invert compute/store or exact/approximate so precision and computation occur only where they change the outcome.
- **Precedents:** Bloom filters reject definite misses cheaply; sketches estimate aggregates; materialized views exchange storage for computation; React's virtual DOM uses an intermediate representation to reconcile UI changes; [speculative decoding](https://proceedings.mlr.press/v202/leviathan23a.html) verifies cheaper drafts while preserving the target sampling distribution.
- **Ask:** Where can we accept approximation, and what small exact check keeps the externally required guarantee intact?

## Import

### Borrow a foreign mechanism
Map the problem to a field that already handles the same structure under different names.
- **Precedents:** PageRank brings citation-like importance propagation to web links; Dyson [adapted industrial cyclone separation](https://www.dyson.com/james-dyson) to vacuum cleaning; software circuit breakers borrow electrical fault isolation; kanban uses replenishment signals associated with supermarket-style stocking.
- **Ask:** Which other field handles this shape of scarcity, congestion, trust, uncertainty, or failure—and what maps to what?

### Build the measuring instrument
Replace repeated speculation with a cheap apparatus that makes the disputed behavior observable.
- **Precedents:** the Wright brothers tested airfoils in a wind tunnel; property-based testing searches generated cases; fault injection makes recovery behavior observable; differential testing compares implementations on identical inputs.
- **Ask:** What small instrument could turn our hardest design argument into an afternoon of evidence?

## Embrace the constraint

### Make failure ordinary
Assume the bad event happens frequently and design useful progress around it.
- **Precedents:** MapReduce retries work after worker failure; Bitcoin reaches agreement despite competing participants through costly proof of work; CRDTs tolerate concurrent updates under their merge rules; circuit breakers contain repeated dependency failure.
- **Ask:** If this failed ten times more often, what architecture would become simpler than prevention?

### Exceed the rated limit, then measure
Treat a vendor rating, quota, or house rule as a claim about the limit, not the limit.
- **Precedents:** overclocking runs silicon past the vendor's rating and keeps the setting that survives a stability test; rate limits that are policy rather than capacity; timeouts and pool sizes set by habit and never remeasured; Sony rated the PlayStation CD drive for 70,000 reads and Crash Bandicoot shipped at an estimated 120,000 per playthrough ([Gavin](https://all-things-andy-gavin.com/2011/02/06/making-crash-bandicoot-part-5/)). This is a risk the user decides, never a recommendation to hide.
- **Ask:** Which limit here is a rating, what cheap test would reveal the real one, and who bears the cost if the rating was right?

### Make the expense the architecture
Make an apparent inefficiency the isolation boundary, product feature, or operating model.
- **Precedents:** per-tenant databases spend database count on isolation; Bitcoin spends computation on consensus participation; AWS exposes infrastructure capacity as rentable services; llama.cpp makes commodity/local execution a design center.
- **Ask:** What does this expensive thing buy us if we stop treating it as an overhead to eliminate?

## Change the unit

### Standardize the boundary
Keep internals varied but change the exchange unit so coordination becomes mechanical.
- **Precedents:** the shipping container standardizes intermodal handling; GGUF packages models in a common format; Stripe exposes payment operations through APIs; OCI container images standardize packaged application artifacts.
- **Ask:** Which interface could become boring enough that everything behind it can vary freely?

### Resize the work
Batch, split, merge, or quantize the unit until it fits the real bottleneck.
- **Precedents:** MapReduce partitions work into tasks; Bloom filters and sketches compress membership or aggregate questions; FlashAttention tiles computation around fast memory; PuzzleScript changes game authorship into rules over a grid; GGUF supports quantized model representations.
- **Ask:** Are we paying per token, trace, request, tenant, deployment, or decision—and what happens if that is no longer the unit?

### Resize the deployment
Change what can be deployed, moved, owned, or discarded independently.
- **Precedents:** SQLite deploys with the application; per-tenant databases give tenants distinct operational boundaries; Borg/Kubernetes schedule groups of processes; local-first applications put useful state on each device.
- **Ask:** What would become replaceable if the deployment boundary followed failure, ownership, or the customer instead of the codebase?

## Arbitrage

Every move above changes the shape of a design. Arbitrage changes what pays for it: a surplus
the conventional design never uses buys relief on the wall it cannot pass. The four moves below
are where the inventory's surplus, fixed facts, and negotiable freedoms turn into ideas.

### Spend the surplus axis
Convert something abundant on one axis into relief on the scarce one, at a degree nobody does.
- **Precedents:** speculative decoding spends cheap draft compute to buy latency; best-of-N sampling with a verifier spends inference to buy accuracy; CDN edge caches spend storage near users to buy backbone bandwidth; Crash Bandicoot streamed 64 KB pages off the CD so the disc acted as RAM and precomputed visibility offline so at most 800 polygons were ever sorted at runtime ([Gavin](https://all-things-andy-gavin.com/2011/02/04/making-crash-bandicoot-part-3/)).
- **Ask:** What do we have far too much of, and what would spending all of it buy on the wall?

### Newly free
Find a step still priced as expensive because the design was set before it became cheap.
- **Precedents:** coverage-guided fuzzing moved from research clusters to every CI run; a full rebuild or full test suite per commit became normal once remote caches made it cheap; one model call per record, per test, or per build step used to be a budget line and is now noise; a per-problem language was once a heroic effort and is now a generated artifact.
- **Ask:** Which step in the conventional design assumes a cost that no longer exists?

### Specialise the instance
Reject the general solution's cost when the specific case does not carry it.
- **Precedents:** a perfect hash beats a hash table when the key set is closed; a compiled decision tree beats a rules engine when the rules are known at build time; a single-writer design skips the locking a general database needs; Naughty Dog were told real-time collision needed a Cray, which was true of the general problem and false of their instance with a fixed camera path ([Gavin](https://all-things-andy-gavin.com/2011/02/07/making-crash-bandicoot-part-6/)).
- **Ask:** What does the general solution assume that is false here, and what becomes trivial once we admit it?

### Trade a freedom for a guarantee
Accept a product constraint the user did not ask for when it turns a runtime problem into an offline one.
- **Precedents:** fixed-size records make random access free; a closed vocabulary makes exact search possible; an append-only log makes replay trivial; Rust gives up unrestricted aliasing to get memory safety without a collector; a camera on rails let Crash Bandicoot precompute visibility per position, the constraint being the enabler rather than a compromise.
- **Ask:** Which freedom, if given up, makes the wall disappear, and would the user take that trade if it were offered plainly? Tag the offer `· accepts:`.

## Deliberately worse

### Worsen the proxy
Deliberately degrade a local measure when doing so improves the outcome that matters.
- **Precedents:** speculative decoding uses weaker drafts plus exact verification; lossy compression sacrifices reconstruction fidelity for size; Bloom filters permit false positives for compact membership checks; JSON gives up XML features for simpler interchange; [TurboQuant/QJL](https://arxiv.org/abs/2504.19874) corrects inner-product bias, rather than optimizing reconstruction error alone.
- **Ask:** Which quality could become worse without hurting the user—and which bottleneck would that release?

## Productize the internal

### Expose the enabling capability
Turn infrastructure, operational knowledge, or a supporting artifact into something others can consume.
- **Precedents:** AWS sells infrastructure primitives as services; Kubernetes exposes ideas informed by Google's Borg experience; SQLite makes an embedded database broadly reusable; the [Michelin Guide](https://www.michelin.com/en/media/magazine/explore-guide-michelin) makes motoring information a useful product alongside tires.
- **Ask:** Which internal capability is more valuable than the workflow it currently serves, and who else could use it directly?

## Oblique constraints

Draw one of these blindly before generating, as a creative lens rather than a requirement:

must work offline · buildable with 1995 technology · operated by someone who can't code ·
must get better as it fails more · runs on the smallest machine in the building ·
survives the team being fired · explainable in one sentence to a child · costs zero at rest ·
reversible at any point · what you'd build if you had to demo tomorrow

## Change the success metric

### Optimize the actual consequence
Replace a convenient proxy with the property whose improvement changes the decision or user experience.
- **Precedents:** FlashAttention optimizes memory traffic, not just arithmetic counts; TurboQuant's inner-product variant uses a QJL residual correction for unbiased estimates, not merely lower reconstruction MSE; Netflix subscriptions remove lateness as a per-rental revenue mechanism; PageRank models link-derived importance instead of counting keyword matches alone.
- **Ask:** If this metric improved tenfold and the user still suffered, what should we have measured instead?
