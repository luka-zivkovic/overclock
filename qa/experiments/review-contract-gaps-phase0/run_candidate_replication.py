#!/usr/bin/env python3
"""Replicate the frozen broad semantic audit for independent samples 2 and 3."""

from __future__ import annotations

import argparse
import concurrent.futures
import json
import shutil
import sys
from pathlib import Path
from typing import Any, Iterable

from run_candidate_tournament import BROAD_TOOLS, TournamentRunner
from run_live_matrix import (
    EXPERIMENT,
    READ_ONLY_TOOLS,
    Case,
    SessionSpec,
    load_json,
    sha256_bytes,
    sha256_file,
    write_json,
)


GATE_PATH = EXPERIMENT / "replication-gate.json"


class ReplicationRunner:
    def __init__(
        self,
        run_root: Path,
        screen_root: Path,
        matrix_root: Path,
        source_repo: Path,
        workers: int,
    ) -> None:
        self.run_root = run_root.resolve()
        self.screen_root = screen_root.resolve()
        self.tournament = TournamentRunner(run_root, matrix_root, source_repo, workers)
        self.runner = self.tournament.runner
        self.workers = workers
        self.gate = load_json(GATE_PATH)
        self.samples = tuple(int(item) for item in self.gate["samples"])
        self.max_analysis_attempts = int(
            self.gate["mechanics_gate"]["maximum_transport_attempts_per_analysis"]
        )
        self.max_repair_attempts = int(
            self.gate["mechanics_gate"]["maximum_transport_attempts_per_repair"]
        )

    def review(self, case: Case, reviewer: str, sample: int) -> Path:
        return self.runner.artifact(case, reviewer, f"sample-{sample}", "base.md")

    def target(self, case: Case, reviewer: str, sample: int) -> Path:
        return self.runner.artifact(case, reviewer, f"sample-{sample}", "broad")

    def session_name(
        self,
        case: Case,
        reviewer: str,
        sample: int,
        suffix: str,
    ) -> str:
        return f"{case.id}/{reviewer}/sample-{sample}/{suffix}"

    def setup(self) -> None:
        self.tournament.setup()
        screen_provenance_path = self.screen_root / "tournament-provenance.json"
        if not screen_provenance_path.is_file():
            raise RuntimeError("sample-1 tournament provenance is missing")
        screen_provenance = load_json(screen_provenance_path)
        candidate_digest = self.tournament.tree_digest(self.tournament.plugin_copy())
        if candidate_digest != screen_provenance["candidate_plugin_sha256"]:
            raise RuntimeError("candidate tree differs from the sample-1 tournament")

        reviews: list[dict[str, Any]] = []
        for case in self.runner.cases:
            for reviewer in ("built-in", "prkit"):
                source = self.tournament.source_review(case, reviewer)
                for sample in self.samples:
                    destination = self.review(case, reviewer, sample)
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    if destination.exists() and destination.read_bytes() != source.read_bytes():
                        raise RuntimeError(f"replication review drifted: {destination}")
                    destination.write_bytes(source.read_bytes())
                    reviews.append(
                        {
                            "case_id": case.id,
                            "reviewer": reviewer,
                            "sample": sample,
                            "source": str(source),
                            "sha256": sha256_file(source),
                        }
                    )
        evidence = {
            "schema_version": 1,
            "screen_root": str(self.screen_root),
            "screen_provenance_sha256": sha256_file(screen_provenance_path),
            "screen_result_sha256": sha256_file(
                EXPERIMENT / "results/candidate-tournament-2026-08-17.json"
            ),
            "candidate_plugin_sha256": candidate_digest,
            "replication_gate_sha256": sha256_file(GATE_PATH),
            "samples": list(self.samples),
            "reviews": reviews,
        }
        destination = self.run_root / "replication-provenance.json"
        if destination.exists() and load_json(destination) != evidence:
            raise RuntimeError("replication provenance changed after setup")
        write_json(destination, evidence)
        self.runner.assert_clean("replication setup")
        print(f"replication setup complete: {self.run_root}", flush=True)

    def prompt(self, case: Case, reviewer: str, sample: int) -> str:
        review = self.review(case, reviewer, sample)
        return f"""/review-contract-gaps-candidate:review-contract-gaps

Run a strict append-only semantic contract-gap pass over exact committed range
{case.base_sha}..{case.head_sha}. The complete frozen primary review is {review}; its SHA-256 is
{sha256_file(review)}. Inspect only the repository and that review. Do not inspect GitHub comments,
reviews, CI discussion, other candidates, replication sessions, or prior experiment output.

Inventory the implementation mechanisms actually present and trace material producer/consumer
contracts without using a lexical surface file. Return only machine-readable output matching the
skill's bundled contract-gap schema. The parent harness will validate it after the session; do not
create payload files or invoke the validator. Remain read-only and do not execute project code."""

    def run_resilient(
        self,
        specs: Iterable[SessionSpec],
        *,
        maximum_attempts: int,
    ) -> set[str]:
        pending = {spec.name: spec for spec in specs}
        for _ in range(maximum_attempts):
            if not pending:
                break
            failed: dict[str, SessionSpec] = {}
            with concurrent.futures.ThreadPoolExecutor(max_workers=self.workers) as pool:
                futures = {
                    pool.submit(self.runner.run_session, spec): spec
                    for spec in pending.values()
                }
                while futures:
                    done, _ = concurrent.futures.wait(
                        futures,
                        timeout=30,
                        return_when=concurrent.futures.FIRST_COMPLETED,
                    )
                    if not done:
                        print(
                            "replication heartbeat; running/queued: "
                            + ", ".join(sorted(spec.name for spec in futures.values())),
                            flush=True,
                        )
                        continue
                    for future in done:
                        spec = futures.pop(future)
                        try:
                            future.result()
                        except Exception as exc:  # transport failures are evidence, then retry
                            print(f"attempt failed {spec.name}: {exc}", flush=True)
                            failed[spec.name] = spec
            pending = failed
        return set(pending)

    def repair_spec(
        self,
        case: Case,
        reviewer: str,
        sample: int,
        payload: dict[str, Any],
        validation: dict[str, Any],
    ) -> SessionSpec:
        review = self.review(case, reviewer, sample)
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
        return SessionSpec(
            name=self.session_name(case, reviewer, sample, "broad-repair-1"),
            cwd=self.runner.repo(case),
            prompt=prompt,
            budget=0.75,
            tools=BROAD_TOOLS,
            plugins=(self.tournament.plugin_copy(),),
            schema=self.tournament.schema,
        )

    def audits(self) -> None:
        self.runner.freeze_sources()
        audit_specs = [
            SessionSpec(
                name=self.session_name(case, reviewer, sample, "broad-audit"),
                cwd=self.runner.repo(case),
                prompt=self.prompt(case, reviewer, sample),
                budget=2.25,
                tools=BROAD_TOOLS,
                plugins=(self.tournament.plugin_copy(),),
                schema=self.tournament.schema,
            )
            for case in self.runner.cases
            for sample in self.samples
            for reviewer in ("built-in", "prkit")
        ]
        failed_audits = self.run_resilient(
            audit_specs,
            maximum_attempts=self.max_analysis_attempts,
        )

        initial: dict[tuple[str, str, int], tuple[dict[str, Any], dict[str, Any]]] = {}
        repair_specs: list[SessionSpec] = []
        for case in self.runner.cases:
            for sample in self.samples:
                for reviewer in ("built-in", "prkit"):
                    name = self.session_name(case, reviewer, sample, "broad-audit")
                    if name in failed_audits:
                        continue
                    result_path = self.runner.session_dir(name) / "result.json"
                    if not result_path.is_file():
                        failed_audits.add(name)
                        continue
                    payload = load_json(result_path)
                    validation = self.tournament.validate(case, reviewer, payload)
                    initial[(case.id, reviewer, sample)] = (payload, validation)
                    if validation.get("status") != "valid":
                        repair_specs.append(
                            self.repair_spec(case, reviewer, sample, payload, validation)
                        )
        failed_repairs = self.run_resilient(
            repair_specs,
            maximum_attempts=self.max_repair_attempts,
        )

        processed: list[dict[str, Any]] = []
        for case in self.runner.cases:
            for sample in self.samples:
                for reviewer in ("built-in", "prkit"):
                    key = (case.id, reviewer, sample)
                    audit_name = self.session_name(case, reviewer, sample, "broad-audit")
                    repair_name = self.session_name(case, reviewer, sample, "broad-repair-1")
                    source_payload = "none"
                    payload: dict[str, Any] = {}
                    validation: dict[str, Any] = {
                        "status": "invalid",
                        "errors": ["analysis transport failed"],
                    }
                    if key in initial:
                        source_payload = "initial"
                        payload, validation = initial[key]
                        repair_result = self.runner.session_dir(repair_name) / "result.json"
                        repair_metrics = self.runner.session_dir(repair_name) / "metrics.json"
                        if (
                            validation.get("status") != "valid"
                            and repair_name not in failed_repairs
                            and repair_result.is_file()
                            and repair_metrics.is_file()
                        ):
                            source_payload = "repair-1"
                            payload = load_json(repair_result)
                            validation = self.tournament.validate(case, reviewer, payload)
                    eligible = validation.get("status") == "valid"
                    target = self.target(case, reviewer, sample)
                    target.mkdir(parents=True, exist_ok=True)
                    write_json(target / "audit.json", payload)
                    write_json(target / "validation.json", validation)
                    repair_dir = self.runner.session_dir(repair_name)
                    repair_attempts = len(list(repair_dir.glob("attempt-*.metrics.json")))
                    admission = {
                        "schema_version": 1,
                        "eligible": eligible,
                        "repair_required": key in initial
                        and initial[key][1].get("status") != "valid",
                        "repair_attempts": repair_attempts,
                        "source_payload": source_payload,
                        "findings": int(validation.get("findings", 0)) if eligible else 0,
                        "reason": "validated" if eligible else "invalid payload failed closed",
                    }
                    write_json(target / "admission.json", admission)
                    delta = self.tournament.render_delta(payload) if eligible else b""
                    base = self.review(case, reviewer, sample).read_bytes()
                    (target / "delta.md").write_bytes(delta)
                    (target / "augmented.md").write_bytes(base + delta)
                    processed.append(
                        {
                            "case_id": case.id,
                            "reviewer": reviewer,
                            "sample": sample,
                            **admission,
                            "errors": validation.get("errors", []),
                            "analysis_failed": audit_name in failed_audits,
                        }
                    )
        write_json(
            self.run_root / "replication-postprocessing.json",
            {
                "schema_version": 1,
                "policy": "At most two transport attempts for one analysis and one repair session; invalid or unavailable payloads fail closed to the frozen base review.",
                "processed": processed,
            },
        )
        self.runner.assert_clean("replication audits")
        print("replication audits complete", flush=True)

    def judge_name(self, case: Case, reviewer: str, sample: int) -> str:
        return self.session_name(case, reviewer, sample, "broad-judge")

    def judge(self) -> None:
        self.runner.freeze_sources()
        specs: list[SessionSpec] = []
        keys: dict[tuple[str, str, int], dict[str, str]] = {}
        for case in self.runner.cases:
            for sample in self.samples:
                for reviewer in ("built-in", "prkit"):
                    target = self.target(case, reviewer, sample)
                    base = self.review(case, reviewer, sample).read_text(encoding="utf-8")
                    augmented = (target / "augmented.md").read_text(encoding="utf-8")
                    if base == augmented:
                        write_json(target / "judgment.json", self.tournament.tie_judgment())
                        continue
                    digest = sha256_bytes(
                        f"broad-replication:{case.id}:{reviewer}:{sample}".encode()
                    )
                    broad_label = "A" if int(digest[0], 16) % 2 == 0 else "B"
                    labels = {
                        broad_label: "broad",
                        "B" if broad_label == "A" else "A": "base",
                    }
                    keys[(case.id, reviewer, sample)] = labels
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
                            name=self.judge_name(case, reviewer, sample),
                            cwd=self.runner.repo(case),
                            prompt=prompt,
                            budget=1.25,
                            tools=READ_ONLY_TOOLS,
                            schema=self.runner.judge_schema,
                        )
                    )
        failed = self.run_resilient(specs, maximum_attempts=2)
        for case in self.runner.cases:
            for sample in self.samples:
                for reviewer in ("built-in", "prkit"):
                    target = self.target(case, reviewer, sample)
                    if (target / "judgment.json").exists():
                        continue
                    name = self.judge_name(case, reviewer, sample)
                    result_path = self.runner.session_dir(name) / "result.json"
                    if name in failed or not result_path.is_file():
                        write_json(
                            target / "judgment.json",
                            {
                                "schema_version": 1,
                                "winner": "unjudged",
                                "arm_winner": "unjudged",
                                "reason": "Blind judge transport failed after bounded retries.",
                                "unsupported_a": [],
                                "unsupported_b": [],
                                "safety": {
                                    "implementation_leakage": False,
                                    "repository_mutation": False,
                                    "posting_claim": False,
                                }
                            },
                        )
                        continue
                    result = load_json(result_path)
                    labels = keys[(case.id, reviewer, sample)]
                    winner = result["winner"]
                    result["arm_winner"] = "tie" if winner == "tie" else labels[winner]
                    result["blind_labels"] = labels
                    write_json(target / "judgment.json", result)
        self.runner.assert_clean("replication judging")
        print("replication judging complete", flush=True)

    @staticmethod
    def unsupported_candidate_count(judgment: dict[str, Any]) -> int:
        labels = judgment.get("blind_labels", {})
        broad_label = next(
            (label for label, arm in labels.items() if arm == "broad"),
            None,
        )
        if broad_label is None:
            return 0
        return len(judgment.get(f"unsupported_{broad_label.lower()}", []))

    def summarize(self) -> None:
        self.runner.freeze_sources()
        rows: list[dict[str, Any]] = []
        for case in self.runner.cases:
            for sample in self.samples:
                for reviewer in ("built-in", "prkit"):
                    target = self.target(case, reviewer, sample)
                    admission = load_json(target / "admission.json")
                    validation = load_json(target / "validation.json")
                    judgment = load_json(target / "judgment.json")
                    payload = load_json(target / "audit.json")
                    root_causes = [
                        row.get("root_cause_key")
                        for row in payload.get("rows", [])
                        if row.get("disposition") == "confirmed-gap"
                    ]
                    rows.append(
                        {
                            "case_id": case.id,
                            "role": case.role,
                            "reviewer": reviewer,
                            "sample": sample,
                            "eligible": admission["eligible"],
                            "repair_required": admission["repair_required"],
                            "findings": admission["findings"],
                            "root_causes": root_causes,
                            "arm_winner": judgment["arm_winner"],
                            "unsupported_candidate_findings": self.unsupported_candidate_count(
                                judgment
                            ),
                            "retained": (target / "augmented.md").read_bytes().startswith(
                                self.review(case, reviewer, sample).read_bytes()
                            ),
                            "validation_status": validation.get("status"),
                        }
                    )

        per_sample: dict[str, dict[str, Any]] = {}
        behavior_gate = self.gate["per_sample_behavior_gate"]
        for sample in self.samples:
            sample_rows = [row for row in rows if row["sample"] == sample]
            wins = sum(row["arm_winner"] == "broad" for row in sample_rows)
            losses = sum(row["arm_winner"] == "base" for row in sample_rows)
            unjudged = sum(row["arm_winner"] == "unjudged" for row in sample_rows)
            unsupported = sum(
                row["unsupported_candidate_findings"] for row in sample_rows
            )
            negative_findings = sum(
                row["findings"]
                for row in sample_rows
                if row["case_id"] == "frozen-error-prototype"
            )
            passed = (
                wins >= int(behavior_gate["minimum_wins"])
                and losses <= int(behavior_gate["maximum_losses"])
                and unsupported
                <= int(behavior_gate["maximum_unsupported_candidate_findings"])
                and unjudged <= int(behavior_gate["maximum_unjudged_deltas"])
                and negative_findings == int(behavior_gate["negative_case_findings"])
                and all(row["retained"] for row in sample_rows)
            )
            per_sample[str(sample)] = {
                "wins": wins,
                "ties": sum(row["arm_winner"] == "tie" for row in sample_rows),
                "losses": losses,
                "unjudged": unjudged,
                "unsupported_candidate_findings": unsupported,
                "negative_case_findings": negative_findings,
                "retention_passed": all(row["retained"] for row in sample_rows),
                "passed": passed,
            }

        win_rows = [row for row in rows if row["arm_winner"] == "broad"]
        distinct_win_cases = sorted({row["case_id"] for row in win_rows})
        win_reviewers = sorted({row["reviewer"] for row in win_rows})
        combined_gate = self.gate["combined_behavior_gate"]
        behavior_passed = (
            all(item["passed"] for item in per_sample.values())
            and len(distinct_win_cases)
            >= int(combined_gate["minimum_distinct_win_cases"])
            and set(win_reviewers) == set(combined_gate["required_win_reviewers"])
        )

        valid_rate = sum(row["eligible"] for row in rows) / len(rows)
        repair_rate = sum(row["repair_required"] for row in rows) / len(rows)
        mechanics_gate = self.gate["mechanics_gate"]
        mechanics_passed = (
            valid_rate >= float(mechanics_gate["minimum_valid_ledger_rate"])
            and repair_rate <= float(mechanics_gate["maximum_repair_dependency_rate"])
        )

        attempts = [
            (path, load_json(path))
            for path in self.run_root.glob("sessions/*/attempt-*.metrics.json")
        ]
        cost: dict[str, dict[str, Any]] = {}
        for path, metrics in attempts:
            name = path.parent.name
            kind = (
                "judge"
                if name.endswith("__broad-judge")
                else "repair"
                if name.endswith("__broad-repair-1")
                else "audit"
            )
            state = "accepted" if metrics.get("accepted") else "failed"
            bucket = cost.setdefault(
                f"{kind}_{state}",
                {"attempts": 0, "cost_usd": 0.0, "permission_denials": 0},
            )
            bucket["attempts"] += 1
            bucket["cost_usd"] += float(metrics.get("total_cost_usd", 0))
            bucket["permission_denials"] += len(metrics.get("permission_denials", []))
        for bucket in cost.values():
            bucket["cost_usd"] = round(bucket["cost_usd"], 8)

        if not behavior_passed:
            decision = "park"
        elif not mechanics_passed:
            decision = "redesign-mechanics"
        else:
            decision = "advance-fresh-ab"
        summary = {
            "schema_version": 1,
            "candidate": "review-contract-gaps",
            "samples": list(self.samples),
            "rows": rows,
            "per_sample": per_sample,
            "aggregate": {
                "wins": sum(row["arm_winner"] == "broad" for row in rows),
                "ties": sum(row["arm_winner"] == "tie" for row in rows),
                "losses": sum(row["arm_winner"] == "base" for row in rows),
                "unjudged": sum(row["arm_winner"] == "unjudged" for row in rows),
                "findings": sum(row["findings"] for row in rows),
                "valid_ledgers": sum(row["eligible"] for row in rows),
                "invalid_ledgers": sum(not row["eligible"] for row in rows),
                "repair_required": sum(row["repair_required"] for row in rows),
                "valid_ledger_rate": valid_rate,
                "repair_dependency_rate": repair_rate,
                "distinct_win_cases": distinct_win_cases,
                "win_reviewers": win_reviewers,
                "behavior_passed": behavior_passed,
                "mechanics_passed": mechanics_passed,
                "decision": decision,
            },
            "cost": cost,
            "all_attempt_cost_usd": round(
                sum(float(metrics.get("total_cost_usd", 0)) for _, metrics in attempts),
                8,
            ),
        }
        write_json(self.run_root / "summary.json", summary)
        print(json.dumps(summary["aggregate"], indent=2, sort_keys=True), flush=True)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-root", required=True, type=Path)
    parser.add_argument("--screen-root", required=True, type=Path)
    parser.add_argument("--matrix-root", required=True, type=Path)
    parser.add_argument("--source-repo", required=True, type=Path)
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("phase", choices=("setup", "audits", "judge", "summary", "all"))
    args = parser.parse_args()
    try:
        runner = ReplicationRunner(
            args.run_root,
            args.screen_root,
            args.matrix_root,
            args.source_repo,
            args.workers,
        )
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
