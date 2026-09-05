---
name: lateral-engineering
description: "Generate creative, out-of-the-box, lateral, non-obvious approaches to technical problems: system design, infra, data pipelines, agent architectures, performance, cost, reliability, and dev tooling. Use when asked 'don't give me the usual', 'how else could this be done', 'reframe this', or 'I want ideas, not best practices'; also use when an engineering design seems stuck, over-engineered, or its obvious fix is expensive and alternatives are wanted. Do NOT use when the user wants the safe, production-proven answer, routine implementation, incident mitigation, a factual explanation, or a trivial fix."
---

# Lateral engineering

Escape the median answer deliberately. Assume the user knows the standard solution;
produce alternatives that change what needs solving, rather than decorate that solution.
Use the procedure below because each stage blocks a different slide back into convention.
Keep this an advisory pass: proposing an experiment does not authorize running it,
editing files, provisioning infrastructure, or committing anything.
If the request falls outside the description, handle it normally without skill ceremony.

## 1. Restate the problem as a goal, not a mechanism

Rewrite the request as the outcome that matters. Turn "make the retry queue faster"
into "work completes without operator intervention within the required deadline."
Strip every implementation noun that is not a hard requirement; preserve actual
constraints rather than solving an easier problem by dropping them. Do not invent
scale, deadlines, or budgets. Put this one mechanism-free line at the top of the output.
The creative room lives between the named mechanism and the needed outcome.

## 2. Extract hidden assumptions

Privately draft the conventional solution in a few lines of reasoning, then inspect
what it takes for granted. Concrete artifacts expose assumptions that abstract
brainstorming misses: treat every noun in that draft as a candidate assumption.
Discard the draft; never show it unless the user asks for the conventional answer.
Retain 5–8 short declarative assumptions, distinguished from explicit hard requirements.

Look for assumptions about the unit of work, who does the work, when it happens,
where the boundary sits, what must be exact, what is scarce, which layer owns the
problem, and whether the success metric itself is negotiable. Publish the assumption
list, not the private draft or reasoning transcript.

## 3. Generate reframings by applying moves

Read [references/moves.md](references/moves.md) before generating; its concrete moves
prevent six renamed versions of the same intuition. Build a private candidate pool
with at least one reframing from each family:

- **Remove:** delete a step or layer assumed mandatory.
- **Relocate:** move the work to a different actor, time, or layer.
- **Invert:** reverse push/pull, sync/async, compute/store, exact/approximate, or truth ownership.
- **Import:** borrow a mechanism from an unrelated field, not just its vocabulary.
- **Embrace the constraint:** assume the bad thing happens; make the expensive thing the architecture.
- **Change the unit:** standardize the interface; batch, split, merge, quantize, or change deployment units.

Then generate at least one additional candidate under an oblique constraint chosen
randomly, before judging its relevance. If a random tool is available, draw uniformly
from the ten entries below; otherwise choose blindly before matching it to the problem
and do not claim tool-backed randomness. Relevance-chosen moves tend toward the obvious;
an arbitrary constraint forces paths your priors would not choose.

must work offline · buildable with 1995 technology · operated by someone who can't code ·
must get better as it fails more · runs on the smallest machine in the building ·
survives the team being fired · explainable in one sentence to a child · costs zero at rest ·
reversible at any point · what you'd build if you had to demo tomorrow

Treat the oblique constraint as a creative lens, not a newly discovered user requirement.
Keep its exact wording attached to the idea it produced. If that candidate fails
prosecution, push it further under the same constraint or draw again and regenerate;
retain at least one surviving oblique-tagged idea.

Generate at least seven candidates privately, then aim for **4–6 final reframings**
different in kind. Family coverage belongs to generation, not seven mandatory output
paragraphs. If two candidates break the same assumption, merge them or retain the one
that goes further; different technology names do not make different reframings.

## 4. Prosecute each candidate

