# CONCEPTS.md template

Shape reference for a project glossary. Copy only what is needed — lazy creation means the
file starts with its first approved term, not with empty scaffolding. Keep it a glossary and
nothing else: no commands, file paths, class names, secrets, or current configuration values.

## Skeleton

```markdown
# Concepts

## <Term> [<bounded context, only when needed>]
<What it is, behaviorally — one to three sentences. What it is NOT, when that prevents a
real confusion. Nearest term it gets confused with.>
Aliases: <retired synonyms, if any — "formerly 'Team'">

## Flagged ambiguities
- <Term known to be contested or fuzzy, and the open question — honest and unresolved.>
```

## Worked example

```markdown
# Concepts

## Workspace
The billing and permission boundary. Every resource belongs to exactly one Workspace; users
may belong to several. Not the same as a Project (a Workspace contains many Projects).
Aliases: formerly "Team", "Org".

## Cancellation
Ending a subscription at the end of the paid period. Access continues until then. Immediate
loss of access is "revocation", which only compliance actions trigger.

## Account [Billing]
The legal customer responsible for invoices. Not the same as a User, who signs in.

## Account [Identity]
A legacy name for a User in older support material. Use User in new material.

## Flagged ambiguities
- "Member" — sometimes a User in a Workspace, sometimes a per-project membership record.
  Undefined until the permissions rework settles it.
```
