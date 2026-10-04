# skill-scout measurement (2026-10-04)

Two questions: does skill-scout find the requests a user really repeats, and what does a run cost?
Evidence tier: `objective` for the helper benchmark (planted ground truth, exact scoring) and
`rubric` for the model-side runs (an independent grader over pre-declared expectations). The live
suite in `qa/evals/skill-scout/` has still not run under `qa/run_evals.sh`; the model-side runs below
are a proxy for it.

## 1. Helper benchmark (no model calls)

`bench.py` writes synthetic Claude Code, Codex, and Pi histories with planted ground truth: five
recurring requests and two recurring corrections, each with three to seven realistic paraphrases,
one request repeated inside a single session only (must not be reported), unique noise requests,
bulky tool output, injected records, headless runs, codex exec rollouts, and subagent transcripts
that carry planted text (must never be counted), a planted token (must never appear), and 61
installed skills. `dense` noise draws subjects from a small vocabulary, so the same subject recurs
with different asks dozens of times (adversarial); `varied` noise is closer to real use.

```text
python3 qa/experiments/skill-scout-bench/bench.py            # dense and varied, 50/200/600 sessions
python3 qa/experiments/skill-scout-bench/bench.py --scales 1000 --noise varied
```

Results with the shipped helper (seed 7):

| Noise | Sessions | History | Helper time | Report tokens | Clusters / topics | Patterns found | Sessions linked | Cluster precision | False positive | Leaks |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---|---|
| dense | 50 | 3.2 MB | 0.14 s | ~3,400 | 9 / 0 | 6/6 | 88% | 67% | no | none |
| dense | 200 | 11.4 MB | 0.50 s | ~6,100 | 12 / 5 | 7/7 | 93% | 67% | no | none |
| dense | 600 | 33.8 MB | 1.96 s | ~6,300 | 12 / 5 | 7/7 | 90% | 58% | no | none |
| varied | 50 | 3.3 MB | 0.13 s | ~2,900 | 7 / 0 | 7/7 | 97% | 100% | no | none |
| varied | 200 | 11.4 MB | 0.45 s | ~6,000 | 12 / 5 | 6/7 | 89% | 58% | no | none |
| varied | 600 | 33.8 MB | 1.70 s | ~5,900 | 12 / 5 | 7/7 | 85% | 75% | no | none |

*Patterns found* counts planted patterns that meet the helper's own thresholds and surface as a
cluster. *Sessions linked* is the share of a pattern's sessions its cluster covers. *Cluster
precision* is the share of returned clusters that are planted patterns; the rest are recurring
subject-plus-condition combinations the model is expected to reject. *False positive* means the
single-session request was reported; *leaks* means contamination inflated a count. No run printed
the planted token. Peak helper memory stayed under 32 MB.

The report is capped (12 clusters, 5 topics, 5 short samples each), so its size, and therefore the
model's input cost, stops growing at about 6,000 tokens regardless of history size.

**What the benchmark changed.** The first version used single-link clustering with a 25-cluster
cap. Same-subject prompts ("fix / explain / refactor the csv importer behind the proxy") chained into
giant clusters that pushed every planted pattern out of the cap: 0/7 at 600 dense sessions, with a
~12,700-token report of which ~4,600 tokens were the installed-skill list. The shipped helper
clusters cohesively, refuses to merge requests whose opening verbs belong to different action
groups, separates `topics` from repeated requests, ranks by sessions weighted by shared specifics,
lists installed skills by name only, and tokenizes redacted text so secret fragments cannot surface
as terms.

**Known limit.** Matching is lexical. Paraphrases that share few words stay apart: in the varied
200-session run the security-review request split into two halves (3 and 2 sessions) whose wording
overlaps at 0.40, below the 0.45 threshold, so it fell below the cut. Expect real recall to be lower
than the planted numbers when users rephrase freely.

## 2. Model-side runs

