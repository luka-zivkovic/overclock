---
name: lateral-engineering
description: "Generate creative, out-of-the-box, lateral, non-obvious approaches to technical problems: system design, infra, data pipelines, agent architectures, performance, cost, reliability, and dev tooling. Use when asked 'don't give me the usual', 'how else could this be done', 'reframe this', 'what could we trade', or 'I want ideas, not best practices'; also use when the user says a design is stuck or over-engineered, or that the obvious fix is too expensive, and wants alternatives. Do NOT use when the user wants the safe, production-proven answer, routine implementation, incident mitigation, a factual explanation, a walkthrough of standard options, or a trivial fix."
---

# Lateral engineering

Escape the median answer deliberately. Assume the user knows the standard solution; produce
alternatives that change what needs solving rather than decorate it. The ideas worth having are
arbitrages: a wall the conventional design cannot pass, paid for with a surplus it never uses.
Find the user's version of that trade in the user's own situation. This is an advisory pass:
proposing an experiment does not authorize running it, editing files, provisioning anything, or
committing. If the request falls outside the description, handle it normally without ceremony.

## 1. Goal and wall

Rewrite the request as the outcome that matters, in one mechanism-free line. Turn "make the
retry queue faster" into "work completes without operator intervention within the deadline."
Strip implementation nouns that are not hard requirements; keep real constraints rather than
solving an easier problem by dropping them.

Then name the wall: the one quantitative limit the conventional answer cannot get past, such as
a memory ceiling, a rate, a budget, a latency, a headcount, or a deadline. Take it from the
prompt. If the prompt has none, ask for it in the same turn and proceed with a labelled working
assumption; never present an invented number as a fact.

## 2. Inventory the specific

Ideas come from facts about this situation that the general solution ignores. Fill four lines
from the prompt, or ask for them in one short block rather than a questionnaire:

- **Surplus:** what is abundant or idle here (bandwidth, offline compute, model tokens, user
  attention, calendar time, historical data), including what became cheap after this design was
  set and is still priced as expensive.
- **Fixed:** what is known ahead of time or never changes (a path, a schema, a fixed model, a
  closed vocabulary, a stable corpus). Anything fixed can be precomputed, enumerated, or searched.
- **Ratings:** which limits are vendor ratings, policies, or habits rather than physics, and what
  a cheap test of the real limit would cost.
- **Negotiable freedoms:** which product freedoms the user might trade for a guarantee.

Surplus is an input, never the seed. "Use a model for it" is a buzzword until it names the wall
it moves and the assumption it breaks.

## 3. Extract hidden assumptions

Privately draft the conventional solution in a few lines, then treat every noun in it as a
candidate assumption. Discard the draft; never show it unless the user asks for the conventional
answer. Retain 5 to 8 short declarative assumptions, kept distinct from hard requirements. Look at
the unit of work, who does it, when, where the boundary sits, what must be exact, what is scarce,
which layer owns the problem, and whether the success metric itself is negotiable.

## 4. Generate by applying moves

Read [references/moves.md](references/moves.md) before generating; its concrete moves prevent six
renamed versions of one intuition. Build a private pool with at least one candidate from each
family:

- **Remove** a step or layer assumed mandatory.
- **Relocate** the work to a different actor, time, or layer.
- **Invert** push/pull, sync/async, compute/store, exact/approximate, or truth ownership.
- **Import** a mechanism from an unrelated field, not just its vocabulary.
- **Embrace the constraint:** assume the bad thing happens; make the expensive thing the design.
- **Change the unit:** batch, split, merge, quantize, or change the deployment unit.
- **Arbitrage:** spend an inventoried surplus to buy relief on the wall; specialise to the
  instance; trade a negotiable freedom for a guarantee.

You may propose a constraint the user did not state when accepting it makes the wall disappear.
Tag it `· accepts:` so the user sees the trade; it is an offer, not a discovered requirement. The
catalog's precedents illustrate moves; cite one as an idea's grounding only when its mechanism
genuinely matches, and prefer a precedent from the user's own field or an experiment.

