# Label rules by element

Each rule names its source. Where sources disagree, the rule states the default and where to
record the alternative in `UX.md`.

## Page titles and navigation labels

- Name the destination in the user's vocabulary, by task or topic: Orders, Members, Billing.
  Never by format (Videos, Documents) or internal name (Entities, Admin2). (NN/g: category
  names, format-based navigation)
- The page title equals the navigation label that led to it. A user who clicked "Members" and
  lands on "Team management" wonders whether they arrived. (NN/g: consistency and standards)
- Titles of object pages are the object's name, with the type in the breadcrumb, not "View
  project: Atlas".
- Group labels in settings name the user's goal: Notifications, Security, not "Preferences 2".

## Buttons and actions

- Verb plus object: Save changes, Delete project, Invite people, Export CSV. The object may be
  dropped only when the context makes it unambiguous (a modal titled "Invite people" may say
  Send invitations, and its primary can be "Invite"). (Apple HIG Alerts; Microsoft dialog
  guide; Shopify Polaris; Vercel Web Interface Guidelines)
- Never OK, Yes, No, Submit, Continue, or Done on a button that commits something. Reserve
  Continue for wizard steps that only advance; the final step names the outcome (Place order,
  Create workspace). (Apple HIG; Microsoft; GOV.UK)
- The negative action in a dialog is Cancel. Close only when nothing is pending. Back only when
  it returns a step keeping data. (NN/g: Cancel vs Close)
- A destructive primary names the destruction: Delete 3 files, Revoke access, not Confirm.
- One verb vocabulary across the app: see `verbs.md`. Same action, same verb, everywhere.
- Loading state on the same button: the verb in progress with an ellipsis (Saving…, Sending…).
  An action that opens a further step ends with an ellipsis (Rename…, Export…). (Apple HIG;
  Vercel guidelines)
- No trailing period on a button. Sentence case unless `UX.md` records title case.

## Links

- Say where the link goes or what it does, in the words the destination uses: "Billing
  settings", "Download the report". A link's text should make sense read alone (screen readers
  list links out of context). (NN/g: better link labels, "learn more" links)
- Never "Click here", "Here", "More", "Learn more" alone. If a learn-more link is unavoidable,
  attach the topic: "Learn more about roles".

## Field labels, help, and placeholders

- Label names the value, two or three words, above the field: Email address, Due date, Project
  name. Not a question, not an instruction ("Enter your email"). (Wroblewski; NN/g form
  usability)
- Help text answers what format or why, below the label or field: "We'll send invoices here."
- Placeholders never carry required information; they are hints of format at most ("name@company.com")
  and disappear on input. (NN/g: placeholders in form fields are harmful; GOV.UK)
- Required versus optional: mark whichever is the minority, with the same word everywhere,
  recorded in `UX.md`. (NN/g; GOV.UK differ on the convention, agree on consistency)
- Units and formats live in the label or help text, not only in the placeholder.

## Section headings and group labels

- Noun phrases that name the content: Payment method, Recent activity. Not sentences.
- Front-load the distinguishing word; users read the first two words when scanning. (NN/g:
  F-shaped pattern)

## Empty states

- One line on what this area holds, one line on why it is empty now (never used vs no matches),
  and one primary action named like any other button (Create your first project, Clear filters).
  No feature tour. (NN/g: empty states)

## Confirmation dialogs

- Title asks the question with the object named: "Delete project Atlas?" Body: one line of
  consequence ("This removes its 14 documents. This can't be undone."). Buttons: Cancel, then
  the specific destructive verb. (Apple HIG Alerts; NN/g confirmation dialogs)

## Toasts and success messages

- State what happened, past tense, with the object: "Invitation sent to ana@example.com",
  "Project deleted". Offer Undo when the action is reversible.
- No exclamation marks, no "Success!" without saying what succeeded.

## Menu items

- Verbs for actions (Rename, Duplicate, Delete), nouns for destinations (Settings, Help).
  Group by kind with separators; destructive items last, separated.

## Tooltips and icon-only buttons

- Icon-only controls always carry a text name (tooltip plus accessible name) equal to the label
  they would have as a text button. (WCAG; Apple HIG; Material)

## Terminology

- One term per concept, recorded in the glossary with its rejected synonyms. Common collisions:
  delete/remove/trash, save/apply/update, add/create/new, edit/modify/change, cancel/close,
  sign in/log in, sign up/register, settings/preferences/options, workspace/team/organization,
  member/user/person. (Yifrah; Podmajersky; IBM Carbon action labels)
- Prefer the word the user says, not the industry term, unless the users are the industry.
- Avoid abbreviations users would not say aloud; no "e.g.", "etc.", "i.e." in interface text.
  (Material 3 writing; Microsoft style guide)

Sources: Apple Human Interface Guidelines (Alerts, Buttons, Writing); Material 3 UX writing best
practices; Microsoft Writing Style Guide and Win32 dialog guidance; Shopify Polaris content;
Atlassian content guidelines; IBM Carbon action labels; Vercel Web Interface Guidelines; NN/g
(link labels, learn-more links, category names, placeholders, empty states, confirmation
dialogs, Cancel vs Close, F-shaped pattern, consistency); Wroblewski, Web Form Design; Yifrah,
Microcopy; Podmajersky, Strategic Writing for UX.
