# Review Contract Gaps — design selection (2026-08-17)

## Verdict

Select the Claude-seeded `audit-consumer-contracts` boundary for forward evaluation, after
cherry-picking Codex's explicit producer/consumer contract direction and stricter evidence ledger.
Keep both candidates unpublished. No automatic-review lift claim exists yet.

## Independent work

- Codex created `candidates/codex/skills/review-contract-gaps/` before reading a valid Claude result.
  It uses a broad implementation-decision matrix and a deterministic validator for review hashes,
  exact anchors, base contracts, producer/consumer reachability, guards, dispositions, duplicate
  root causes, and coverage counts.
- Claude Code 2.1.233 independently proposed `audit-consumer-contracts` through Agent Bridge consult
  result `cd0fb8076cd2e53e21f1b1460f420f4ee02d617f1eca09929b7451f37a206b16`.
  It replaces the blind risk brief with a narrow implementation-aware surface extractor and external
  contract verification. The proposal is preserved verbatim in `candidates/claude/PROPOSAL.md`.
- A first consultation returned `workspace_changed` because the parent created the Codex candidate
  during the snapshot. Agent Bridge correctly rejected it; none of that response was used.
- Delegate mode was unavailable because the active checkout contains unrelated user work. The parent
  therefore materialized the certified read-only proposal and verified every file locally.

## Comparison

| Property | Codex candidate | Claude candidate | Selected behavior |
| --- | --- | --- | --- |
| Scope | All material implementation decisions | Touched tokens with external base matches | Narrow contract-edge sweep |
| Cheap gate | None | Deterministic surface extractor | Keep, but treat as leads only |
| Contract direction | Explicit producer and consumers | Assumed every match was a consumer | Require producer/consumer classification |
| Review retention | Delta-only with review hash | Delta-only with review hash | Structural append-only retention |
| Admission | Exact anchors, base contract, reachability, guards, coverage | Changed line, external match, head evidence, guards | Combine both; fail closed |
| Main risk | Cost and overlap with general review | Heuristic lexical noise and missed non-lexical contracts | Bound syntax/path surface; validate on fresh cases |

The narrower product boundary wins because it addresses the observed supply-side miss without
creating another complete reviewer. The broad Codex candidate remains useful evidence but would run
model analysis on every invocation and collide more with `review-pr`.

## Deterministic calibration

The original Claude proposal's lexical extractor was implemented literally first. On the two role-
matrix PRs it surfaced common words from tests, docs, changelogs, and repository skill files and
produced hundreds of kilobytes of output. It was rejected at the component level.

The selected extractor now:

- reads production changed lines only;
- extracts bounded string and property contract tokens rather than every identifier;
- excludes hidden, generated, fixture, snapshot, and test paths from external matches;
- ranks matching files by token frequency and returns one representative anchor per file; and
- caps surface, match, and changed-anchor counts.

After the correction, the agent-guardrails calibration surfaced `promptType` with the relevant Agent,
Chain, helper, and `utils/descriptions.ts` paths, which makes the known unreachable-description
contract discoverable without an edge brief. The clean frozen-error calibration still surfaced seven
contract tokens, so this is a prioritizer rather than a proven selective router.

## Evidence status

- Focused deterministic tests: 17/17 pass.
- Both candidate skill directories pass `tools/validate_skill.py`.
- The four registered control repositories materialize cleanly; the extractor surfaces the expected
  `description` and `dataTableId` contracts and returns zero surface for the wording-only control.
- Admission tests enforce exact changed anchors, frozen-review hashes, external endpoint membership,
  producer/consumer direction, duplicate-root-cause rejection, and unsupplied PR/issue-claim rejection.
- A model forward run through Agent Bridge was inconclusive: consult mode exposed only planning/read
  tools, so Claude could not execute Git or the bundled validator. Result
  `b4c9ac22735b696ad57fab5439d78c23db9aa6b6b390326ad99e43f94b92e2b1` is mechanics evidence only
  and is not scored. The repository's provider boundary was not bypassed with an ad-hoc CLI call.

## Next gate

Run the committed behavioral controls in a harness that can execute the bundled read-only helpers,
then use fresh metadata-selected PRs for matched reviewer lift. Park the candidate if it cannot turn
at least one cross-reviewer miss into a confirmed addition with zero losses and full retention.
