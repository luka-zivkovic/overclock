# Local evaluation setup intake — 2026-09-07

Evidence tier: **subjective**. This change has qualitative review and mechanical
validation, with no measured behavioral gain claimed.

## Change and coverage

The setup workflow now establishes the user's question, coding agent, example
scope, and requested phase before setup. It reuses supplied choices, allows
inspection without a judge, and distinguishes local storage from external
model processing. Completion follows the chosen goal; agreement on a few
development examples is not evidence of evaluator accuracy.

The behavioral suite retains both `skill` and `plugin` installation modes.
Three cases cover missing goals, a supplied inspection-only preflight, and a
production-log request based on the mistaken assumption that hosted judging
keeps data local. Existing cases cover import fidelity, judging costs, and the
production-deployment boundary. The full-stack setup case now supplies its
goal and example source. All seven fixture directories are generated.

The skill description and invocation policy are unchanged. This is an
execution change, not a routing expansion; the existing positive and negative
routing controls remain applicable.

## Independent forward checks

Two fresh agents received realistic requests and the relevant skill context,
without this review, the expected answers, or the authoring conversation.
These were scoped, read-only spot checks rather than runs of the live harness.

- **Target skill alone, unspecified goal:** the response asked what the user
  wanted to understand, offered concrete starting points and a custom question,
  and suggested a synthetic example. It did not install anything or read logs.
- **Owning plugin context, supplied Codex/synthetic/inspection-only preflight:**
  the response preserved those choices, checked prerequisites without mutation,
  and outlined an Ironside-only inspection. It reported Docker and restricted
  system checks as unverified rather than claiming setup was complete. It did
  not require Coeval or a judge, or inspect existing session contents.

Both responses were consistent with the intended intake and scope behavior.
They do not establish reliability across tasks, routing accuracy, or an
improvement over the previous version.

## Mechanical validation and limits

- All 18 shipped skill directories passed validation and the skill audit.
- Shared-file, documentation-claim, capability-catalog, and version checks passed.
- All 367 local unit tests passed. Process-isolation tests needed an execution
  environment that permits process inspection; the first sandboxed run could
  not inspect detached fixture processes.
- The skill-creator validator and Claude marketplace/plugin validators passed.
- Publication metadata is synchronized for eval-stack 0.2.1 and
  overclock-setup 0.1.20; the README declares 123 live cases.

The committed live cases were not executed: the isolated harness requires
`ANTHROPIC_API_KEY` or `ANTHROPIC_AUTH_TOKEN`, and neither was available. Host
OAuth/keychain credentials were not accessed. No live stack was installed, no
real traces were captured, and no paid judge call was made. The forward checks
above do not substitute for the missing live-suite results.
