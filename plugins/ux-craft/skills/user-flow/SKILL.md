---
name: user-flow
description: "Design how one user task moves through an application: the entry points, the ordered steps, what each step asks for, validation timing, back and exit paths, whether an action gets a confirmation or an undo, and where the user lands afterwards. Use when the user asks how a flow, journey, process, wizard, onboarding, checkout, signup, invite, import, or multi-step task should work, says 'what should happen after they click', 'how many steps', 'should this be one page or several', or is about to build a feature that spans more than one screen. Do NOT use for the internal structure of a single page (page-structure), for label wording (ui-naming), for styling, for backend or API design, or for a flow the user has already specified and just wants implemented."
argument-hint: "[task, e.g. 'invite a teammate'] [--platform web|ios|android|desktop]"
---

# User flow

Think in **scent**. At every step the user should be able to tell where they are, what this step
wants, and what happens next; a flow loses people where the scent breaks: a step that asks for
something they do not have yet, a submit with no visible outcome, a Back that erases their work.
Design the sequence so the scent never breaks, then hand each screen to page-structure.

This is a design pass. It produces a flow spec; it does not implement, and it does not design
the inside of each screen beyond what the step needs. If the request is outside the description,
answer plainly without this procedure.

## 0. Read what the project already decided

If `UX.md` exists at the project root, read its Platform, Button order, Glossary, and Flows
sections first. A flow already named there is extended, not redesigned, unless the user asks. Use
the glossary's terms for objects and actions throughout the spec.

In a shadcn/ui app (`components.json` or `components/ui/`), specify each decision with the
component that implements it: `AlertDialog`, sonner Undo, `Dialog`, `Sheet`, or `Drawer`, and
react-hook-form plus zod timing. `references/decisions.md` › In shadcn apps holds that mapping,
and skipping it yields specs that name behaviours the component library already fixes.

## 1. Frame the task

Fill five lines from the prompt, asking in one short block for anything missing rather than
guessing silently:

- **Actor and goal:** who, and the outcome in their words ("a workspace admin gets a colleague
  into the workspace with the right access").
- **Trigger and entry points:** where the task starts (a button on which page, a link in an
  email, an empty state, a deep link). Most flows have more than one.
- **Success condition:** the observable end state.
- **Stakes:** reversible or not; cost of an error; frequency (daily routine or once a year).
- **Inputs required:** everything the system truly needs, separated from what it can default,
  derive, or ask later.

## 2. Find the minimal step sequence

Read `references/patterns.md` before sequencing; it holds the reference shapes for the common
tasks (create, edit, delete, invite, signup and sign-in, onboarding, checkout and wizard, search
and filter, bulk action, import, settings change, triage a queue), and starting from the pattern avoids
re-deriving a shape users already know. Then:

- Remove every input the system can default or derive (Tesler: complexity that stays lives with
  the system, not the user). Ask later for anything not needed to reach the success condition.
- Decide the granularity with `references/decisions.md`: one screen for short, low-stakes,
  independent inputs; one thing per step for long, high-stakes, or dependent inputs; a review
  step whenever the outcome is costly to reverse.
- Order steps so each one has what it needs from the previous ones, and so the step most likely
  to end the task (eligibility, payment failure) comes as early as it honestly can.
- Mark branches: where the flow forks on an answer, an error, or a permission.

## 3. Specify each step

For every step, record: the question it asks or the thing it shows; the inputs and their
defaults; validation timing (on submit or on blur, never per keystroke for text); what Back does
(returns one step, keeps data); what exit does (Cancel with an "unsaved changes" guard only when
there are changes); the progress indicator when there are three or more steps; and the five
states (ideal, empty, loading, partial, error) where the step shows data.

## 4. Decide confirmations, undo, and feedback

Apply the rules in `references/decisions.md`: reversible actions get undo, irreversible ones get
a confirmation that names the object and count, routine actions get neither, and every action
over a second long gets visible progress and a visible completion. Write the exact decision per
consequential action in the spec.

## 5. Design the landing

Decide where the user is after the final step and what they see: the created object's detail
page, the list with the new item highlighted, or the place they came from. The landing confirms
success in place (a banner, a highlighted row, a status), names the next likely action, and
handles the empty-versus-populated destination (first item created shows differently from the
tenth).

## 6. Fit the flow into the navigation

Check the entry points against `references/navigation.md`: the flow starts where users look for
it, its screens show location (breadcrumb, step context, or active nav), each screen that should
be shareable has its own URL or route, and the terms in the navigation match the glossary.

## 7. Deliver the flow spec

Return, in this order:

1. The frame (actor and goal, entry points, success condition, stakes).
2. The steps table: step, asks or shows, inputs and defaults, validation, back and exit,
   progress, states.
3. A Mermaid flowchart of steps, branches, and exits.
4. The decisions list: each confirmation, undo, default, and deferral, with its rule.
5. The landing.
6. The screens list to hand to page-structure, each with its archetype.
7. Open questions, in one short block.

Completion check: every required input from step 1 appears in exactly one step; every branch
has an exit; every consequential action has a written confirm-or-undo decision; the landing is
named; no rule is asserted without a reference section behind it. When the user asks you to
build it, implement step by step, keeping the step names as route or component names, and record
the flow under Flows in `UX.md` if that file exists.

## Handoffs

- The inside of each screen: page-structure, with the screens list from step 7.
- Button, step, and error wording: `UX.md` glossary; if silent, plain verb-plus-object
  placeholders and a suggestion to run ui-naming.
- Visual design and accessibility audit: separate passes; name `impeccable` or `frontend-design`
  if available.
