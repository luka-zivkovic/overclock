#!/usr/bin/env python3
"""Validate and normalize one live-eval judge response.

Expectation failures produce a normal FAIL verdict. Malformed judge output is an
infrastructure error and exits nonzero so baseline mode cannot hide it.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path


def extract_object(text: str) -> dict:
    decoder = json.JSONDecoder()
    for index, character in enumerate(text):
        if character != "{":
            continue
        try:
            value, _ = decoder.raw_decode(text[index:])
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict) and "verdicts" in value:
            return value
    raise ValueError("judge response contains no JSON object with verdicts")


def normalize(raw_result: str, expectations: list[str]) -> dict:
    if not expectations:
        raise ValueError("eval expectations must be non-empty")
    value = extract_object(raw_result)
    verdicts = value.get("verdicts")
    if not isinstance(verdicts, list):
        raise ValueError("verdicts must be an array")
    if len(verdicts) != len(expectations):
        raise ValueError(
            f"judge returned {len(verdicts)} verdicts for {len(expectations)} expectations"
        )

    normalized = []
    for index, (declared, row) in enumerate(zip(expectations, verdicts)):
        if not isinstance(row, dict):
            raise ValueError(f"verdicts[{index}] must be an object")
        verdict = row.get("verdict")
        if verdict not in {"PASS", "FAIL"}:
            raise ValueError(f"verdicts[{index}].verdict must be PASS or FAIL")
        why = row.get("why")
        if not isinstance(why, str) or not why.strip():
            raise ValueError(f"verdicts[{index}].why must be a non-empty string")
        normalized.append(
            {"expectation": declared, "verdict": verdict, "why": why.strip()}
        )

    passed = sum(row["verdict"] == "PASS" for row in normalized)
    return {"verdicts": normalized, "passed": passed, "total": len(expectations)}


def main(argv: list[str]) -> int:
    if len(argv) != 5:
        print(
            "usage: validate_judge_result.py JUDGE_RAW EVALS CASE_INDEX GRADING_OUT",
            file=sys.stderr,
        )
        return 2
    raw_path = Path(argv[1])
    evals_path = Path(argv[2])
    output_path = Path(argv[4])
    try:
        case_index = int(argv[3])
        wrapper = json.loads(raw_path.read_text(encoding="utf-8"))
        raw_result = wrapper.get("result")
        if not isinstance(raw_result, str):
            raise ValueError("judge wrapper result must be a string")
        case = json.loads(evals_path.read_text(encoding="utf-8"))["evals"][case_index]
        expectations = case.get("expectations")
        if not isinstance(expectations, list) or not expectations or not all(
            isinstance(item, str) and item for item in expectations
        ):
            raise ValueError("eval expectations must be a non-empty string array")
        grading = normalize(raw_result, expectations)
        output_path.write_text(json.dumps(grading, indent=1) + "\n", encoding="utf-8")
    except (OSError, ValueError, KeyError, IndexError, json.JSONDecodeError) as exc:
        print(f"JUDGE-ERROR {exc}")
        return 2
    if grading["passed"] == grading["total"]:
        print("PASS")
    else:
        print(f"FAIL {grading['passed']}/{grading['total']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
