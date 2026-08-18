# Routing batteries

Routing batteries measure whether Claude selects a skill for the prompts that need it and stays
silent for prompts that do not. Each case runs in a fresh temporary project with a disposable
installation whose boundary is explicit. Optional `fixture_files` and `fixture_git` fields make
referenced code inspectable instead of asking the router to act on imaginary files.

## Run one battery

```sh
python3 qa/trigger_battery.py qa/trigger-battery/critical-thinking.json
```

Every committed battery declares an `install_modes` matrix:

- `skill` synthesizes a minimal plugin containing only the target skill directory and a manifest
  derived from that skill's own description. It carries no owning-plugin hooks, sibling skills, or
  group description.
- `plugin` loads the complete owning plugin and therefore measures sibling and hook effects.
- `stack` loads the owning plugin plus every distribution named in `plugins`.

The command above runs every declared mode as a distinct battery. Select one matrix cell during
iteration with `--install-mode skill`, `--install-mode plugin`, or `--install-mode stack`.
Artifacts are mode-qualified, so separate cells cannot overwrite one another.

Live batteries require a sandbox-capable Claude Code CLI plus an explicit
`ANTHROPIC_API_KEY` or `ANTHROPIC_AUTH_TOKEN`. The harness ignores host OAuth and keychain state:
it moves the supplied credential into an owner-only temporary file read through `apiKeyHelper`,
starts Claude with an empty environment and isolated home/config/temp directories, disables
network and real `gh` access, and denies the source repository. If fail-closed sandboxing is
unavailable, the battery stops as an infrastructure failure.

The harness does not use Claude Code's `--bare` flag because bare mode exposes only the core
Bash/Read/Edit registry and therefore cannot measure autonomous `Skill` calls. Discovery remains
isolated by the temporary home/config, empty setting sources, fresh fixture outside the repository,
strict MCP configuration, explicit disposable plugin directories, and environment-level disabling
of all `CLAUDE.md` and auto-memory loading. Every row mechanically requires the initialized auth
source to be the private `apiKeyHelper`.

The default is **route-only**: as soon as a positive case emits the target `Skill` tool call, the
harness records the route and stops that process tree. Negative cases run until normal completion,
and every case has a 180-second timeout. This keeps routing measurement separate from the much
slower behavioral suites under `qa/evals/`.

Routing uses three independent samples by default. Override that count when tuning a description
or doing a larger stochastic audit:

```sh
python3 qa/trigger_battery.py qa/trigger-battery/test-discipline.json --samples 3
```

Use `--full-session` only when downstream cost/turn metrics matter. Contract-file detectors always
run to completion because their evidence does not exist at route time.

To test installed-together behavior, set `plugins` to the plugin names that should be loaded
beside the target and include `stack` in `install_modes`. A `forbidden_skills` list turns
selection of any named sibling during a positive prompt into a routing failure. Those cases run
to completion so the harness can observe every selection:

```json
{
  "skill": "project-vocabulary",
  "install_modes": ["skill", "stack"],
  "plugins": ["project-vocabulary", "session-memory"],
  "forbidden_skills": ["lessons-learned"]
}
```

Prompt strings remain supported. In a composed battery, each `should_not` prompt is an object with
an explicit routing-ownership contract:

```json
{
  "prompt": "Independently inspect ./spec/openapi.yaml.",
  "allowed_skills": ["independent-research"],
  "forbidden_skills": ["groundwork"]
}
```

`allowed_skills` is closed-world: selecting any skill not listed fails the row; an empty list
requires no skill route at all. `forbidden_skills` is an additional deny list. A row passes only
when the target fires or stays silent as expected and every observed `Skill` selection satisfies
both ownership lists. This lets a hybrid negative permit its intentional sibling while still
catching unrelated sibling pollution. Top-level `forbidden_skills` remains a shorthand for
positive ownership controls.

## Quality gates

A battery may define minimum `accuracy`, `precision`, `recall`, and `specificity` under a
`thresholds` object. CLI flags such as `--min-precision 0.9` override the file for one run. Missing
a configured threshold exits non-zero; timeouts and CLI failures are infrastructure errors and are
never scored as silence.

- **Precision** answers: when the skill fired, how often was it wanted?
- **Recall** answers: of the prompts that needed the skill, how many routed?
- **Specificity** answers: of the prompts that should stay quiet, how many did?

Results, including the confusion counts and run configuration, are written to
`qa/_work/trigger-battery/<plugin>-<skill>-<install-mode>.results.json`, so independently
installable distributions that share a skill name never overwrite one another.

Behavioral suites under `qa/evals/` use the same `install_modes` and per-case override. Running
`qa/run_evals.sh plugin/skill` executes the committed matrix; set
`EVAL_INSTALL_MODE=skill|plugin|stack` to select one cell. Paired value runs preserve the selected
mode in both artifact names and source-bound provenance. A case-level `install_modes` replaces the
suite matrix when its expectations intrinsically require a sibling or external plugin.
