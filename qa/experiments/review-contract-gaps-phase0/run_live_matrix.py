#!/usr/bin/env python3
"""Run the resumable 2x2 consumer-contract review-composition experiment."""

from __future__ import annotations

import argparse
import concurrent.futures
import dataclasses
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Iterable


ROOT = Path(__file__).resolve().parents[3]
EXPERIMENT = Path(__file__).resolve().parent
CANDIDATE_PLUGIN = (EXPERIMENT / "candidates/claude").resolve()
CANDIDATE_SKILL = CANDIDATE_PLUGIN / "skills/audit-consumer-contracts"
PRKIT_PLUGIN = (
    ROOT / "qa/experiments/pr-reviewer-phase0/candidate/pr-kit"
).resolve()
EXTRACTOR = CANDIDATE_SKILL / "scripts/extract_surface.py"
ADMITTER = CANDIDATE_SKILL / "scripts/admit_findings.py"
AUDIT_SCHEMA = CANDIDATE_SKILL / "references/contract-audit-output-schema.json"
CONTROL_SETUP = EXPERIMENT / "setup_control_case.py"
MODEL = "claude-sonnet-5"
EFFORT = "medium"
READ_ONLY_TOOLS = ",".join(
    [
        "Read",
        "Grep",
        "Glob",
        "Task",
        "TaskOutput",
        "Bash(git status *)",
        "Bash(git diff *)",
        "Bash(git show *)",
        "Bash(git grep *)",
        "Bash(git log *)",
        "Bash(git cat-file *)",
        "Bash(git rev-parse *)",
        "Bash(git merge-base *)",
        "Bash(git ls-tree *)",
        "Bash(git blame *)",
    ]
)
SKILL_TOOLS = "Read,Grep,Glob,Skill,Bash(python3 *)"
DISALLOWED_TOOLS = ",".join(
    [
        "Write",
        "Edit",
        "NotebookEdit",
        "WebFetch",
        "WebSearch",
        "Bash(git push *)",
        "Bash(git fetch *)",
        "Bash(git pull *)",
        "Bash(git checkout *)",
        "Bash(git switch *)",
        "Bash(git reset *)",
        "Bash(git clean *)",
        "Bash(git commit *)",
        "Bash(git merge *)",
        "Bash(git rebase *)",
        "Bash(gh *)",
        "Bash(curl *)",
        "Bash(wget *)",
    ]
)


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def claude_schema(value: Any) -> Any:
    """Translate the committed 2020-12 schema subset for Claude's draft-07 parser."""
    if isinstance(value, list):
        return [claude_schema(item) for item in value]
    if not isinstance(value, dict):
        if isinstance(value, str):
            return value.replace("#/$defs/", "#/definitions/")
        return value
    translated: dict[str, Any] = {}
    for key, item in value.items():
        if key == "$schema":
            continue
        translated["definitions" if key == "$defs" else key] = claude_schema(item)
    return translated


def command(*args: str, cwd: Path | None = None, capture: bool = False, stdin: str | None = None) -> str:
    result = subprocess.run(
        list(args),
        cwd=cwd,
        input=stdin,
        check=False,
        text=True,
        stdout=subprocess.PIPE if capture else None,
        stderr=subprocess.PIPE if capture else None,
    )
    if result.returncode != 0:
        detail = (result.stderr or result.stdout or "").strip()
        raise RuntimeError(f"command failed ({result.returncode}): {' '.join(args)}\n{detail}")
    return (result.stdout or "").strip()


@dataclasses.dataclass(frozen=True)
class Case:
    id: str
    number: int
    url: str
    title: str
    base_sha: str
    head_sha: str
    role: str


@dataclasses.dataclass(frozen=True)
class SessionSpec:
    name: str
    cwd: Path
    prompt: str
    budget: float
    tools: str
    plugins: tuple[Path, ...] = ()
    schema: dict[str, Any] | None = None


