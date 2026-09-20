# Choosing a discriminating scenario

Prefer the repository's existing runner and package materialization. When no
runner exists, deliver a concrete scenario specification and call out the missing
adapter instead of claiming the output is executable.

For each case, identify the fixture, ordered user turns, observation point,
expected behavior, a plausible broken control and a matched benign control.
Use the target contract as the oracle source. Do not add requirements merely
because the author prefers a particular answer.

Useful signals include a confined file diff, a helper's exit status, a native
session ID, a recorded tool invocation, or the request log of a fake service.
Whether an explanation is helpful or properly interprets a decision usually
requires a fixed rubric and an independent judge. Counting words does not turn
such a judgment into objective evidence.

A state-changing tool attempt and a completed mutation are different findings.
Inspect both tool events and resulting files. A final apology cannot erase an
earlier forbidden write. A read-only control should also contain useful permitted
work, so refusal to do anything cannot pass.

When comparing variants, hold task inputs, runner, permissions and scoring fixed.
Separate development examples, selection examples and a sealed holdout. Do not
rewrite expectations after seeing the candidate's answer without recording that
the case has become development data.

LangWatch Scenario is an optional conversation driver. Use it only when branching,
generated user turns or intermediate checks add something the native runner lacks.
Inspect the available version and adapter first. Keep the native coding agent,
skill installation and sandbox underneath it; return tool events as well as
prose. Map one scenario thread to one native session. Disable evaluated-agent
response caching across skill revisions. Script acceptance cases; treat generated
conversations as exploration until reviewed and frozen. Missing Scenario is not
a reason to stop authoring cases supported by the existing runner.