Separate generation from judgment. Switch roles and argue that each candidate is
conventional: name the established pattern it really is and the senior engineer who
would suggest it in ten minutes. Use a role such as "the team's staff SRE" rather
than inventing a real person's opinion. Ask:

- Would a competent senior engineer propose this in the first ten minutes?
- Is this the standard answer with a library swap, a cache, or "add a queue"?
- Does it break an assumption the other candidates do not?
- Can it be grounded in a precedent from any field, a first-principles argument,
  or a cheap experiment that could settle whether it works?

A convincing charge means cut the candidate or push it further and prosecute again.
A familiar ingredient is allowed; acquit only when its application changes a specific
assumption here. No grounding of any kind means it is a vibe, not an idea.
Only acquittals ship. If fewer than three survive, return to step 2; missed assumptions
are often about success criteria or who does the work. With three, generate another
distinct acquittal so the final answer still contains 4–6.

Keep a brief internal record of candidates cut or changed so the filter is substantive,
without exposing a reasoning transcript. If the user has seen a previous round on this
problem, prosecute those ideas too. Briefly name convicted prior ideas and their pattern
in **The core**, showing the delta without reprinting the conventional solution.

## 5. Rank and present

Rank leverage (how much of the problem disappears) against plausibility (buildable
with what the user has). Place a brilliant but currently impossible idea last and label
that limitation; it may unlock a practical hybrid, but do not rank it as deployable.
Use exactly this output structure, extending the numbered list to 4–6 entries:

```text
**Goal:** <one line, mechanism-free>

**Assumptions the standard approach makes:**
- <assumption>
- ...

**Reframings, ranked:**

1. **<Name — 3–5 words>** · breaks: <assumption> [· oblique: <constraint> if applicable]
   <2–4 sentences: the idea, why it works, what it costs.>
   Grounding: <"Precedent: <system/paper/field>" | "Argument: <first-principles reason>" | "Untested: <cheapest experiment>">

2. ...

**The core:** <the one or two reframings that form the spine of a real solution, why they compose, and the single biggest risk>
```

Give each reframing a 3–5 word name so it can be referred to later. Replace template
placeholders and omit the literal brackets around an optional oblique tag.
Name its broken assumption explicitly, using the assumption list's wording or a clear
reference to it; without that link it is not a reframing. State the cost every time:
unconventional ideas trade something away, and hiding it makes the idea look like magic.
Commit to each idea for its paragraph; keep uncertainty in precise limitations and
grounding rather than hedging the proposal into mush.

Require grounding, not precedent. Requiring an existing implementation filters out the
very ideas the user wants. **Untested** with a concrete cheap experiment and an observable
pass/fail signal is a feature; do not disguise a proposed experiment as a result.
Never invent a precedent. Verify uncertain attributions when source access is available;
use "similar in spirit to" for a partial analogy and identify the shared mechanism.
If no source can be established, use an argument or experiment instead.
For system design, let ideas compose: **The core** names the practical spine, why its
parts fit, and the single biggest risk rather than forcing a single winner.

## Calibration

Assume a senior engineer building agent systems, evals, and infra, deeply familiar
with distributed systems, LLM tooling, TypeScript/Node, Postgres, and containers.
Spend words on the idea, not explanations of KV caches or message queues.
If the problem is too thin to extract assumptions, ask one or two sharp questions
about scale, latency, budget, or what already exists and proceed with clearly labelled
working assumptions. Keep the goal first; place those questions briefly in **The core**
so clarification does not become a long intake or an excuse to stall.

## Anti-patterns

- "Use microservices / event sourcing / a graph DB" as if the buzzword were the idea.
- Five ideas that all reduce to caching at different layers.
- Ideas with no stated cost, distinct broken assumption, or grounding.
- Reprinting the conventional draft, private prosecution, or reasoning transcript.
- Brainstorm-voice filler such as "Here are some exciting possibilities!" Lead with the goal.

Before sending, check: mechanism-free goal; 5–8 assumptions; 4–6 named, distinct
reframings; cost and grounding on every entry; an oblique survivor; and a composable spine.
