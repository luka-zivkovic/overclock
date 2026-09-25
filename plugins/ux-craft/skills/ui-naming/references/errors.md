# Error, warning, and status message rules

## The shape of an error message

1. **What is wrong**, naming the field or the thing, in the label's own words.
2. **What to do** about it, as an instruction.
3. Plain language: no codes as the whole message, no jargon, no blame, no humour.

Templates that satisfy this (GOV.UK error-message grammar):

| Case | Pattern | Example |
|---|---|---|
| Empty required field | "Enter [the thing]" | Enter your email address |
| Wrong format | "[Field] must [format]" | Date of birth must be a real date |
| Out of range | "[Field] must be between X and Y" | Quantity must be between 1 and 99 |
| Wrong choice | "Select [the thing]" | Select a payment method |
| Conflict | "[Thing] is already [state]. [What to do]" | This email is already registered. Sign in instead |
| Action failed | "[Thing] couldn't be [verb]. [What to do]" | Changes couldn't be saved. Check your connection and try again |
| Permission | "You don't have access to [thing]. [Who can help]" | You don't have access to billing. Ask an owner to change your role |

## Words to avoid in errors

please, sorry, oops, invalid, illegal, forbidden, error occurred, something went wrong (alone),
failed to (alone), bad, wrong (without saying what), unexpected, fatal, exception, null,
undefined, and any raw code, stack trace, or HTTP status as the whole message. A code may be
appended for support ("Reference: 4F2A") after a human sentence. (GOV.UK error message; NN/g
error-message guidelines and scoring rubric)

## Placement and behaviour

- Inline, next to the field, in the same words as the summary.
- Forms with several fields: a summary at the top listing each error as a link to its field,
  with focus moved to the summary on submit. (GOV.UK error summary; NN/g reporting errors in
  forms)
- Keep every value the user entered. Never clear a form on error.
- Colour plus an icon or text, never colour alone. (WCAG 1.4.1; NN/g)
- Validate on submit or on blur; never on each keystroke for text fields.
- Page-level failures (a fetch failed) show what failed, what loaded, and Retry.

## Warnings and destructive confirmations

- Warn before, not after: "This removes 14 documents. This can't be undone."
- The confirmation's primary names the destruction (Delete project), the safe action is Cancel.

## Success and status

- Past tense with the object: "Project created", "Invitation sent to ana@example.com".
- Ongoing: the verb in progress on the control (Saving…) and a visible completion.
- Empty results: say what was searched and offer the next move ("No orders match these filters.
  Clear filters").

## Sign-in specific

- Do not reveal whether an email exists: "Email or password is incorrect".
- Say when an account is locked and how long, and how to reset.

Sources: GOV.UK Design System (Error message, Error summary); NN/g (Error-message guidelines,
Error messages scoring rubric, 10 guidelines for reporting errors in forms, visibility of
system status); WCAG 2.2 (1.4.1 Use of colour, 3.3.1 Error identification, 3.3.3 Error
suggestion); Microsoft Writing Style Guide on error messages.
