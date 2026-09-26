# Reference flow shapes

Start from the shape users already know for the task, then remove what this product does not
need. Each shape lists its steps, the decisions that usually matter, and the trap.

## Create an object

Entry: primary action on the list page, or the list's empty state.
Steps: (1) form with the required fields, defaults prefilled; optional fields collapsed or
deferred to the detail page. (2) Land on the new object's detail page, or the list with the new
row highlighted, with an in-place success confirmation.
Decision: create-then-configure (short form, then edit on the detail page) beats one long form
whenever the object is useful before it is complete.
Trap: asking for everything up front, including things the user does not know yet.

## Edit an object

Entry: Edit action on the detail page, or inline edit on the field.
Steps: (1) edit in place or on an edit page prefilled with current values; (2) Save returns to
the detail with a saved confirmation.
Decision: inline edit for one field at a time; a page for many fields; auto-save only when every
change is safe and individually reversible.
Trap: a Cancel that does not restore the previous values; a Save that reloads the page silently.

## Delete an object

Entry: Delete in the detail page's danger zone or a row overflow menu, never beside the
primary action.
Steps: reversible (soft delete, trash): delete immediately, show a toast with Undo, purge later.
Irreversible: a confirmation naming the object ("Delete project Atlas?"), consequences in one
line, a specific primary (Delete project) and Cancel. For high-stakes deletions, type-to-confirm.
Landing: the list, with a confirmation that the object is gone.
Trap: confirmation on routine deletions, which trains click-through.

## Invite a person

Entry: Invite action on the members page, or the members empty state.
Steps: (1) email or identifier plus role, with the most common role defaulted; multiple entries
allowed. (2) Send. (3) Land on the members list with the pending invitations visible and
resendable; the invitee's path (email, accept, land in the workspace) is a second flow.
Decision: role explanation inline; do not send the user to docs to learn what Editor means.
Trap: no visibility of pending state after sending.

## Sign up and sign in

Sign up: ask only for what is needed to create the account (email, password or magic link,
maybe name); everything else after first login. Show password rules before the first error.
Verify email without blocking the first session when the product allows it.
Sign in: one screen, email and password or a passwordless option, Forgot password on the
screen, errors that do not reveal whether the email exists. Land where the user was going
(deep link preserved), else the home page.
Trap: a signup that asks for company size, role, and use case before the product has shown any
value.

## Onboarding and first run

Prefer contextual help and empty states with the first task over a tour. If a setup is truly
required (connect a source, create a first project), make it a short wizard with progress, each
step skippable when it can be, and land on the populated state it produced. Any tour is
dismissable and remembers dismissal.
Trap: a tour of features the user has not needed yet, forgotten by the time they do.

## Checkout, wizard, and other multi-step commits

Steps: one thing per step when steps are dependent or high stakes: (1) what, (2) who or where,
(3) how to pay or confirm, (4) review with edit links, (5) commit with a primary that names the
outcome (Place order), (6) land on a confirmation page with the reference, what happens next,
and the next action.
Rules: progress indicator; Back keeps data; the review step is where the user checks, so earlier
steps do not need their own confirmations; the commit button is disabled and shows progress
while the request runs, then the confirmation page replaces the wizard.
Trap: a Finish or Submit button; validation at step 1 for something only known at step 3.

## Search, filter, and browse

Steps: search or filter controls on the list; results update on submit (or live for cheap
queries) with a visible count; active filters are shown as removable chips; a no-results state
offers clearing filters; the result set is a URL so it can be shared and returned to.
Trap: filters that reset on Back; no way to see which filters are active.

## Bulk action

Steps: select items (checkboxes, select-all with a clear count), the toolbar shows the actions
that apply to the selection, the action runs with progress for large sets, the result reports
successes and failures separately, undo where reversible.
Trap: a select-all that silently selects only the current page, or one that includes items the
user cannot see.

## Import

Steps: (1) choose a source or file, (2) map fields with sensible defaults, (3) preview with the
errors found and what will be skipped, (4) import with progress and the ability to leave, (5)
land on the list with a summary (imported, skipped, failed) and a way to fix failures.
Trap: an all-or-nothing import that fails on row 400 with no report.

## Settings change

Steps: change the control; either per-section Save with an unsaved-changes indicator, or
auto-save with a per-row "Saved" state. Dangerous settings (visibility, billing, deletion) get
their own confirmation. One save model per app, recorded in `UX.md`.
Trap: mixing auto-save and explicit Save on one page.

## Permission or eligibility gate

Check as early as the flow honestly can and show the gate before the user enters data. When the
gate fails mid-flow, keep the entered data and say what unlocks it.

Sources: GOV.UK Service Manual (form structure, question pages), NN/g (onboarding tutorials,
mobile onboarding, confirmation dialogs, user control and freedom, slips and mistakes, progress
indicators), Wroblewski Web Form Design, Krug, Laws of UX (Tesler, Zeigarnik), Apple HIG and
Material 3 pattern guidance.
