# Harness audit — <date>

<One line: harnesses found with versions, and the project audited (or "user level only").>

| Area | Grade | Why |
| --- | --- | --- |
| Safety | <A–F> | <one line> |
| Coherence | <A–F> | <one line, including confirmed judged findings> |
| Hygiene | <A–F> | <one line> |
| Context | <A–D> | <~N tokens load every session in <harness>> |
| **Overall** | <worst of safety, coherence, hygiene> | |

## Fix first

1. **<severity> · <title>** — `<evidence path>`
   <Why it matters, one sentence.>
   ```diff
   <exact proposed change, or the command to run>
   ```
<!-- At most five items. Nothing here has been applied. -->

## Also noted

<Counts per area for the remaining findings, plus one line for any high item that did not fit.>

## Not checked

<Helper coverage notes, casefile status, and pointers: /doctor for install health and hook latency,
/skill-doctor and /usage for usage and real context cost.>
