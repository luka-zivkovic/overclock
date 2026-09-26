# Decision rules for flows

## One page or one thing per step

| Choose one screen when | Choose one thing per step when |
|---|---|
| Fewer than ~6 inputs, all independent | Inputs depend on earlier answers |
| Low stakes, easily corrected | High stakes, costly to undo, or legally significant |
| The user does this often and wants speed | The user does this rarely and needs guidance |
| All inputs are known to the user up front | Some inputs require looking something up |

GOV.UK's default is one thing per page for public services; product apps used daily by experts
lean to one screen. A review step is the middle ground: short steps, then one page to check.

## Defaults, derivation, deferral

- Default anything with a most-common value and make it visible and changeable.
- Derive anything the system can compute (timezone, currency, name from email) and show it.
- Defer anything not required to reach the success condition to the detail page or a later
  prompt. Ask at the moment it is needed, with the reason.
- Never default a consequential choice silently (visibility public, recurring billing, sharing).

## Validation timing

- Text inputs: validate on submit, or on blur once the user has left the field; never on each
  keystroke.
- Format-constrained inputs (dates, codes): constrain by the control (picker, mask) before
  validating by message.
- Show the error next to the field and, for forms with several fields, a summary at the top with
  focus moved to it. Keep every value the user entered.
- Positive confirmation (a check mark) only where the user is likely to be unsure the value is
  accepted (usernames, codes).

## Confirmation, undo, or nothing

| Action | Choose |
|---|---|
| Reversible within the product (archive, soft delete, move) | Immediate, plus Undo (toast or in place); no confirmation |
| Irreversible, non-routine (delete permanently, send to many, charge) | Confirmation naming the object and count, one line of consequence, a specific primary verb, Cancel |
| Irreversible and severe (delete an account or a workspace, revoke all access) | Type-to-confirm or a second factor |
| Routine and low-cost (mark read, toggle a filter) | Nothing; make it reversible instead |

A confirmation asked on every routine action is soon clicked through and stops protecting the
one time it matters (NN/g confirmation dialogs; slips versus mistakes).

## Back, Cancel, Close, and unsaved changes

- Back returns one step and keeps everything entered.
- Cancel abandons the task; guard it with an "Discard changes?" prompt only when there are
  changes, with the primary named for the outcome (Discard) and the safe option (Keep editing).
- Close dismisses something with nothing pending; it never needs a guard.
- Browser Back on a wizard step goes to the previous step, not out of the flow.

## Feedback timing

- Under 0.1 s: no indicator needed. 0.1 to 1 s: a subtle indicator on the control. Over 1 s:
  a visible loading state, the triggering button disabled with a progress label ("Saving…").
  Over 10 s: progress with an estimate and a way to leave and come back.
- Every completed action produces a visible change where the user is looking: the new row, the
  saved state, the banner. A toast alone is weak because it can be missed; pair it with an
  in-place change.

## Progress indication

Three or more steps: show step context (Step 2 of 4, or a labelled progress bar) and let the user
see what is ahead. Steps completed are revisitable from the review step.

## Landing after completion

- Created something: its detail page, or the list with it highlighted, whichever the user acts on
  next.
- Changed something: where they were, with the change visible and confirmed.
- Committed something (order, payment, send): a confirmation page with reference, what happens
  next, and the next action; never the empty form again.
- First item ever: the destination's populated state, with a one-line orientation if the area is
  new to them.

## In shadcn apps

| Decision | Component and wiring |
|---|---|
| Irreversible confirmation | `AlertDialog`. The title asks the question with the object named. `AlertDialogAction` carries the specific verb, styled with `buttonVariants({ variant: "destructive" })` when it destroys. `AlertDialogCancel` reads "Cancel". |
| Reversible action | Act immediately, then show a `sonner` toast with an Undo action: `toast("Project archived", { action: { label: "Undo", onClick: restore } })`. Also change the page in place, for example by removing the row. |
| Short create or edit that keeps context | `Dialog` on desktop. Side-by-side editing uses `Sheet`. On phones, use `Drawer` or a full page. |
| Validation timing | react-hook-form with zod. The default `mode: "onSubmit"` with `reValidateMode: "onChange"` matches the rules above: errors appear on submit and clear as the user fixes them. Use `mode: "onTouched"` for long forms. Never validate on every keystroke before the first submit. |
| Error summary | On submit failure, render the errors from `form.formState.errors` in an `Alert` above the form, each linking to its field. Move focus with `form.setFocus`. `FormMessage` shows the same words inline. |
| Progress on the trigger | While `form.formState.isSubmitting` is true, disable the button and show a `Spinner` with "Saving…". |
| Completion | Land where the flow says (`patterns.md`) and show the change in place. A toast alone is not the confirmation. |

Sources: NN/g (confirmation dialogs, slips, user mistakes, user control and freedom, Cancel vs
Close, response-time limits, progress indicators, errors in forms), GOV.UK (structuring forms,
question pages, error summary), Wroblewski, Laws of UX (Tesler, Doherty, Zeigarnik); shadcn/ui
documentation (AlertDialog, Dialog, Sheet, Drawer, Form, Sonner, Spinner); react-hook-form
`useForm` documentation (mode, reValidateMode, setFocus).
