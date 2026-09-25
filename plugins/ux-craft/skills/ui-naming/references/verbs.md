# Canonical verb vocabulary

Adapted from IBM Carbon's action-label table and Apple, Material, and Microsoft guidance. The
point is not these exact choices but that each verb has one meaning across the app; record the
chosen table in `UX.md` and treat deviations as drift.

| Verb | Use for | Do not use for | Pair |
|---|---|---|---|
| **Create** | Making a new object from nothing (Create project) | Attaching an existing object | Delete |
| **Add** | Attaching an existing object to a container (Add member to team) | Creating from nothing | Remove |
| **New** | Only as a button label prefix on list pages ("New project") when the design system uses it; otherwise Create | Verbs in sentences | — |
| **Delete** | Permanently destroying an object | Detaching from a container | Create |
| **Remove** | Detaching from a container; the object still exists elsewhere | Permanent destruction | Add |
| **Archive** | Hiding from active views, recoverable | Deletion | Restore / Unarchive |
| **Save** | Persisting changes the user made | Applying a filter or a temporary view | Cancel / Discard |
| **Apply** | Putting a selection or filter into effect without persisting a record | Persisting edits | Reset / Clear |
| **Update** | Only when the system updates something (Update available); avoid as a button verb for Save | Saving edits | — |
| **Edit** | Opening something for changes | The act of saving | Save |
| **Rename** | Changing only the name | General edits | — |
| **Duplicate** | Making a copy inside the product | Copying to clipboard | — |
| **Copy** | Copying to the clipboard (Copy link) | Duplicating an object | Paste |
| **Move** | Changing the container or position | Copying | — |
| **Send** | Dispatching a message, invitation, or request | Saving a draft | — |
| **Invite** | Sending an invitation to a person | Adding an existing member | — |
| **Share** | Granting access or producing a link | Sending a message | Unshare / Revoke |
| **Export** / **Import** | Moving data out of or into the product | Download of a file already there | — |
| **Download** / **Upload** | Transferring a file | Export of structured data | — |
| **Enable** / **Disable** | Turning a feature on or off (switches use the state, not the verb) | Show/Hide | — |
| **Show** / **Hide** | Visibility in the current view | Enabling features | — |
| **Continue** | Advancing a wizard step that commits nothing | Any committing action | Back |
| **Cancel** | Abandoning a task with changes | Dismissing with nothing pending | — |
| **Close** | Dismissing with nothing pending | Abandoning changes | — |
| **Discard** | Throwing away unsaved changes (in the guard dialog) | Deleting saved objects | Keep editing |
| **Sign in** / **Sign out** | Authentication (pick sign in or log in once, app-wide) | — | — |
| **Sign up** | Creating an account (or Create account) | — | — |
| **Retry** | Re-running a failed action | Refreshing a view | — |
| **Refresh** | Reloading a view | Re-running an action | — |
| **Reset** | Returning settings to defaults | Clearing a form field | — |
| **Clear** | Emptying a field, selection, or filters | Resetting settings | — |

Rules:

- Switches and checkboxes are labelled with the state or thing (Notifications, Dark mode), not
  Enable dark mode; the control shows on/off.
- Confirmations repeat the same verb as the button that opened them.
- When the product's users have their own word (Publish, Book, Ship), use it consistently and
  add it to this table in `UX.md`.

Sources: IBM Carbon, Action labels; Apple HIG, Writing and Buttons; Material 3, UX writing best
practices; Microsoft Writing Style Guide (word list); Shopify Polaris, Actionable language.
