**Goal:** Reach trustworthy judgments about quality quickly without making human effort grow with every new example.

**Assumptions the standard approach makes:**
- Every trace needs an individual label before an evaluation decision is possible.
- Human judgment must happen after the behavior has already occurred.
- A whole trace is the smallest useful unit of annotation.
- Reviewers can only label behavior, not change how it is evaluated.
- Reviewer disagreement is noise that must collapse into one correct label.
- Queue throughput is the measure of evaluation progress.

**Reframings, ranked:**

1. **Retire Questions Before Traces** · breaks: Every trace needs an individual label before an evaluation decision is possible.
   Define the decision first—such as whether a candidate regresses a particular failure rate—and let annotation stop once a predeclared sequential bound settles that decision. Keep a probability sample and its inclusion probabilities so stopping and allocation do not quietly bias the estimate; a trace with no remaining decision value need not acquire a label at all. The cost is explicit uncertainty and unresolved narrow subgroups, and this route is unavailable wherever complete review is a contractual requirement.
   Grounding: Argument: A bounded estimate of a population property can support a decision without observing every member; the obligation is coverage and a valid stopping rule, not a complete annotation table.

2. **Spend Judgment At Authoring** · breaks: Human judgment must happen after the behavior has already occurred.
   Ask task authors to supply a small executable evidence contract when they create an evaluation task, including the artifact or state change that would demonstrate success. Capture that evidence during execution so many later traces become explanations of a checked outcome, while humans review exceptions and an independent sample for contract blind spots. The cost is up-front authoring work and a shift in coverage: behaviors omitted from the contract remain unmeasured rather than becoming implicitly correct.
   Grounding: Argument: When success entails an observable state predicate, checking that predicate directly removes the need to reconstruct it from the entire narrative; this does not establish qualities absent from the predicate.

3. **Annotate Causal Forks Once** · breaks: A whole trace is the smallest useful unit of annotation.
   Extract the smallest decision fork at which two otherwise matched executions diverge, and ask the reviewer which branch satisfies the task and under what conditions. Reuse that judgment as a conditional assertion over a validated context signature, with random full-trace audits checking that discarded context did not change its meaning. The cost is building reliable alignment and invalidation; superficially similar tool calls cannot inherit a judgment merely because their text matches.
   Grounding: Untested: Take thirty trace pairs, have one reviewer judge extracted forks and another judge complete traces, and reject the compression if any material reversal is caused by omitted context; record minutes per agreement as the potential gain.

4. **Let Reviewers Rewrite Outcomes** · breaks: Reviewers can only label behavior, not change how it is evaluated. · oblique: operated by someone who can't code
   Let a reviewer correct a visible before/after artifact—remove an unauthorized recipient, restore a deleted field, or mark an expected file—as the annotation action, and compile that edit into a replayable assertion over the recorded inputs. A review then produces a reusable executable check that a person can inspect through the same visual interface, rather than a label that merely ends the current queue item. The cost is a deliberately limited assertion vocabulary, versioned fixtures, and occasional expert intervention; intent such as politeness will not compile into these checks.
   Grounding: Untested: Prototype three artifact-edit operations on twenty recorded tasks; accept the interface only if reviewers can inspect the resulting assertions and those assertions reject seeded violations while accepting the original valid controls without code editing.

5. **Keep Disagreement As Structure** · breaks: Reviewer disagreement is noise that must collapse into one correct label.
   Preserve the incompatible rubric interpretations and evaluate the candidate under each instead of adjudicating every disputed trace into a majority label. Ship a decision only when it remains the same under all retained interpretations, and spend adjudication effort only on disagreements that can reverse it. The cost is conservative or delayed decisions and a need to distinguish legitimate interpretations from annotation mistakes; universal agreement across a badly chosen interpretation set proves little.
   Grounding: Argument: If a decision is invariant over every admissible interpretation of the disputed evidence, resolving that dispute cannot change the decision; disagreement matters only where it crosses the decision boundary.

**The core:** Retire Questions Before Traces and Annotate Causal Forks Once form the spine: the first decides whether another judgment is needed, and the second reduces what a reviewer must inspect when one is needed. Keep their roles distinct: probability sampling supplies population evidence, while reusable fork judgments require their own context-validation evidence. The single biggest risk is biased exclusion—apparently settled decisions can hide rare failures if sampling, discarded context, or contract coverage systematically omits them.
