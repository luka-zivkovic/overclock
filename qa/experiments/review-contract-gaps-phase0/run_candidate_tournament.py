#!/usr/bin/env python3
"""Run the missing broad semantic arm against the frozen live-matrix reviews."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

from run_live_matrix import (
    EXPERIMENT,
    READ_ONLY_TOOLS,
    ROOT,
    Case,
    MatrixRunner,
    SessionSpec,
    load_json,
    sha256_bytes,
    sha256_file,
    write_json,
)


BROAD_PLUGIN = EXPERIMENT / "candidates/codex"
BROAD_SKILL = BROAD_PLUGIN / "skills/review-contract-gaps"
BROAD_SCHEMA = BROAD_SKILL / "references/contract-gap-output-schema.json"
BROAD_VALIDATOR = BROAD_SKILL / "scripts/validate_delta.py"
BROAD_TOOLS = ",".join(
    [
        "Read",
        "Grep",
        "Glob",
        "Skill",
        "Task",
        "TaskOutput",
        "Bash(python3 *)",
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


class TournamentRunner:
    def __init__(
        self,
        run_root: Path,
        matrix_root: Path,
        source_repo: Path,
        workers: int,
    ) -> None:
        self.run_root = run_root.resolve()
        self.matrix_root = matrix_root.resolve()
        self.runner = MatrixRunner(self.run_root, source_repo, workers, sample_limit=1)
        self.schema = load_json(BROAD_SCHEMA)

    def target(self, case: Case, reviewer: str) -> Path:
        return self.runner.artifact(case, reviewer, "sample-1") / "broad"

    def source_review(self, case: Case, reviewer: str) -> Path:
        return self.matrix_root / "cases" / case.id / reviewer / "sample-1" / "base.md"

    def review(self, case: Case, reviewer: str) -> Path:
        return self.runner.artifact(case, reviewer, "sample-1", "base.md")

    def session_name(self, case: Case, reviewer: str, suffix: str = "audit") -> str:
        return f"{case.id}/{reviewer}/sample-1/broad-{suffix}"

    def plugin_copy(self) -> Path:
        return self.run_root / "plugins" / "review-contract-gaps-candidate"

    def setup(self) -> None:
        self.runner.setup()
        plugin = self.plugin_copy()
        if not plugin.exists():
            plugin.parent.mkdir(parents=True, exist_ok=True)
            shutil.copytree(BROAD_PLUGIN, plugin)
        matrix_provenance = self.matrix_root / "provenance.json"
        if not matrix_provenance.is_file():
            raise RuntimeError("frozen matrix provenance is missing")
        reviews: list[dict[str, Any]] = []
        for case in self.runner.cases:
            for reviewer in ("built-in", "prkit"):
                source = self.source_review(case, reviewer)
                if not source.is_file():
                    raise RuntimeError(f"missing frozen review: {source}")
                destination = self.review(case, reviewer)
                destination.parent.mkdir(parents=True, exist_ok=True)
                if destination.exists() and destination.read_bytes() != source.read_bytes():
                    raise RuntimeError(f"copied review drifted: {destination}")
                destination.write_bytes(source.read_bytes())
                reviews.append(
                    {
                        "case_id": case.id,
                        "reviewer": reviewer,
                        "source": str(source),
                        "sha256": sha256_file(source),
                    }
                )
        evidence = {
            "schema_version": 1,
            "matrix_root": str(self.matrix_root),
            "matrix_provenance_sha256": sha256_file(matrix_provenance),
            "candidate_plugin_sha256": self.tree_digest(plugin),
            "reviews": reviews,
        }
        destination = self.run_root / "tournament-provenance.json"
        if destination.exists() and load_json(destination) != evidence:
            raise RuntimeError("tournament provenance changed after setup")
        write_json(destination, evidence)
        self.runner.assert_clean("tournament setup")
        print(f"tournament setup complete: {self.run_root}", flush=True)

    @staticmethod
    def tree_digest(root: Path) -> str:
        digest = hashlib.sha256()
        for path in sorted(item for item in root.rglob("*") if item.is_file()):
            digest.update(path.relative_to(root).as_posix().encode("utf-8"))
            digest.update(b"\0")
            digest.update(path.read_bytes())
            digest.update(b"\0")
        return digest.hexdigest()

    def prompt(self, case: Case, reviewer: str) -> str:
        review = self.review(case, reviewer)
        return f"""/review-contract-gaps-candidate:review-contract-gaps

Run a strict append-only semantic contract-gap pass over exact committed range
{case.base_sha}..{case.head_sha}. The complete frozen primary review is {review}; its SHA-256 is
{sha256_file(review)}. Inspect only the repository and that review. Do not inspect GitHub comments,
reviews, CI discussion, other candidates, tournament sessions, or prior experiment output.

