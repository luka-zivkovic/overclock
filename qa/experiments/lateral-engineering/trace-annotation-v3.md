**Goal:** Reach trustworthy judgments about quality quickly without making human effort grow with every new example.
**Wall:** human review throughput; assumed 200 traces per reviewer-day against roughly 5,000 new traces per day, so the queue grows by an order of magnitude more than it drains.
**Inventory:** surplus: model judgment tokens, since thousands of judged traces per hour cost less than one reviewer-hour, the backlog itself as unlabeled data, and every past human label · fixed: the rubric, the trace format, the set of task types, and the reviewers themselves (assumed stable) · ratings: "every trace must be human-reviewed" is assumed to be a policy adopted when model judges were unreliable rather than a contractual rule; if it is contractual, ideas 1, 2, and 5 are off the table · freedoms: per-trace labels as the output, synchronous review before release, and one reviewer per trace are assumed negotiable

**Assumptions the standard approach makes:**
- Every trace needs an individual human label before a decision is possible.
- The queue is ordered by arrival.
- Reviewers label; they do not teach.
- A human label is produced by reading the trace.
- The queue must drain before a release decision can be made.
- Labels are consumed once, for the release they gate.
- Review happens after the trace exists.

**Reframings, ranked:**

1. **Humans Grade The Judge** · breaks: Every trace needs an individual human label before a decision is possible.
   Route every trace through a model judge that applies the fixed rubric, and point the human queue at the judge rather than the traces: reviewers audit a stratified sample of judge verdicts, and the judge's measured agreement per task type becomes the release gate's error bar. Human throughput is spent where it compounds, on calibrating a judge that then labels 5,000 traces an hour, and the cost is that every release decision now carries a stated uncertainty and needs a per-task-type minimum audit before the judge is trusted. Wall: human work becomes proportional to the number of task types, not to trace volume.
   Grounding: Precedent: acceptance sampling in manufacturing, where inspectors audit the process that grades parts instead of grading every part, once process capability is measured.

2. **Disagreement Is The Queue** · breaks: The queue is ordered by arrival.
   Run two cheap judges with different prompts or models over everything, and put only the traces where they disagree, or where either is low-confidence, in front of a human, while agreeing verdicts ship with the audited error rate from idea 1. The cost is two judge passes per trace and a blind spot for correlated judge errors, which the stratified audit must deliberately include. Wall: if the judges agree on an assumed 85 percent of traces, the human queue shrinks by that much before any single review gets faster.
   Grounding: Precedent: query-by-committee active learning, which selects the examples a committee of models disagrees on for human labeling; the same mechanism applied to evaluation rather than training.

3. **Reviewers Write Checks** · breaks: Reviewers label; they do not teach. · accepts: a fixed, small assertion vocabulary that reviewers pick from
   When a reviewer rejects a trace, the required output is not a label but an executable check chosen from a short menu, such as the answer must cite the tool result, no write before confirmation, or the final message is under N lines. Each check then runs over the backlog and every future trace at zero human cost, so one review-minute removes a whole failure class from the queue. The cost is a vocabulary that cannot express taste and a check suite that grows and needs pruning. Wall: converts human time from linear in traces to linear in failure classes.
   Grounding: Precedent: a regression test written once for a reported bug guards every later commit, so the reviewer's minute is amortised over all future traces.

4. **Judge State, Not Narrative** · breaks: A human label is produced by reading the trace.
   For task types with an observable end state, a file diff, a returned value, or a tool-call log, evaluate the state predicate directly and show the human a one-line summary plus the predicate result, reserving full trace reading for the cases the predicate leaves inconclusive. The cost is authoring a predicate per task type up front and losing coverage of behaviours the predicate does not encode, which idea 1's audit sample must keep catching. Wall: a trace that takes five minutes to read takes five seconds to check.
   Grounding: Argument: when success entails a checkable state, checking the state is strictly cheaper than reconstructing it from narrative, and the narrative is only needed where the state check is ambiguous.

5. **Sample Like A Pollster** · breaks: The queue must drain before a release decision can be made. · oblique: buildable with 1995 technology
   Treat the release question as a proportion estimate: draw a stratified random sample of traces sized for the margin the decision needs, label only those, and report the failure rate with its interval, leaving the rest of the queue unlabeled on purpose. A confidence interval depends on sample size, not on population size, so the human effort per release is a constant, roughly 400 traces for a five-point margin at 95 percent confidence, whatever the daily volume. The cost is blindness to rare failures in strata the sample misses and no answer to per-trace questions, so this is a release gate, not a debugging tool. Wall: fixes human effort per release instead of letting it scale with traces.
   Grounding: Argument: for a large population the standard error of a proportion is governed by the sample size alone, which is why a poll of a thousand people bounds a nation's opinion.

6. **Label Once, Replay Forever** · breaks: Labels are consumed once, for the release they gate.
   Store every human verdict as a replayable pair of trace fingerprint and rubric version, so when the rubric, the judge, or the evaluated model changes, the existing labels re-grade the new judge for free and no human re-labels a trace that has already been judged. The cost is versioning discipline and fingerprint drift when trace formats change. Wall: every rubric or judge change stops costing a fresh review pass.
   Grounding: Untested: replay the last 500 human labels against the current judge and a candidate judge; if the candidate agrees more on the replay set with no new human work, the mechanism has paid for itself on its first upgrade.

**The stack:** Humans Grade The Judge and Disagreement Is The Queue form the spine, with Reviewers Write Checks as the loop that shrinks the queue over time and Sample Like A Pollster as the release gate that bounds what the spine costs. It accepts that the release decision carries a stated error bar instead of full human coverage, and targets human review of roughly 15 percent of traces, an assumed figure set by measured judge agreement, rather than 100 percent. The single biggest risk is correlated judge blindness: two judges sharing a failure mode agree confidently on wrong verdicts, so the audit sample must be stratified by task type and refreshed whenever the evaluated model changes.
