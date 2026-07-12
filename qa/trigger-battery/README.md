# Routing batteries

Routing batteries measure whether Claude selects a skill for the prompts that need it and stays
silent for prompts that do not. Each case runs in a fresh temporary project with the real plugin
loaded. Optional `fixture_files` and `fixture_git` fields make referenced code inspectable instead
of asking the router to act on imaginary files.

## Run one battery

```sh
python3 qa/trigger_battery.py qa/trigger-battery/critical-thinking.json
```

The default is **route-only**: as soon as a positive case emits the target `Skill` tool call, the
harness records the route and stops that process tree. Negative cases run until normal completion,
and every case has a 180-second timeout. This keeps routing measurement separate from the much
slower behavioral suites under `qa/evals/`.

Use repeated samples when tuning a description or auditing stochastic routing:

```sh
python3 qa/trigger_battery.py qa/trigger-battery/test-discipline.json --samples 3
```

Use `--full-session` only when downstream cost/turn metrics matter. Contract-file detectors always
run to completion because their evidence does not exist at route time.

## Quality gates

A battery may define minimum `accuracy`, `precision`, `recall`, and `specificity` under a
`thresholds` object. CLI flags such as `--min-precision 0.9` override the file for one run. Missing
a configured threshold exits non-zero; timeouts and CLI failures are infrastructure errors and are
never scored as silence.

- **Precision** answers: when the skill fired, how often was it wanted?
- **Recall** answers: of the prompts that needed the skill, how many routed?
- **Specificity** answers: of the prompts that should stay quiet, how many did?

Results, including the confusion counts and run configuration, are written to
`qa/_work/trigger-battery/<skill>.results.json`.