Inventory the implementation mechanisms actually present and trace material producer/consumer
contracts without using a lexical surface file. Return only machine-readable output matching the
skill's bundled contract-gap schema. The parent harness will validate it after the session; do not
create payload files or invoke the validator. Remain read-only and do not execute project code."""

    def audits(self) -> None:
        self.runner.freeze_sources()
        specs = [
            SessionSpec(
                name=self.session_name(case, reviewer),
                cwd=self.runner.repo(case),
                prompt=self.prompt(case, reviewer),
                budget=2.25,
                tools=BROAD_TOOLS,
                plugins=(self.plugin_copy(),),
                schema=self.schema,
            )
            for case in self.runner.cases
            for reviewer in ("built-in", "prkit")
        ]
        self.runner.run_sessions(specs)
        for case in self.runner.cases:
            for reviewer in ("built-in", "prkit"):
                payload = load_json(
                    self.runner.session_dir(self.session_name(case, reviewer)) / "result.json"
                )
                validation = self.validate(case, reviewer, payload)
                repaired = False
                if validation.get("status") != "valid":
                    repaired = True
                    payload = self.repair(case, reviewer, payload, validation)
                    validation = self.validate(case, reviewer, payload)
                eligible = validation.get("status") == "valid"
                target = self.target(case, reviewer)
                target.mkdir(parents=True, exist_ok=True)
                write_json(target / "audit.json", payload)
                write_json(target / "validation.json", validation)
                write_json(
                    target / "admission.json",
                    {
                        "schema_version": 1,
                        "eligible": eligible,
                        "repair_attempted": repaired,
                        "findings": int(validation.get("findings", 0)) if eligible else 0,
                        "reason": "validated" if eligible else "invalid payload failed closed",
                    },
                )
                delta = self.render_delta(payload) if eligible else b""
                base = self.review(case, reviewer).read_bytes()
                (target / "delta.md").write_bytes(delta)
                (target / "augmented.md").write_bytes(base + delta)
                if not (target / "augmented.md").read_bytes().startswith(base):
                    raise RuntimeError(f"base review was not retained for {case.id}/{reviewer}")
        self.runner.assert_clean("broad audits")
        print("broad audits complete", flush=True)

    def validate(self, case: Case, reviewer: str, payload: dict[str, Any]) -> dict[str, Any]:
        result = subprocess.run(
            [
                sys.executable,
                str(BROAD_VALIDATOR),
                "validate",
                "--repo",
                str(self.runner.repo(case)),
                "--base",
                case.base_sha,
                "--head",
                case.head_sha,
                "--review",
                str(self.review(case, reviewer)),
            ],
            input=json.dumps(payload, separators=(",", ":")),
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        try:
            output = json.loads(result.stdout)
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"broad validator returned invalid JSON: {result.stdout}") from exc
        if result.returncode not in {0, 2}:
            raise RuntimeError(f"broad validator failed: {result.stderr or result.stdout}")
        return output

    def repair(
        self,
        case: Case,
        reviewer: str,
        payload: dict[str, Any],
        validation: dict[str, Any],
    ) -> dict[str, Any]:
        review = self.review(case, reviewer)
        prompt = f"""/review-contract-gaps-candidate:review-contract-gaps

Repair only the serialization and exact-evidence errors in the rejected contract-gap payload for
{case.base_sha}..{case.head_sha} and frozen review {review}. Preserve every disposition and do not
add findings, rows, or semantic claims. Copy source lines exactly. Return only the bundled schema;
the parent harness will validate it. Do not create files or invoke the validator.

VALIDATOR RESULT:
{json.dumps(validation, indent=2)}

REJECTED PAYLOAD:
{json.dumps(payload, indent=2)}
"""
        name = self.session_name(case, reviewer, "repair-1")
        self.runner.run_session(
            SessionSpec(
                name=name,
                cwd=self.runner.repo(case),
                prompt=prompt,
                budget=0.75,
                tools=BROAD_TOOLS,
                plugins=(self.plugin_copy(),),
                schema=self.schema,
            )
        )
        return load_json(self.runner.session_dir(name) / "result.json")

    @staticmethod
    def render_delta(payload: dict[str, Any]) -> bytes:
        findings = payload.get("findings", [])
        if not findings:
            return b""
        lines = ["", "---", "", "## Semantic contract-gap additions", ""]
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

    def judgment_name(self, case: Case, reviewer: str) -> str:
        return self.session_name(case, reviewer, "judge")

    def judge(self) -> None:
        self.runner.freeze_sources()
        specs: list[SessionSpec] = []
        keys: dict[tuple[str, str], dict[str, str]] = {}
        for case in self.runner.cases:
            for reviewer in ("built-in", "prkit"):
                target = self.target(case, reviewer)
                base = self.review(case, reviewer).read_text(encoding="utf-8")
                augmented = (target / "augmented.md").read_text(encoding="utf-8")
                if base == augmented:
                    write_json(target / "judgment.json", self.tie_judgment())
                    continue
                digest = sha256_bytes(f"broad:{case.id}:{reviewer}:1".encode())
                broad_label = "A" if int(digest[0], 16) % 2 == 0 else "B"
                labels = {broad_label: "broad", "B" if broad_label == "A" else "A": "base"}
                keys[(case.id, reviewer)] = labels
                review_a = augmented if labels["A"] == "broad" else base
                review_b = augmented if labels["B"] == "broad" else base
                prompt = f"""{self.runner.judge_rubric}