A fresh agent (claude-opus-5-5, default effort) executed the skill exactly as installed: it read
SKILL.md, followed it, and was limited to the skill's own files and helper. An independent grader
agent, which wrote neither the skill nor the reports, scored each report against pre-declared
expectations and checked every count and quote against the helper JSON. Expectations for the
200-session case were written from the ground truth before that report existed.

| Case | History | Expectations passed | Grader usefulness (1-5) | Wall time |
|---|---|---:|---:|---:|
| Planted (eval case 0 fixture) | 7 sessions, 3 harnesses | 6/6 | 5 | 70 s |
| No recurrence (eval case 1 fixture) | 6 sessions | 3/3 | 5 | 14 s |
| Realistic scale (bench, varied noise) | 200 sessions, 1,312 prompts kept | 9/9 | 4 | 161 s |

All three runs made exactly four tool calls (three reads of the skill's own files, one helper run),
read no transcript and wrote no file. On the planted fixture the agent proposed the release-notes
skill, a trigger fix for the installed pr-description skill (not a duplicate), and the pnpm
correction as an instruction line. At 200 sessions it proposed release notes (skill), changelog plus
version bump (command), the pr-description trigger fix, and both corrections (instruction lines);
it held back the rebase request only because of the five-proposal limit, and rejected all five
noise clusters and all five topics as subjects rather than requests.

Grader notes on the 200-session report, all outside the proposals' counts: one omitted-topic count
off by one, one shared term left out, two unsupported asides (that the bump level varies; that every
project shares the same changelog file), and no advice to install pr-description in Codex and Pi,
where it could not fire.

### Cost per run

Token counts come from the agents' transcripts. Input-side counts are exact; output counts are the
visible report and tool inputs at ~4 characters per token. Hidden reasoning tokens are not recorded
in transcripts, so output cost is a lower bound. Only Opus 5.5 was run; the Sonnet and Haiku columns
reprice the same token counts and say nothing about quality on those models. Prices: Opus 5.5
$4/$20 per MTok, Sonnet 5.5 $2/$10, Haiku 4.5 $1/$5, cache writes 1.25x input, cache reads
$0.20/$0.20/$0.10.

| Case | Context the skill added | Visible output | Inside an existing session: Opus 5.5 / Sonnet 5.5 / Haiku 4.5 | Fresh session: Opus 5.5 |
|---|---:|---:|---|---:|
| No recurrence | 6.8k tokens | ~0.5k | $0.06 / $0.04 / $0.02 | $0.29 |
| Planted, 7 sessions | 9.5k tokens | ~1.5k | $0.11 / $0.07 / $0.04 | $0.34 |
| 200 sessions | 17.2k tokens | ~2.4k | $0.16 / $0.09 / $0.05 | $0.38 |

*Inside an existing session* is what `/skill-scout` costs on top of a conversation whose system
prompt is already cached: the skill files (~2.5k tokens), the helper report (1.7k to 6k tokens),
tool-call overhead, re-reading that context on each follow-up request, and the output. *Fresh
session* adds the ~45k-token Claude Code system prompt and tool definitions written to cache once.

## Measure it on your own history

```text
# Helper only: no model cost.
python3 plugins/skill-scout/skills/skill-scout/scripts/skill_scout.py scan > scout.json
python3 -c "import json; d=json.load(open('scout.json')); c=d['coverage']; print(c['sessions_kept'], 'sessions,', round(c['bytes_read']/1e6, 1), 'MB,', c['elapsed_seconds'], 's,', len(open('scout.json').read())//4, 'report tokens,', len(d['clusters']), 'clusters')"

# Whole skill: load the plugin from this checkout, run it, then check the session's cost.
claude --plugin-dir ./plugins/skill-scout
#   /skill-scout
#   /usage
```

## Follow-ups

- Run `qa/run_evals.sh skill-scout/skill-scout` and the value comparison with real credentials.
- From the grader notes: tell the model to keep asides to what the samples show, and to suggest
  installing a matched skill in the harnesses where the cluster occurred but the skill is absent.
  Re-measure after any such change.
- Measure on Sonnet 5.5 directly; the repriced column is not evidence of quality.