class MatrixRunner:
    def __init__(self, run_root: Path, source_repo: Path, workers: int, sample_limit: int) -> None:
        self.run_root = run_root.resolve()
        self.source_repo = source_repo.resolve()
        self.workers = workers
        manifest = load_json(EXPERIMENT / "live-cases.json")
        self.cases = [Case(**case) for case in manifest["cases"]]
        self.planned_samples = int(manifest["samples"])
        if not 1 <= sample_limit <= self.planned_samples:
            raise ValueError(f"sample limit must be between 1 and {self.planned_samples}")
        self.sample_limit = sample_limit
        self.manifest = manifest
        self.audit_schema = load_json(AUDIT_SCHEMA)
        self.judge_schema = load_json(EXPERIMENT / "live-judge-schema.json")
        self.judge_rubric = (EXPERIMENT / "live-judge-rubric.md").read_text(encoding="utf-8")
        self.run_root.mkdir(parents=True, exist_ok=True)
        (self.run_root / "sessions").mkdir(exist_ok=True)

    def case_root(self, case: Case) -> Path:
        return self.run_root / "cases" / case.id

    def repo(self, case: Case) -> Path:
        return self.case_root(case) / "repo"

    def artifact(self, case: Case, *parts: str) -> Path:
        return self.case_root(case).joinpath(*parts)

    def session_dir(self, name: str) -> Path:
        return self.run_root / "sessions" / name.replace("/", "__")

    def plugin_copy(self) -> Path:
        return self.run_root / "plugins" / "review-contract-audit"

    @staticmethod
    def has_commit(repo: Path, sha: str) -> bool:
        result = subprocess.run(
            ["git", "-C", str(repo), "cat-file", "-e", f"{sha}^{{commit}}"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )
        return result.returncode == 0

    def freeze_sources(self) -> None:
        paths: list[Path] = []
        for root in (EXPERIMENT, CANDIDATE_PLUGIN, PRKIT_PLUGIN):
            paths.extend(
                path
                for path in root.rglob("*")
                if path.is_file()
                and "__pycache__" not in path.parts
                and "results" not in path.relative_to(root).parts
            )
        hashes = {
            str(path.relative_to(ROOT)): sha256_file(path)
            for path in sorted(set(paths))
        }
        provenance = {
            "schema_version": 1,
            "created_at_epoch": int(time.time()),
            "model": MODEL,
            "effort": EFFORT,
            "claude_version": command("claude", "--version", capture=True),
            "source_repo": str(self.source_repo),
            "planned_samples": self.planned_samples,
            "source_hashes": hashes,
        }
        destination = self.run_root / "provenance.json"
        if destination.exists():
            previous = load_json(destination)
            if previous["source_hashes"] != hashes or previous["planned_samples"] != self.planned_samples:
                raise RuntimeError("experiment sources changed after the run was frozen")
            return
        write_json(destination, provenance)

    def setup(self) -> None:
        self.freeze_sources()
        plugin = self.plugin_copy()
        if not plugin.exists():
            plugin.parent.mkdir(parents=True, exist_ok=True)
            shutil.copytree(CANDIDATE_PLUGIN, plugin)
        central = self.run_root / "repository"
        if not (central / ".git").exists():
            command("git", "clone", "--shared", "--no-checkout", str(self.source_repo), str(central))
            command("git", "remote", "set-url", "origin", "https://github.com/n8n-io/n8n.git", cwd=central)
        for case in self.cases:
            if not self.has_commit(central, case.head_sha):
                command(
                    "git",
                    "fetch",
                    "--no-tags",
                    "origin",
                    f"refs/pull/{case.number}/head:refs/eval/pr-{case.number}",
                    cwd=central,
                )
            for sha, label in ((case.base_sha, "base"), (case.head_sha, "head")):
                if not self.has_commit(central, sha):
                    raise RuntimeError(f"{case.id}: pinned {label} commit unavailable: {sha}")
            case_root = self.case_root(case)
            case_root.mkdir(parents=True, exist_ok=True)
            repo = self.repo(case)
            if not (repo / ".git").exists():
                command("git", "clone", "--shared", "--no-checkout", str(central), str(repo))
                command("git", "remote", "set-url", "origin", "https://github.com/n8n-io/n8n.git", cwd=repo)
                command("git", "update-ref", "refs/heads/master", case.base_sha, cwd=repo)
                command("git", "update-ref", "refs/remotes/origin/master", case.base_sha, cwd=repo)
                command("git", "checkout", "--detach", case.head_sha, cwd=repo)
            if command("git", "rev-parse", "HEAD", cwd=repo, capture=True) != case.head_sha:
                raise RuntimeError(f"{case.id}: checkout moved from pinned head")
            if command("git", "status", "--short", cwd=repo, capture=True):
                raise RuntimeError(f"{case.id}: checkout is dirty before setup")
            surface_path = self.artifact(case, "surface.json")
            if not surface_path.exists():
                raw = command(
                    sys.executable,
                    str(EXTRACTOR),
                    "--repo",
                    str(repo),
                    "--base",
                    case.base_sha,
                    "--head",
                    case.head_sha,
                    capture=True,
                )
                surface = json.loads(raw)
                if surface.get("base") != case.base_sha or surface.get("head") != case.head_sha:
                    raise RuntimeError(f"{case.id}: extractor endpoints do not match pins")
                write_json(surface_path, surface)
            write_json(self.artifact(case, "case.json"), dataclasses.asdict(case))
        print(f"setup complete: {self.run_root}", flush=True)

    def run_session(self, spec: SessionSpec) -> dict[str, Any]:
        target = self.session_dir(spec.name)
        target.mkdir(parents=True, exist_ok=True)
        accepted = target / "metrics.json"
        if accepted.exists() and load_json(accepted).get("accepted"):
            print(f"skip {spec.name}", flush=True)
            return load_json(accepted)
        number = len(list(target.glob("attempt-*.transcript.jsonl"))) + 1
        stem = target / f"attempt-{number}"
        (target / "prompt.txt").write_text(spec.prompt, encoding="utf-8")
        args = [
            "claude",
            "--print",
            "--verbose",
            "--output-format",
            "stream-json",
            "--model",
            MODEL,
            "--effort",
            EFFORT,
            "--max-budget-usd",
            str(spec.budget),
            "--permission-mode",
            "dontAsk",
            "--no-session-persistence",
            "--strict-mcp-config",
            "--mcp-config",
            '{"mcpServers":{}}',
            "--allowedTools",
            spec.tools,
            "--disallowedTools",
            DISALLOWED_TOOLS,
        ]
        for plugin in spec.plugins:
            args.extend(["--plugin-dir", str(plugin)])
        if spec.schema is not None:
            args.extend(
                ["--json-schema", json.dumps(claude_schema(spec.schema), separators=(",", ":"))]
            )
        args.extend(["--", spec.prompt])
        print(f"start {spec.name}", flush=True)
        started = time.time()
        env = os.environ.copy()
        env["NO_COLOR"] = "1"
        with stem.with_suffix(".transcript.jsonl").open("wb") as stdout, stem.with_suffix(
            ".stderr.log"
        ).open("wb") as stderr:
            process = subprocess.run(args, cwd=spec.cwd, env=env, stdout=stdout, stderr=stderr, check=False)
        transcript = stem.with_suffix(".transcript.jsonl")
        result_event: dict[str, Any] | None = None
        for line in transcript.read_text(encoding="utf-8", errors="replace").splitlines():
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            if event.get("type") == "result":
                result_event = event
        if result_event is None:
            raise RuntimeError(f"{spec.name}: Claude returned no result event")
        success = process.returncode == 0 and not result_event.get("is_error", False)
        metrics = {
            "accepted": success,
            "attempt": number,
            "returncode": process.returncode,
            "elapsed_seconds": round(time.time() - started, 3),
            "total_cost_usd": result_event.get("total_cost_usd", 0),
            "session_id": result_event.get("session_id"),
            "permission_denials": result_event.get("permission_denials", []),
            "num_turns": result_event.get("num_turns"),
            "stop_reason": result_event.get("stop_reason"),
            "model_usage": result_event.get("modelUsage", {}),
        }
        write_json(stem.with_suffix(".metrics.json"), metrics)
        if not success:
            raise RuntimeError(f"{spec.name}: Claude session failed; see {stem}")
        result_text = result_event.get("result") or ""
        (target / "result.txt").write_text(result_text, encoding="utf-8")
        if spec.schema is not None:
            structured = result_event.get("structured_output")
            if structured is None:
                structured = json.loads(result_text)
            write_json(target / "result.json", structured)
        write_json(accepted, metrics)
        print(
            f"done {spec.name} cost={metrics['total_cost_usd']:.4f} "
            f"denials={len(metrics['permission_denials'])}",
            flush=True,
        )
        return metrics

    def run_sessions(self, specs: Iterable[SessionSpec]) -> None:
        pending = list(specs)
        if not pending:
            return
        with concurrent.futures.ThreadPoolExecutor(max_workers=self.workers) as pool:
            futures = {pool.submit(self.run_session, spec): spec for spec in pending}
            while futures:
                done, _ = concurrent.futures.wait(
                    futures, timeout=30, return_when=concurrent.futures.FIRST_COMPLETED
                )
                if not done:
                    print(
                        "heartbeat; running/queued: "
                        + ", ".join(sorted(spec.name for spec in futures.values())),
                        flush=True,
                    )
                    continue
                for future in done:
                    spec = futures.pop(future)
                    try:
                        future.result()
                    except Exception:
                        for other in futures:
                            other.cancel()
                        raise RuntimeError(f"session group failed at {spec.name}")

    def review_name(self, case: Case, reviewer: str, sample: int) -> str:
        return f"{case.id}/{reviewer}/sample-{sample}/base"

    def review_prompt(self, case: Case, reviewer: str) -> str:
        target = (
            f"Review PR #{case.number} ({case.url}) over exact committed range "
            f"{case.base_sha}..{case.head_sha}. Review only that range. Do not read existing PR "
            "reviews, comments, CI discussion, or prior experiment output. Remain read-only: do not "
            "edit, execute project code, fetch, post, commit, or push. Return draft actionable "
            "P0-P2 findings for a human reviewer."
        )
        return f"/code-review {target}" if reviewer == "built-in" else f"/pr-kit:review-pr {target}"

    def reviews(self) -> None:
        self.freeze_sources()
        specs: list[SessionSpec] = []
        for case in self.cases:
            for sample in range(1, self.sample_limit + 1):
                for reviewer in ("built-in", "prkit"):
                    specs.append(
                        SessionSpec(
                            name=self.review_name(case, reviewer, sample),
                            cwd=self.repo(case),
                            prompt=self.review_prompt(case, reviewer),
                            budget=2.25,
                            tools=READ_ONLY_TOOLS if reviewer == "built-in" else SKILL_TOOLS,
                            plugins=() if reviewer == "built-in" else (PRKIT_PLUGIN,),
                        )
                    )
        self.run_sessions(specs)
        for case in self.cases:
            for sample in range(1, self.sample_limit + 1):
                for reviewer in ("built-in", "prkit"):
                    source = self.session_dir(self.review_name(case, reviewer, sample)) / "result.txt"
                    destination = self.artifact(case, reviewer, f"sample-{sample}", "base.md")
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    destination.write_bytes(source.read_bytes())
        self.assert_clean("reviews")
        print("reviews complete", flush=True)

    def audit_name(self, case: Case, reviewer: str, sample: int) -> str:
        return f"{case.id}/{reviewer}/sample-{sample}/audit"

    def audit_prompt(self, case: Case, reviewer: str, sample: int, review: Path) -> str:
        surface = self.artifact(case, "surface.json")
        return f"""/review-contract-audit:audit-consumer-contracts

Audit exact committed range {case.base_sha}..{case.head_sha} as a strict append-only second pass.
The frozen base review is the regular non-audit review at {review}; its SHA-256 is
{sha256_file(review)}. The deterministic surface is frozen at {surface}; its SHA-256 is
{sha256_file(surface)}. Use the frozen surface file for admission and do not replace its
serialization. Do not inspect GitHub comments, reviews, CI discussion, or any experiment output
other than those two supplied artifacts.

Return machine-readable evaluation output matching the skill's bundled contract-audit schema.
Inspect at most ten surfaced entries. Include a decision only for entries actually verified, set
skipped to surfaced minus verified. The parent harness will run admit_findings.py with the frozen
surface and review after this session; do not create temporary payload files or invoke the validator
in-session. The frozen review is only for duplicate suppression; never rewrite, summarize, or embed
it."""

    def empty_audit(self, case: Case, review: Path, surface: dict[str, Any]) -> dict[str, Any]:
        return {
            "schema_version": 1,
            "base": case.base_sha,
            "head": case.head_sha,
            "surface_sha256": sha256_file(self.artifact(case, "surface.json")),
            "base_review_sha256": sha256_file(review),
            "decisions": [],
            "coverage": {
                "surfaced": 0,
                "verified": 0,
                "confirmed": 0,
                "already_covered": 0,
                "defeated": 0,
                "unreachable": 0,
                "unresolved": 0,
                "skipped": 0,
                "blind_spots": [],
            },
        }

    def validate_audit_paths(
        self,
        repo: Path,
        base: str,
        head: str,
        surface: Path,
        review: Path,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        raw = json.dumps(payload, separators=(",", ":"))
        result = subprocess.run(
            [
                sys.executable,
                str(ADMITTER),
                "--repo",
                str(repo),
                "--base",
                base,
                "--head",
                head,
                "--surface-file",
                str(surface),
                "--review",
                str(review),
            ],
            input=raw,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        try:
            output = json.loads(result.stdout)
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"admission helper returned invalid JSON: {result.stdout}") from exc
        if result.returncode not in {0, 2}:
            raise RuntimeError(f"admission helper failed unexpectedly: {result.stderr or result.stdout}")
        return output

    def validate_audit(self, case: Case, review: Path, payload: dict[str, Any]) -> dict[str, Any]:
        return self.validate_audit_paths(
            self.repo(case),
            case.base_sha,
            case.head_sha,
            self.artifact(case, "surface.json"),
            review,
            payload,
        )

    def repair_audit(
        self,
        *,
        name: str,
        cwd: Path,
        base: str,
        head: str,
        surface: Path,
        review: Path,
        payload: dict[str, Any],
        errors: list[str],
    ) -> dict[str, Any]:
        prompt = f"""/review-contract-audit:audit-consumer-contracts

Repair the machine-readable audit payload below so it passes the bundled fail-closed validator for
exact range {base}..{head}, frozen surface {surface}, and frozen review {review}. Change only fields
identified by the validator errors. Copy line_text and changed_line byte-for-byte from the frozen
surface; do not normalize indentation, quote style, or syntax. Do not add a finding, change a
disposition, broaden evidence, create temporary files, or invoke the validator. The parent harness
will validate the repaired payload. Return only the supplied schema.

VALIDATOR ERRORS:
{json.dumps(errors, indent=2)}

REJECTED PAYLOAD:
{json.dumps(payload, indent=2)}
"""
        self.run_session(
            SessionSpec(
                name=name,
                cwd=cwd,
                prompt=prompt,
                budget=0.5,
                tools=SKILL_TOOLS,
                plugins=(self.plugin_copy(),),
                schema=self.audit_schema,
            )
        )
        return load_json(self.session_dir(name) / "result.json")

    @staticmethod
    def render_delta(payload: dict[str, Any]) -> bytes:
        findings = [
            decision["finding"]
            for decision in payload["decisions"]
            if decision["disposition"] == "confirmed-new-finding"
        ]
        if not findings:
            return b""
        lines = ["", "---", "", "## Consumer-contract audit additions", ""]
        for finding in findings:
            lines.extend(
                [
                    f"### [{finding['priority']}] {finding['title']}",
                    "",
                    f"**Location:** `{finding['file']}:{finding['line']}`",
                    "",
                    finding["failure_path"],
                    "",
                    f"**Impact:** {finding['impact']}",
                    "",
                    f"**Suggested comment:** {finding['suggested_comment']}",
                    "",
                ]
            )
        return ("\n".join(lines).rstrip() + "\n").encode("utf-8")

    def audits(self) -> None:
        self.freeze_sources()
        specs: list[SessionSpec] = []
        synthetic: list[tuple[Case, str, int, Path, dict[str, Any]]] = []
        for case in self.cases:
            surface = load_json(self.artifact(case, "surface.json"))
            for sample in range(1, self.sample_limit + 1):
                for reviewer in ("built-in", "prkit"):
                    review = self.artifact(case, reviewer, f"sample-{sample}", "base.md")
                    if surface["surface_count"] == 0:
                        synthetic.append((case, reviewer, sample, review, self.empty_audit(case, review, surface)))
                    else:
                        specs.append(
                            SessionSpec(
                                name=self.audit_name(case, reviewer, sample),
                                cwd=self.repo(case),
                                prompt=self.audit_prompt(case, reviewer, sample, review),
                                budget=1.75,
                                tools=SKILL_TOOLS,
                                plugins=(self.plugin_copy(),),
                                schema=self.audit_schema,
                            )
                        )
        self.run_sessions(specs)
        for case in self.cases:
            for sample in range(1, self.sample_limit + 1):
                for reviewer in ("built-in", "prkit"):
                    review = self.artifact(case, reviewer, f"sample-{sample}", "base.md")
                    surface = load_json(self.artifact(case, "surface.json"))
                    if surface["surface_count"] == 0:
                        payload = self.empty_audit(case, review, surface)
                    else:
                        payload = load_json(self.session_dir(self.audit_name(case, reviewer, sample)) / "result.json")
                    validation = self.validate_audit(case, review, payload)
                    if validation.get("status") != "valid":
                        payload = self.repair_audit(
                            name=self.audit_name(case, reviewer, sample) + "-repair-1",
                            cwd=self.repo(case),
                            base=case.base_sha,
                            head=case.head_sha,
                            surface=self.artifact(case, "surface.json"),
                            review=review,
                            payload=payload,
                            errors=list(validation.get("errors", [])),
                        )
                        validation = self.validate_audit(case, review, payload)
                    if validation.get("status") != "valid":
                        raise RuntimeError(
                            f"{case.id}/{reviewer}/sample-{sample}: audit failed admission after repair: "
                            + json.dumps(validation.get("errors", []))
                        )
                    target = self.artifact(case, reviewer, f"sample-{sample}")
                    write_json(target / "audit.json", payload)
                    write_json(target / "audit-validation.json", validation)
                    base = review.read_bytes()
                    delta = self.render_delta(payload)
                    (target / "audit-delta.md").write_bytes(delta)
                    (target / "augmented.md").write_bytes(base + delta)
                    if not (target / "augmented.md").read_bytes().startswith(base):
                        raise RuntimeError(f"{case.id}/{reviewer}/sample-{sample}: base bytes not retained")
        self.assert_clean("audits")
        print("audits complete", flush=True)

    def control_cases(self) -> None:
        self.freeze_sources()
        controls = load_json(EXPERIMENT / "behavioral-controls.json")["cases"]
        control_root = self.run_root / "controls"
        specs: list[SessionSpec] = []
        metadata: dict[str, tuple[dict[str, Any], Path, Path]] = {}
        for control in controls:
            case_id = control["id"]
            repo = control_root / case_id / "repo"
            meta_path = control_root / case_id / "metadata.json"
            if not meta_path.exists():
                raw = command(sys.executable, str(CONTROL_SETUP), case_id, str(repo), capture=True)
                write_json(meta_path, json.loads(raw))
            meta = load_json(meta_path)
            surface_path = control_root / case_id / "surface.json"
            if not surface_path.exists():
                raw = command(
                    sys.executable,
                    str(EXTRACTOR),
                    "--repo",
                    str(repo),
                    "--base",
                    meta["base"],
                    "--head",
                    meta["head"],
                    capture=True,
                )
                write_json(surface_path, json.loads(raw))
            surface = load_json(surface_path)
            metadata[case_id] = (meta, repo, surface_path)
            if surface["surface_count"]:
                review = Path(meta["review"])
                prompt = f"""/review-contract-audit:audit-consumer-contracts

Audit exact committed range {meta['base']}..{meta['head']} using frozen review {review} and frozen
surface {surface_path}. Their SHA-256 values are {sha256_file(review)} and
{sha256_file(surface_path)}.

USER-SUPPLIED CHANGE CONTEXT:
{control['prompt']}

Return only the machine-readable evaluation payload. The parent harness will validate it with
--surface-file and --review after the session; do not create temporary payload files or invoke the
validator in-session, and never modify the repository."""
                specs.append(
                    SessionSpec(
                        name=f"controls/{case_id}/audit",
                        cwd=repo,
                        prompt=prompt,
                        budget=1.25,
                        tools=SKILL_TOOLS,
                        plugins=(self.plugin_copy(),),
                        schema=self.audit_schema,
                    )
                )
        self.run_sessions(specs)
        outcomes: list[dict[str, Any]] = []
        for control in controls:
            case_id = control["id"]
            meta, repo, surface_path = metadata[case_id]
            surface = load_json(surface_path)
            review = Path(meta["review"])
            case = Case(case_id, 0, "", case_id, meta["base"], meta["head"], control["kind"])
            if surface["surface_count"]:
                payload = load_json(self.session_dir(f"controls/{case_id}/audit") / "result.json")
            else:
                payload = {
                    "schema_version": 1,
                    "base": meta["base"],
                    "head": meta["head"],
                    "surface_sha256": sha256_file(surface_path),
                    "base_review_sha256": sha256_file(review),
                    "decisions": [],
                    "coverage": {
                        "surfaced": 0,
                        "verified": 0,
                        "confirmed": 0,
                        "already_covered": 0,
                        "defeated": 0,
                        "unreachable": 0,
                        "unresolved": 0,
                        "skipped": 0,
                        "blind_spots": [],
                    },
                }
            validation = self.validate_audit_paths(
                repo, meta["base"], meta["head"], surface_path, review, payload
            )
            if validation.get("status") != "valid":
                payload = self.repair_audit(
                    name=f"controls/{case_id}/audit-repair-1",
                    cwd=repo,
                    base=meta["base"],
                    head=meta["head"],
                    surface=surface_path,
                    review=review,
                    payload=payload,
                    errors=list(validation.get("errors", [])),
                )
                validation = self.validate_audit_paths(
                    repo, meta["base"], meta["head"], surface_path, review, payload
                )
            if validation.get("status") != "valid":
                raise RuntimeError(
                    f"control {case_id}: audit failed admission after repair: "
                    + json.dumps(validation.get("errors", []))
                )
            confirmed = validation["admitted_findings"]
            expected = 1 if control["kind"] == "positive" else 0
            outcomes.append(
                {
                    "case_id": case_id,
                    "kind": control["kind"],
                    "surface_count": surface["surface_count"],
                    "confirmed": confirmed,
                    "expected": expected,
                    "passed": confirmed == expected,
                }
            )
            if command("git", "status", "--short", cwd=repo, capture=True):
                raise RuntimeError(f"control {case_id}: repository mutated")
        write_json(self.run_root / "control-results.json", {"schema_version": 1, "outcomes": outcomes})
        if not all(item["passed"] for item in outcomes):
            raise RuntimeError("one or more target-only controls failed")
        print("controls complete", flush=True)

    def judgment_name(self, case: Case, reviewer: str, sample: int) -> str:
        return f"{case.id}/{reviewer}/sample-{sample}/judge"

    def judge(self) -> None:
        self.freeze_sources()
        specs: list[SessionSpec] = []
        keys: dict[tuple[str, str, int], dict[str, str]] = {}
        for case in self.cases:
            for sample in range(1, self.sample_limit + 1):
                for reviewer in ("built-in", "prkit"):
                    root = self.artifact(case, reviewer, f"sample-{sample}")
                    base = (root / "base.md").read_text(encoding="utf-8")
                    augmented = (root / "augmented.md").read_text(encoding="utf-8")
                    if base == augmented:
                        write_json(
                            root / "judgment.json",
                            {
                                "schema_version": 1,
                                "winner": "tie",
                                "arm_winner": "tie",
                                "review_a_findings": [],
                                "review_b_findings": [],
                                "unsupported_a": [],
                                "unsupported_b": [],
                                "reason": "Audit admitted no additions; final bytes equal the base review.",
                                "safety": {
                                    "implementation_leakage": False,
                                    "repository_mutation": False,
                                    "posting_claim": False,
                                },
                            },
                        )
                        continue
                    digest = sha256_bytes(f"{case.id}:{reviewer}:{sample}".encode())
                    audit_label = "A" if int(digest[0], 16) % 2 == 0 else "B"
                    labels = {audit_label: "audit", "B" if audit_label == "A" else "A": "base"}
                    keys[(case.id, reviewer, sample)] = labels
                    review_a = augmented if labels["A"] == "audit" else base
                    review_b = augmented if labels["B"] == "audit" else base
                    prompt = f"""{self.judge_rubric}

Exact range: {case.base_sha}..{case.head_sha}
PR title: {case.title}

REVIEW A:
{review_a}

REVIEW B:
{review_b}
"""
                    specs.append(
                        SessionSpec(
                            name=self.judgment_name(case, reviewer, sample),
                            cwd=self.repo(case),
                            prompt=prompt,
                            budget=1.25,
                            tools=READ_ONLY_TOOLS,
                            schema=self.judge_schema,
                        )
                    )
        self.run_sessions(specs)
        for case in self.cases:
            for sample in range(1, self.sample_limit + 1):
                for reviewer in ("built-in", "prkit"):
                    root = self.artifact(case, reviewer, f"sample-{sample}")
                    if (root / "judgment.json").exists():
                        continue
                    result = load_json(self.session_dir(self.judgment_name(case, reviewer, sample)) / "result.json")
                    labels = keys[(case.id, reviewer, sample)]
                    winner = result["winner"]
                    result["arm_winner"] = "tie" if winner == "tie" else labels[winner]
                    result["blind_labels"] = labels
                    write_json(root / "judgment.json", result)
        self.assert_clean("judge")
        print("judging complete", flush=True)

    def assert_clean(self, phase: str) -> None:
        dirty = {
            case.id: command("git", "status", "--short", cwd=self.repo(case), capture=True)
            for case in self.cases
        }
        dirty = {key: value for key, value in dirty.items() if value}
        if dirty:
            raise RuntimeError(f"repositories mutated after {phase}: {dirty}")

    def summarize(self) -> None:
        self.freeze_sources()
        rows: list[dict[str, Any]] = []
        cost = 0.0
        denials = 0
        for metrics_path in self.run_root.glob("sessions/*/metrics.json"):
            metrics = load_json(metrics_path)
            cost += float(metrics.get("total_cost_usd", 0))
            denials += len(metrics.get("permission_denials", []))
        for case in self.cases:
            for sample in range(1, self.sample_limit + 1):
                for reviewer in ("built-in", "prkit"):
                    root = self.artifact(case, reviewer, f"sample-{sample}")
                    judgment = load_json(root / "judgment.json")
                    validation = load_json(root / "audit-validation.json")
                    base = (root / "base.md").read_bytes()
                    augmented = (root / "augmented.md").read_bytes()
                    rows.append(
                        {
                            "case_id": case.id,
                            "role": case.role,
                            "reviewer": reviewer,
                            "sample": sample,
                            "surface_count": load_json(self.artifact(case, "surface.json"))["surface_count"],
                            "admitted_findings": validation["admitted_findings"],
                            "arm_winner": judgment["arm_winner"],
                            "retained": augmented.startswith(base),
                        }
                    )
        wins = sum(row["arm_winner"] == "audit" for row in rows)
        ties = sum(row["arm_winner"] == "tie" for row in rows)
        losses = sum(row["arm_winner"] == "base" for row in rows)
        win_cases = {row["case_id"] for row in rows if row["arm_winner"] == "audit"}
        win_reviewers = {row["reviewer"] for row in rows if row["arm_winner"] == "audit"}
        negative_ok = all(
            row["admitted_findings"] == 0
            for row in rows
            if row["case_id"] == "frozen-error-prototype"
        )
        complete = len(rows) == len(self.cases) * 2 * self.planned_samples
        promoted = (
            complete
            and losses == 0
            and all(row["retained"] for row in rows)
            and len(win_cases) >= 2
            and win_reviewers == {"built-in", "prkit"}
            and negative_ok
        )
        summary = {
            "schema_version": 1,
            "complete": complete,
            "sample_limit": self.sample_limit,
            "planned_samples": self.planned_samples,
            "rows": rows,
            "aggregate": {
                "wins": wins,
                "ties": ties,
                "losses": losses,
                "distinct_win_cases": sorted(win_cases),
                "win_reviewers": sorted(win_reviewers),
                "negative_control_passed": negative_ok,
                "retention_passed": all(row["retained"] for row in rows),
                "promoted": promoted,
                "accepted_cost_usd": round(cost, 8),
                "permission_denials": denials,
            },
        }
        write_json(self.run_root / "summary.json", summary)
        print(json.dumps(summary["aggregate"], indent=2, sort_keys=True), flush=True)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-root", required=True, type=Path)
    parser.add_argument("--source-repo", required=True, type=Path)
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--sample-limit", type=int, default=3)
    parser.add_argument(
        "phase",
        choices=("setup", "controls", "reviews", "audits", "judge", "summary", "all"),
    )
    args = parser.parse_args()
    try:
        if not 1 <= args.workers <= 8:
            raise ValueError("workers must be between 1 and 8")
        runner = MatrixRunner(args.run_root, args.source_repo, args.workers, args.sample_limit)
        if args.phase in {"setup", "all"}:
            runner.setup()
        if args.phase in {"controls", "all"}:
            runner.control_cases()
        if args.phase in {"reviews", "all"}:
            runner.reviews()
        if args.phase in {"audits", "all"}:
            runner.audits()
        if args.phase in {"judge", "all"}:
            runner.judge()
        if args.phase in {"summary", "all"}:
            runner.summarize()
        return 0
    except (OSError, UnicodeError, ValueError, RuntimeError, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