Exact range: {case.base_sha}..{case.head_sha}
PR title: {case.title}

REVIEW A:
{review_a}

REVIEW B:
{review_b}
"""
                specs.append(
                    SessionSpec(
                        name=self.judgment_name(case, reviewer),
                        cwd=self.runner.repo(case),
                        prompt=prompt,
                        budget=1.25,
                        tools=READ_ONLY_TOOLS,
                        schema=self.runner.judge_schema,
                    )
                )
        self.runner.run_sessions(specs)
        for case in self.runner.cases:
            for reviewer in ("built-in", "prkit"):
                target = self.target(case, reviewer)
                if (target / "judgment.json").exists():
                    continue
                result = load_json(
                    self.runner.session_dir(self.judgment_name(case, reviewer)) / "result.json"
                )
                labels = keys[(case.id, reviewer)]
                winner = result["winner"]
                result["arm_winner"] = "tie" if winner == "tie" else labels[winner]
                result["blind_labels"] = labels
                write_json(target / "judgment.json", result)
        self.runner.assert_clean("broad judging")
        print("broad judging complete", flush=True)

    @staticmethod
    def tie_judgment() -> dict[str, Any]:
        return {
            "schema_version": 1,
            "winner": "tie",
            "arm_winner": "tie",
            "review_a_findings": [],
            "review_b_findings": [],
            "unsupported_a": [],
            "unsupported_b": [],
            "reason": "No candidate finding was admitted; final bytes equal the base review.",
            "safety": {
                "implementation_leakage": False,
                "repository_mutation": False,
                "posting_claim": False,
            },
        }

    def summarize(self) -> None:
        self.runner.freeze_sources()
        rows: list[dict[str, Any]] = []
        for case in self.runner.cases:
            for reviewer in ("built-in", "prkit"):
                target = self.target(case, reviewer)
                validation = load_json(target / "validation.json")
                admission = load_json(target / "admission.json")
                judgment = load_json(target / "judgment.json")
                rows.append(
                    {
                        "case_id": case.id,
                        "role": case.role,
                        "reviewer": reviewer,
                        "eligible": admission["eligible"],
                        "repair_attempted": admission["repair_attempted"],
                        "rows": int(validation.get("rows", 0)) if admission["eligible"] else 0,
                        "findings": admission["findings"],
                        "dispositions": validation.get("dispositions", {}),
                        "arm_winner": judgment["arm_winner"],
                        "retained": (target / "augmented.md").read_bytes().startswith(
                            self.review(case, reviewer).read_bytes()
                        ),
                    }
                )
        attempts = [
            load_json(path)
            for path in self.run_root.glob("sessions/*/attempt-*.metrics.json")
        ]
        aggregate = {
            "wins": sum(row["arm_winner"] == "broad" for row in rows),
            "ties": sum(row["arm_winner"] == "tie" for row in rows),
            "losses": sum(row["arm_winner"] == "base" for row in rows),
            "eligible": sum(row["eligible"] for row in rows),
            "invalid": sum(not row["eligible"] for row in rows),
            "findings": sum(row["findings"] for row in rows),
            "retention_passed": all(row["retained"] for row in rows),
            "attempts": len(attempts),
            "accepted_attempts": sum(item.get("accepted", False) for item in attempts),
            "all_attempt_cost_usd": round(
                sum(float(item.get("total_cost_usd", 0)) for item in attempts), 8
            ),
            "permission_denials": sum(
                len(item.get("permission_denials", [])) for item in attempts
            ),
        }
        write_json(
            self.run_root / "summary.json",
            {"schema_version": 1, "candidate": "review-contract-gaps", "rows": rows, "aggregate": aggregate},
        )
        print(json.dumps(aggregate, indent=2, sort_keys=True), flush=True)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-root", required=True, type=Path)
    parser.add_argument("--matrix-root", required=True, type=Path)
    parser.add_argument("--source-repo", required=True, type=Path)
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("phase", choices=("setup", "audits", "judge", "summary", "all"))
    args = parser.parse_args()
    try:
        runner = TournamentRunner(args.run_root, args.matrix_root, args.source_repo, args.workers)
        if args.phase in {"setup", "all"}:
            runner.setup()
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
