# UX skill — planning record (2026-09-25)

Status: **planning only, nothing built.** This file exists so the build session starts from a
grounded brief instead of inventing UX rules. It ends with a paste-ready prompt for that session.

What the maintainer asked for: a skill that helps with the UX of the applications they build,
naming the axes *naming conventions*, *flow*, and *positioning*, and asking that the skill lean on
established literature rather than invented rules.

Two research passes fed this record: a survey of published UX/UI skills for coding agents
(section 4) and a literature survey with verified sources (section 5). Both were run on
2026-09-25; URLs marked [U] were not directly fetched.

---

## 1. Questions the maintainer must answer before the build

The build session should ask these first. Each has a recommended default so the session can
proceed on a stated assumption if no answer comes.

| # | Question | Why it matters | Default if unanswered |
|---|---|---|---|
| Q1 | Which application types: web apps, mobile (iOS/Android), desktop, or all? Which frameworks? | Button order, casing, and navigation conventions differ per platform (section 6). A skill that ignores this gives wrong advice half the time. | Web apps first; platform detection step with a per-platform conventions reference. |
| Q2 | Is `impeccable` still installed, and do you use `frontend-design`? | They own visual polish, a11y audit, and sentence-level microcopy rewriting. The new skill should hand off to them, not duplicate. | Assume installed; guard the handoff with an availability check and a scope stop. |
| Q3 | Do you want a persistent project artifact (a `UX.md` or `GLOSSARY.md` with the app's terminology, casing policy, and platform conventions)? | It is the only way "use the same term everywhere" becomes enforceable across sessions. It also widens write scope, which Overclock treats carefully. | Yes, one file at the project root, written only on explicit request, never auto-committed. |
| Q4 | User-invoked (`/ux …`) or model-invoked (fires on UI edits)? | Model-invoked UX advice would trigger on almost every UI edit and misfire on trivial work. The two-loads model in `docs/skill-authoring-notes.md` favours explicit invocation for a skill this broad. | User-invoked with explicit modes. Revisit a narrow model-invoked trigger later. |
| Q5 | Review-only, or also generative (draft the flow, propose the labels)? | Review-only is easier to right-size and eval. Generative help is where the ecosystem is thinnest (section 4). | Both, but generation always produces a proposal for the user to accept; the skill never applies label changes across the codebase without an explicit go. |
| Q6 | Is there a design system or content style guide already in your apps? | If yes, the skill should read it as the source of truth and only fall back to the literature defaults. | Read `DESIGN.md`, `PRODUCT.md`, a style guide, or design tokens if present; otherwise use literature defaults. |

---

## 2. Decisions the planning already supports (recommendations)

**D1 — Scope.** Own three things nothing in the kit or ecosystem owns well: (a) terminology and
label consistency across a codebase, (b) task-flow design and critique for a feature, and
(c) placement of actions and controls within a screen. Treat feedback, UI states, forms, and
error recovery as review lenses inside (b) and (c), not as separate modes. Explicitly do **not**
own visual aesthetics, spacing rhythm, colour, typography, or accessibility audits; those are
delegated (D6).

**D2 — Modes (working names).** Three explicit modes keep the skill right-sized:
- `review` — heuristic evaluation of one feature or screen. Output: findings, each with a
  heuristic id (Nielsen H1–H10), location (`file:line` or route), severity 0–4, evidence, and a
  concrete fix. Capped list; a coherent screen yields a short "holds up" result.
- `names` — build or check the terminology glossary. Deterministic scan of UI strings for label
  drift (Remove/Delete/Trash, Save/Apply, mixed casing, generic labels like OK/Submit/Click here),
  then a proposal table: term, canonical form, occurrences. Writes the glossary only on request.
- `flow` — design or critique a task flow: entry point, steps, what each step needs, where
  confirmation or undo belongs, what happens after submit, the five UI states per step, exit and
  back paths. Output: an ordered flow table plus the placement decisions per step.

**D3 — Leading word.** Candidate: **scent** (information scent, from NN/g and the IA literature).
Every label, position, and step should tell the user where they are and what happens next. It
anchors all three modes: a label without scent is generic, a screen without scent hides its primary
action, a flow without scent loses the user between steps. Alternatives: *signifier* (Norman),
*wayfinding*. Decide in the build session; do not ship without one.

**D4 — Memory artifact.** One project-root file (`UX.md`, name open) holding: target platform(s),
casing policy, button order, verb vocabulary (Add/Create, Remove/Delete, Save/Apply), the term
glossary, and the app's named flows. Modes read it first; literature defaults apply only where it
is silent. It is the "settled decisions" carrier: a term the user chose is not re-litigated.

**D5 — Invocation and right-sizing.** User-invoked. Even so, the SKILL.md must state anti-triggers
so a model does not reach for it via description: single-string rewording, CSS/spacing work,
colour/typography, accessibility audits, marketing copy, backend changes with no UI. A one-label
question gets a one-line answer, not a review.

**D6 — Handoffs (guarded, with standalone fallback).**
- Visual polish, hierarchy by spacing/colour, aesthetics → `impeccable critique|polish|layout` or
  `frontend-design`. Fallback: note "visual review not performed" and stop.
- Accessibility audit → `impeccable audit` or Vercel `web-design-guidelines`. Fallback: apply only
  the mechanical floor (target size, visible label, accessible name, not colour-only) and say the
  rest was not checked.
- Sentence-level rewriting of a single string → `impeccable clarify` or plain answer. The new
  skill's naming mode is about consistency across strings, not polishing one.
- Long-form prose → `natural-writing` (which already excludes UI strings, so the seam is clean).

**D7 — Boundaries that keep it Overclock-shaped.** Read-only scans. No auto-commit. Codebase-wide
label edits only after the user approves the proposal table, and then one term at a time with the
diff shown. No network fetches at run time (Vercel's skill fetches guidelines live; ours ships
them in `references/`). Never invent a platform convention; cite the reference file.

**D8 — Evidence tier.** `objective` for the glossary/drift scanner (planted-drift recall,
read-only boundary, no-write-without-approval), `rubric` for review and flow quality
(independent judge, predeclared cases), routing battery only if a model-invoked trigger is added.

**D9 — Packaging.** New plugin, one skill with modes, references split per mode plus one
per-platform conventions file. Working plugin/skill name: `ux-craft` (open; alternatives
`interface-craft`, `scent`). Version 0.1.0, marketplace entry, capabilities.json entry,
`overclock-setup` bump, CHANGELOG, strategy ledger entry.

---

## 3. Dimension map — what the skill must think about

Each row: the question the skill asks, the literature it leans on, a candidate rule that can be
checked rather than felt, and who owns it.

| Dimension | Core question | Grounding | Candidate checkable rule | Owner |
|---|---|---|---|---|
| Terminology | Is one concept called one thing everywhere? | Yifrah; Podmajersky; Carbon action labels; NN/g UX writing | Glossary with one canonical term per concept; scanner flags synonyms (remove/delete/trash) | this skill (`names`) |
| Button and action labels | Does the label say what happens? | Apple HIG Alerts; Microsoft dialog guide; Polaris; Atlassian; Vercel guidelines | Verb (+ object), never OK/Yes/No/Submit on a commit action; "Cancel" is literally Cancel; sentence case unless platform says otherwise | this skill (`names`) |
| Links and nav labels | Do they carry scent? | NN/g Better Link Labels (4 Ss); category names | Flag "Click here", "Learn more", "More"; labels by task/topic, not format | this skill (`names`) |
| Error messages | What failed, why, how to fix, in the user's words? | NN/g error-message rubric; GOV.UK error message | Names the field, states the fix, no codes; banned words: please, sorry, invalid, forbidden, illegal; error text reuses the label wording | this skill (`review`) |
| Casing and punctuation | One policy? | Atlassian; Material; Microsoft style guide; Apple | Mixed Title/Sentence case across labels is a finding; no trailing period on labels | this skill (`names`) |
| Information architecture | Can the user predict where things live? | Rosenfeld/Morville/Arango; NN/g IA mistakes; card sorting/tree testing | Nav categories mutually exclusive, in user vocabulary; >7 top-level items recommends a tree test | this skill (`flow`) |
| Location awareness | Does the user know where they are? | NN/g breadcrumbs; "You are here" | Active nav state or breadcrumb on every routed view | this skill (`flow`) |
| Task flow | Fewest steps to the goal without losing state? | GOV.UK one-thing-per-page, question pages; Krug | Multi-step flows show step context, allow back without data loss, show progress | this skill (`flow`) |
| Progressive disclosure | Is the primary path visible, the rest on request? | NN/g progressive disclosure; Hick's law | Primary path never behind an "Advanced" toggle; secondary options collapsed | this skill (`flow`, `review`) |
| Onboarding | Contextual over tutorial? | NN/g onboarding tutorials, mobile onboarding | Tours skippable with progress; empty state carries the first-task CTA | this skill (`flow`); `impeccable onboard` for the build |
| Primary action placement | One dominant action, where the platform expects it? | GOV.UK button; Material buttons; NN/g OK-Cancel; Apple HIG | One primary button per screen; order per platform (section 6); never mixed within one app | this skill (`review`) |
| Destructive actions | Separated and recoverable? | NN/g consequential options; confirmation dialogs; Cancel vs Close | Destructive not adjacent to primary; undo or confirmation that names the object, not both by default | this skill (`review`) |
| Grouping | Do related controls read as related? | Gestalt proximity, common region, similarity (NN/g) | Label closer to its own field than the next; identical-looking controls behave identically | this skill (`review`) |
| Reach and target size | Can it be hit? | Fitts's law; Hoober thumb zones; WCAG 2.5.8 | Targets ≥24 px; mobile primary actions in thumb reach, destructive out of it | this skill (mechanical floor only); a11y audit delegated |
| Feedback and status | Does every action answer? | Norman feedback; NN/g H1; response-time limits; Doherty | >1 s shows an indicator; >10 s shows progress; async buttons enter a loading state; success is confirmed | this skill (`review`) |
| UI states | Ideal, empty, error, partial, loading all designed? | Hurff UI stack; NN/g empty states | Every data view has all five; empty state explains why and offers one CTA | this skill (`flow`, `review`) |
| Forms | Labeled, ordered, forgiving? | Wroblewski; Silver; NN/g forms; GOV.UK error summary | Persistent visible label above field; placeholder never the only label; inline error plus summary with focus; input preserved on error; validate on submit/blur | this skill (`review`) |
| Platform consistency | Does it follow what the user already knows? | Jakob's law; NN/g H4; HIG/Material/Fluent/Carbon | Detect platform, load its conventions file, check internal consistency (same term, same place, same icon) | this skill (`review`) |
| Visual hierarchy, spacing, colour, type | Delegated | Refactoring UI; NN/g visual hierarchy | Out of scope; handoff | `impeccable`, `frontend-design` |
| Accessibility beyond the floor | Delegated | WCAG 2.2; ARIA APG; Inclusive Components | Out of scope; handoff | `impeccable audit`, Vercel guidelines |
| Review method | Traceable, severity-rated findings | Nielsen & Molich; NN/g severity ratings, HE workbook | Each finding: heuristic id, location, severity 0–4, evidence, fix | this skill (`review`) |

---

## 4. Ecosystem grounding — what already exists

Grounding is research, not a gate (strategy principle 3). It shapes the seams.

| Skill | What it owns | Invocation | Gap relative to this plan |
|---|---|---|---|
| Anthropic `frontend-design` — https://github.com/anthropics/skills/blob/main/skills/frontend-design/SKILL.md | Aesthetic direction, typography, anti-template visuals; a few copy principles ("Save changes" not "Submit", sentence case) | model-invoked on UI builds | No flows, IA, or placement reasoning; copy guidance is principles, not a naming system |
| `impeccable` (Paul Bakaus) — https://github.com/pbakaus/impeccable | `craft`, `shape`, `critique`, `audit` (a11y/perf/responsive), `polish`, `extract`, `layout`, `onboard`, `harden`, `clarify`; 61 deterministic detectors; reads PRODUCT.md/DESIGN.md | `/impeccable <command>` | `clarify` is the strongest microcopy piece and asks for consistent nouns/verbs, but consistency is advice inside a rewrite, not a scanned, enforced glossary. `shape` explicitly does not do IA, layout, or flows. Only `onboard` is flow-shaped. |
| Vercel `web-design-guidelines` — https://github.com/vercel-labs/agent-skills/blob/main/skills/web-design-guidelines/SKILL.md (guidelines: https://github.com/vercel-labs/web-interface-guidelines) | Review checklist: interactions, animation, layout, content, forms, performance; terse `file:line` findings | "review my UI", "audit design" | Review-only; fetches guidelines at run time; casing rules are Vercel house style; no flows or IA |
| `ui-ux-pro-max` — https://github.com/nextlevelbuilder/ui-ux-pro-max-skill | Catalogs of styles, palettes, font pairs, design-system generator | chat, `/ui-ux-pro-max` | Visual tokens only |
| Anthropic `ux-copy` (knowledge-work-plugins, design) — https://github.com/anthropics/knowledge-work-plugins/tree/HEAD/design/skills/ux-copy | Write/review microcopy, errors, empty states, CTAs; variants with rationale | "what should this button say?" | Sentence-level; no cross-app glossary, flow, or placement |
| humbleteam/ux-writing — https://github.com/humbleteam/ux-writing ; content-designer/ux-writing-skill — https://github.com/content-designer/ux-writing-skill | Per-element copy rules, banned AI-tell patterns, voice/tone | explicit | Sentence-level only |
| tommyjepsen/awesome-ux-skills — https://github.com/tommyjepsen/awesome-ux-skills ; Owl-Listener/designer-skills — https://github.com/Owl-Listener/designer-skills | Designer-facing research and review packs: personas, journey maps, Nielsen heuristics review, IA, onboarding critique | explicit | Research frameworks; do not read the app's routes/components and propose flows in code |
| rampstackco information-architecture — https://github.com/rampstackco/claude-skills/blob/main/skills/information-architecture/SKILL.md | Sitemaps, navigation, URL taxonomy | explicit | Website/content oriented, not app UI |

**Synthesis.** Well covered elsewhere: visual direction, a11y and design-compliance audits,
single-string microcopy, design-system extraction. Thin: naming consistency as an enforced,
codebase-wide artifact. Absent for app builders: flow design that reads the app's routes and
components, placement reasoning beyond spacing, and one lightweight review that ties copy, flow,
and placement together for a feature. That is the space D1 claims.

---

## 5. Literature by area (verified sources)

[V] fetched or confirmed on the publisher's domain; [U] wording confirmed only via mirror or
search snippet. The build session should ship the *rules* derived from these in `references/`,
with the citation, not the prose.

**Foundations**
- Nielsen, 10 Usability Heuristics [V] https://www.nngroup.com/articles/ten-usability-heuristics/
- Norman, The Design of Everyday Things (rev.) [V] https://jnd.org/books/the-design-of-everyday-things-revised-and-expanded-edition/ — signifiers, mapping, feedback, conceptual models
- Krug, Don't Make Me Think, Revisited [V] https://sensible.com/ — scanning, satisficing, omit needless words
- Yablonski, Laws of UX [V] https://lawsofux.com/ — Fitts, Hick, Jakob, Miller, Tesler, Doherty, peak-end, Zeigarnik, aesthetic-usability, proximity, common region, similarity, serial position, Von Restorff

**Naming, labels, microcopy**
- Apple HIG, Alerts [U, JS page; wording via mirror] https://developer.apple.com/design/human-interface-guidelines/alerts — verb-phrase buttons, avoid OK as default, always Cancel
- Apple HIG, Writing [V] https://developer.apple.com/design/human-interface-guidelines/writing
- Microsoft Win32 UX guide, Dialog Boxes [V] https://learn.microsoft.com/en-us/windows/win32/uxguide/win-dialog-box — specific commit buttons; permits deliberate Yes/No to force reading
- Microsoft Writing Style Guide [V] https://learn.microsoft.com/en-us/style-guide/welcome/
- Shopify Polaris content [V] https://shopify.dev/docs/apps/design/content — verb-first CTAs, active voice (the older verb+noun/no-punctuation page now redirects; [U] for exact wording)
- Atlassian, Language and grammar [V] https://atlassian.design/foundations/content/language-and-grammar — sentence case, active voice, contractions
- Material 3, UX writing best practices [V] https://m3.material.io/foundations/content-design/style-guide/ux-writing-best-practices
- IBM Carbon, Action labels [V] https://carbondesignsystem.com/guidelines/content/action-labels/ — Add vs Create, Apply vs Save, Remove vs Delete
- Fluent 2, Content design [V] https://fluent2.microsoft.design/content-design
- NN/g, Error-Message Guidelines [V] https://www.nngroup.com/articles/error-message-guidelines/ and Scoring Rubric [V] https://www.nngroup.com/articles/error-messages-scoring-rubric/
- GOV.UK Design System, Error message [V] https://design-system.service.gov.uk/components/error-message/ — "Enter X", "X must be…", banned words
- NN/g, Better Link Labels [V] https://www.nngroup.com/articles/better-link-labels/ ; "Learn More" links [V] https://www.nngroup.com/articles/learn-more-links/ ; Category names [V] https://www.nngroup.com/articles/category-names-suck/
- NN/g, UX Writing study guide [V] https://www.nngroup.com/articles/ux-writing-study-guide/
- Yifrah, Microcopy: The Complete Guide (2nd ed.) [V listing] https://www.goodreads.com/book/show/34847317-microcopy
- Podmajersky, Strategic Writing for UX [V] https://www.oreilly.com/library/view/strategic-writing-for/9781492049388/
- Mailchimp Content Style Guide [V] https://styleguide.mailchimp.com/ — voice vs tone; no humour in error or destructive contexts

**Flow, navigation, information architecture**
- Rosenfeld, Morville, Arango, Information Architecture (4th ed.) [V] https://www.oreilly.com/library/view/information-architecture-4th/9781491913529/
- NN/g, Card sorting [V] https://www.nngroup.com/articles/card-sorting-definition/ ; Tree testing [V] https://www.nngroup.com/articles/tree-testing/ ; comparison [V] https://www.nngroup.com/articles/card-sorting-tree-testing-differences/
- Optimal Workshop, Card sorting 101 [V] https://www.optimalworkshop.com/101-guides/card-sorting-101/introduction-to-card-sorting ; Tree testing [V] https://blog.optimalworkshop.com/tree-testing/
- NN/g, 3 common IA mistakes [V] https://www.nngroup.com/articles/3-ia-mistakes/ ; Format-based navigation [V] https://www.nngroup.com/articles/format-based-navigation/ ; Breadcrumbs [V] https://www.nngroup.com/articles/breadcrumbs/ ; You are here [V] https://www.nngroup.com/articles/navigation-you-are-here/
- NN/g, Progressive disclosure [V] https://www.nngroup.com/articles/progressive-disclosure/
- NN/g, Onboarding tutorials vs contextual help [V] https://www.nngroup.com/articles/onboarding-tutorials/ ; Mobile-app onboarding [V] https://www.nngroup.com/articles/mobile-app-onboarding/
- GOV.UK Service Manual, Structuring forms [V] https://www.gov.uk/service-manual/design/form-structure ; Question pages pattern [V] https://design-system.service.gov.uk/patterns/question-pages
- Laws of UX, Zeigarnik effect [V] https://lawsofux.com/zeigarnik-effect/ — progress indicators in multi-step flows

**Positioning, hierarchy, grouping**
- NN/g, Visual hierarchy [V] https://www.nngroup.com/articles/visual-hierarchy-ux-definition/ ; Principles of visual design [V] https://www.nngroup.com/articles/principles-visual-design/
- Wathan & Schoger, Refactoring UI [V site; content paywalled] https://www.refactoringui.com/
- NN/g Gestalt: Proximity [V] https://www.nngroup.com/articles/gestalt-proximity/ ; Common region [V] https://www.nngroup.com/articles/common-region/ ; Similarity [V] https://www.nngroup.com/articles/gestalt-similarity/
- NN/g, Fitts's law [V] https://www.nngroup.com/articles/fitts-law/ ; Consequential options near benign ones [V] https://www.nngroup.com/articles/proximity-consequential-options/
- Hoober, How do users really hold mobile devices? [V] https://www.uxmatters.com/mt/archives/2013/02/how-do-users-really-hold-mobile-devices.php ; Smashing, The thumb zone [V] https://www.smashingmagazine.com/2016/09/the-thumb-zone-designing-for-mobile-users/
- NN/g, F-shaped pattern [V] https://www.nngroup.com/articles/f-shaped-pattern-reading-web-content/
- Material 3, Buttons [V] https://m3.material.io/components/buttons/guidelines ; GOV.UK, Button [V] https://design-system.service.gov.uk/components/button/
- NN/g, OK-Cancel or Cancel-OK? [V] https://www.nngroup.com/articles/ok-cancel-or-cancel-ok/

**Feedback, status, error prevention**
- NN/g, Visibility of system status [V] https://www.nngroup.com/articles/visibility-system-status/ ; Response times [V] https://www.nngroup.com/articles/response-times-3-important-limits/ ; Progress indicators [V] https://www.nngroup.com/articles/progress-indicators/ ; Skeleton screens [V] https://www.nngroup.com/articles/skeleton-screens/ ; Doherty threshold [V] https://lawsofux.com/doherty-threshold/
- NN/g, Slips [V] https://www.nngroup.com/articles/slips/ ; Mistakes [V] https://www.nngroup.com/articles/user-mistakes/ ; Confirmation dialogs [V] https://www.nngroup.com/articles/confirmation-dialog/ ; User control and freedom [V] https://www.nngroup.com/articles/user-control-and-freedom/ ; Cancel vs Close [V] https://www.nngroup.com/articles/cancel-vs-close/

**Forms and UI states**
- Wroblewski, Web Form Design [V] https://rosenfeldmedia.com/books/web-form-design/ (deck: https://static.lukew.com/webforms_lukew.pdf)
- Silver, Form Design Patterns [V] https://www.smashingmagazine.com/printed-books/form-design-patterns/
- NN/g, Web form usability [V] https://www.nngroup.com/articles/web-form-design/ ; Placeholders are harmful [V] https://www.nngroup.com/articles/form-design-placeholders/ ; Reporting errors in forms [V] https://www.nngroup.com/articles/errors-forms-design-guidelines/
- GOV.UK, Error summary [V] https://design-system.service.gov.uk/components/error-summary/
- Hurff, The UI stack [V] https://www.scotthurff.com/posts/why-your-user-interface-is-awkward-youre-ignoring-the-ui-stack/ ; NN/g, Empty states [V] https://www.nngroup.com/articles/empty-state-interface-design/

**Accessibility floor (the rest is delegated)**
- WCAG 2.2 new criteria [V] https://www.w3.org/WAI/standards-guidelines/wcag/new-in-22/ ; Target size minimum [V] https://www.w3.org/WAI/WCAG22/Understanding/target-size-minimum.html
- ARIA Authoring Practices Guide [V] https://www.w3.org/WAI/ARIA/apg/
- Pickering, Inclusive Components [V] https://inclusive-components.design/
- GOV.UK, Making your service accessible [V] https://www.gov.uk/service-manual/helping-people-to-use-your-service/making-your-service-accessible-an-introduction ; Home Office dos and don'ts [V] https://accessibility.blog.gov.uk/2016/09/02/dos-and-donts-on-designing-for-accessibility/

**Heuristic evaluation as a method**
- Nielsen & Molich, CHI 1990 [V] https://dl.acm.org/doi/10.1145/97243.97281
- NN/g, How to conduct a heuristic evaluation [V] https://www.nngroup.com/articles/how-to-conduct-a-heuristic-evaluation/ ; Severity ratings [V] https://www.nngroup.com/articles/how-to-rate-the-severity-of-usability-problems/ ; Workbook PDF [V] https://media.nngroup.com/media/articles/attachments/Heuristic_Evaluation_Workbook_-_Nielsen_Norman_Group.pdf

**Platform conventions**
- Apple HIG [V] https://developer.apple.com/design/human-interface-guidelines/ ; Material 3 foundations [V] https://m3.material.io/foundations ; Fluent 2 [V] https://fluent2.microsoft.design/content-design ; Carbon content [V] https://carbondesignsystem.com/guidelines/content/overview/ ; Atlassian content [V] https://atlassian.design/foundations/content ; NN/g Consistency and standards [V] https://www.nngroup.com/articles/consistency-and-standards/ ; Jakob's law [V] https://lawsofux.com/jakobs-law/

---

## 6. Where the literature disagrees (the skill must pick per platform, never mix)

- **Button order.** NN/g says follow the platform. Apple: Cancel leading, primary trailing
  (Cancel left, action right). Windows: right-aligned row, action before Cancel. Material
  dialogs: confirming action right, dismissive to its left [U]. GOV.UK forms: primary first,
  left-aligned to the form. Rule: detect platform, load its order, flag any screen that deviates
  from the app's own convention.
- **Placeholders and floating labels.** NN/g: placeholders harmful, floating labels tolerable.
  Material uses floating labels natively. GOV.UK bans placeholder-as-label. Rule that survives all
  three: placeholder text never carries required information.
- **Required vs optional markers.** NN/g: mark the minority (usually optional). GOV.UK and
  Wroblewski differ in convention. Rule: one convention per app, recorded in the memory artifact.
- **Casing.** Sentence case is the majority (Atlassian, Material, Microsoft, GOV.UK); Apple uses
  title case for some controls; Vercel uses Title Case for product headings and buttons. Rule: one
  policy per app, recorded, then linted.
- **Generic Yes/No.** Mostly banned, but Microsoft allows it deliberately on confirmations to
  force reading. Rule: default to specific verbs; a documented exception is acceptable if the
  memory artifact records it.

---

## 7. Overclock constraints the build must satisfy

From `AGENTS.md`, `docs/strategy.md`, and `docs/skill-authoring-notes.md`:

- Ledger entry in `docs/strategy.md` (Demand, Grounding, Product shape, Boundaries, Evidence,
  Next). Demand is satisfied by the direct maintainer request (principle 4).
- Skill at `plugins/<plugin>/skills/<skill>/SKILL.md`; `agents/openai.yaml` with quoted
  `display_name`, `short_description` (25–64 chars), one-sentence `default_prompt` naming
  `$<skill-name>`; if user-invoked, `disable-model-invocation: true` and
  `policy.allow_implicit_invocation: false` must agree.
- Manifest at `plugins/<plugin>/.claude-plugin/plugin.json`; marketplace entry; capabilities.json
  entry with an `overclock-setup` bump; CHANGELOG entry.
- Standalone: every reference, script, template resolves inside the skill directory; sibling
  handoffs guarded with an availability check and a safe fallback.
- Right-sizing: concrete positive triggers, explicit anti-triggers, trivial work stays a no-op.
- Authoring checklist: a leading word; no no-op lines; positive phrasing over negation where the
  line is not a safety boundary; checkable completion criteria per mode; load stubs that name
  what a reference contains and the cost of skipping it.
- Evidence: committed live-eval cases under `qa/evals/<plugin>/`, tier declared; deterministic
  tests for scanner behaviour and write boundaries; routing battery under `qa/trigger-battery/`
  only if model-invoked.
- Validation before handoff: the full suite in `AGENTS.md`, plus `claude plugin validate .` when
  manifests change; casefile scan needs an ignore entry with a reason if the scanner script
  trips a warning.
- No auto-commit, no silent widening of write scope, setup stays report-only.

---

## 8. The prompt for the build session

Paste this into a fresh session in the Overclock repo. Fill the bracketed answers first, or leave
them and let the session ask.

```text
You are building a new Overclock skill for application UX. This is a build session; the planning
is done and recorded in docs/brainstorm/ux-skill-planning-2026-09-25.md. Read that file first,
then AGENTS.md, docs/strategy.md (operating principles and the untangle and lateral-engineering
ledger entries as shape references), and docs/skill-authoring-notes.md. Do not re-litigate the
planning record's decisions unless you find evidence that one is wrong; if so, say which and why
before proceeding.

My answers to the planning questions (section 1 of the record):
- Q1 application types and frameworks: [answer]
- Q2 impeccable / frontend-design installed: [answer]
- Q3 persistent UX.md artifact: [yes/no, name]
- Q4 invocation: [user-invoked / model-invoked]
- Q5 review-only or also generative: [answer]
- Q6 existing design system or style guide: [answer]
Where an answer is blank, use the record's default and state the assumption in your first reply.

Build in this order, stopping for my confirmation after step 2 and after step 4.

1. Confirm the shape. Restate in ten lines or fewer: the skill and plugin name, the leading word,
   the modes and their outputs, the memory artifact, the four handoffs and their standalone
   fallbacks, and the write scope. Name the anti-triggers. Name the evidence tier per mode.

2. Derive the rule set from the literature. For each dimension in section 3 of the record, write
   the rules the skill will apply as short, checkable statements, each with its citation from
   section 5. Split them into: mechanical (a script can check), judgment (a model checks against a
   fixed rubric), and platform-dependent (from section 6, one value per platform). Reject any rule
   you cannot cite; do not invent UX rules. Show me the list before writing SKILL.md.

3. Write the skill. SKILL.md holds core execution only: the leading word, the mode dispatch, the
   memory-artifact read, the per-mode procedure with checkable completion criteria, the handoffs,
   and the scope stops. Put per-mode detail in references/ (one file per mode, one platform
   conventions file with the section 6 decisions, one heuristics-and-severity file). Put the label
   drift scanner in scripts/ as a deterministic, read-only Python helper with no network access
   that reports and never edits. Put the UX.md skeleton in templates/. Add agents/openai.yaml,
   plugin.json, marketplace and capabilities entries, the overclock-setup bump, and a CHANGELOG
   entry. Every reference load stub must say what the file contains and what goes wrong without
   it. Audit every line of SKILL.md against the failure modes in skill-authoring-notes.md: no-op
   lines, negation where a positive phrasing works, sediment, premature completion.

4. Write the evidence. Deterministic tests for the scanner (planted drift recall, read-only
   boundary, refusal to write without approval, no network) and for the packaging invariants.
   Live-eval cases under qa/evals/: one per mode on a planted fixture, one control where a
   coherent screen must yield a short "holds up" result with no findings list, one scope stop
   (a visual or a11y request must hand off, not answer), and one trivial one-label question that
   must get a one-line answer. Declare the tier in the eval record. Add a routing battery only if
   the skill is model-invoked. Show me the case list before running anything.

5. Validate and hand off. Run the full suite from AGENTS.md and claude plugin validate. Write the
   strategy.md ledger entry. Do not commit. End with: what was built, what the evals showed
   (actual output, including failures), what remains unverified, and the exact commands I should
   run to try each mode on one of my apps.

Rules for the whole session: the skill never applies codebase-wide label edits without my
approval of the proposal table, never commits, never fetches guidelines at run time, and never
states a platform convention without citing the conventions reference. If a step needs
information only I have, ask in one short block and continue on a labelled assumption.
```