Add one candidate under an oblique constraint drawn blindly from the ten in the catalog before
judging relevance; if a random tool is available use it, otherwise choose before matching and
do not claim tool-backed randomness. Keep the constraint's wording attached to the idea it
produced. Generate at least seven candidates privately, then aim for 4 to 6 final reframings
different in kind. If two break the same assumption, merge them or keep the one that goes
further; different technology names are not different reframings.

## 5. Prosecute each candidate

Separate generation from judgment. Switch roles, such as "the team's staff SRE" rather than a
named real person, and argue against each candidate:

- What does it do to the wall, and by how much? An idea that leaves the number where it is is
  decoration however novel it sounds.
- What does it give up? Every real idea trades something away; no cost means a vibe.
- Does it break an assumption the other candidates do not?
- Can it be grounded in a precedent from any field, a first-principles argument, or a cheap
  experiment with an observable pass/fail signal?

A familiar ingredient pushed to a degree nobody does acquits: precompute everything that is
fixed, run the cheap thing a thousand times, build a tool instead of a feature. A novel-sounding
idea that leaves the wall alone convicts. If fewer than three survive, return to step 2; the missing input is usually a surplus
or a negotiable freedom. Keep a brief internal record of cuts so the filter is substantive. If the
user has seen a previous round, prosecute those ideas too and name the convicted ones in **The
stack** without reprinting them.

## 6. Rank and present

Rank leverage (how much of the wall disappears) against plausibility (buildable with the
inventory). Place a brilliant but currently impossible idea last and say so. Use exactly this
structure, extending the numbered list to 4 to 6 entries:

```text
**Goal:** <one line, mechanism-free>
**Wall:** <the limit and its number; mark "assumed" when it is a working assumption>
**Inventory:** surplus: <...> · fixed: <...> · ratings: <...> · freedoms: <...>

**Assumptions the standard approach makes:**
- <assumption>
- ...

**Reframings, ranked:**

1. **<Name, 3 to 5 words>** · breaks: <assumption> [· accepts: <self-imposed constraint>] [· oblique: <constraint>]
   <2 to 4 sentences: the idea, why it works here, what it costs, what it does to the wall.>
   Grounding: <"Precedent: <system/paper/field>" | "Argument: <first-principles reason>" | "Untested: <cheapest experiment and its pass/fail signal>">

2. ...

**The stack:** <one composition of 2 to 4 decisions: the constraint it accepts, the trick that unlocks, the number it reaches, its cost, and the single biggest risk>
```

Replace placeholders and omit the brackets around optional tags. Name the broken assumption in
the assumption list's wording. Commit to each idea for its paragraph; keep uncertainty in the
grounding line. Require grounding, not precedent: **Untested** with a concrete cheap experiment is
a feature, so long as the experiment is not reported as a result. Never invent a precedent; verify
uncertain attributions when source access exists, and use "similar in spirit to" for a partial
analogy.

## Calibration

Calibrate to the user's evident level and stack; default to a senior engineer and spend words on
the idea, not on explaining familiar mechanisms. When the problem is too thin, ask one or two
sharp questions for the wall and inventory and proceed with labelled working assumptions; put the
questions briefly in **The stack** so clarification never becomes a long intake.

## Anti-patterns

- A technology name as the idea, including "use an LLM for it."
- Five ideas that all reduce to caching at different layers.
- Ideas with no stated cost, no distinct broken assumption, no grounding, or no effect on the wall.
- Reprinting the conventional draft, the prosecution, or a reasoning transcript.
- Brainstorm-voice filler. Lead with the goal.

Before sending, check: mechanism-free goal; a wall with a number; four inventory lines; 5 to 8
assumptions; 4 to 6 named, distinct reframings; cost, grounding, and wall effect on every entry;
an oblique survivor; and a stack that names its accepted constraint and biggest risk.
