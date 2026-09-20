from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SKILL_DIR = REPO / "plugins/untangle/skills/untangle"
SCRIPT = SKILL_DIR / "scripts/untangle.py"
sys.path.insert(0, str(SKILL_DIR / "scripts"))
import untangle  # noqa: E402

GIT_ENV = {
    **os.environ,
    "GIT_AUTHOR_NAME": "fixture",
    "GIT_AUTHOR_EMAIL": "fixture@example.com",
    "GIT_COMMITTER_NAME": "fixture",
    "GIT_COMMITTER_EMAIL": "fixture@example.com",
}

FAKE_AWS_KEY = "AKIA" + "ABCDEFGHIJKLMNOP"


def write(root: Path, relative: str, text: str) -> None:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def git(root: Path, *args: str, date: str | None = None) -> str:
    env = dict(GIT_ENV)
    if date:
        env["GIT_AUTHOR_DATE"] = date
        env["GIT_COMMITTER_DATE"] = date
    return subprocess.run(
        ["git", *args], cwd=root, env=env, check=True, capture_output=True, text=True
    ).stdout


def run(*args: str, cwd: Path | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        cwd=cwd,
        env=GIT_ENV,
        capture_output=True,
        text=True,
        check=False,
    )


def tree_digest(root: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(root.rglob("*")):
        if ".git" in path.parts:
            continue
        digest.update(path.relative_to(root).as_posix().encode())
        if path.is_file():
            digest.update(path.read_bytes())
    return digest.hexdigest()


def build_sprawl(root: Path) -> None:
    write(
        root,
        "README.md",
        "# Notely\n\nNotely is a command-line note-taking app that keeps notes as plain text.\n\n"
        "## Usage\n\nRun `bin/notely add \"text\"`. See `docs/SETUP.md` and `scripts/install.sh`.\n",
    )
    write(
        root,
        "package.json",
        json.dumps(
            {
                "name": "notely",
                "description": "Command-line notes",
                "scripts": {"start": "node src/server/index.js", "cli": "node src/cli.js"},
                "dependencies": {
                    "express": "^4",
                    "fastify": "^4",
                    "passport": "^0.7",
                    "jsonwebtoken": "^9",
                },
            }
        )
        + "\n",
    )
    write(root, ".eslintrc.json", '{"extends":"eslint:recommended"}\n')
    write(
        root,
        "src/server/index.js",
        'const express = require("express");\nconst app = express();\n'
        "app.listen(process.env.PORT, () => console.log(process.env.SYNC_TOKEN));\n",
    )
    write(root, "src/auth/passport.js", 'module.exports = require("passport");\n// TODO wire sessions\n')
    write(
        root,
        "src/auth/jwt.js",
        'const jwt = require("jsonwebtoken");\nmodule.exports = t => jwt.verify(t, process.env.JWT_SECRET);\n',
    )
    write(root, "docs/SETUP.md", "See `src/missing/file.js` for details.\n")
    write(root, ".env", f"SYNC_TOKEN=placeholder\nAWS_KEY={FAKE_AWS_KEY}\n")
    write(root, "experiments/ai-summarizer/index.js", 'console.log("summarize");\n')
    write(root, "old/notes.txt", "old stuff\n")
    git(root, "init", "-q", "-b", "main")
    git(root, "add", "-A")
    git(root, "commit", "-qm", "initial sprawl", date="2026-01-10T00:00:00")
    with (root / "src/server/index.js").open("a", encoding="utf-8") as handle:
        handle.write("// serve\n")
    git(root, "add", "-A")
    git(root, "commit", "-qm", "server work", date="2026-06-01T00:00:00")


def build_clean(root: Path) -> None:
    write(root, "README.md", "# Tidy\n\nA small CLI that counts words.\n\n## Usage\n\nRun `src/cli.js`.\n")
    write(root, "package.json", '{"name":"tidy","scripts":{"test":"node test/cli.test.js"},"dependencies":{}}\n')
    write(root, "package-lock.json", "{}\n")
    write(root, ".gitignore", "node_modules\n.env\n")
    write(root, "src/cli.js", 'console.log(require("./count").count(process.argv[2]));\n')
    write(root, "src/count.js", "exports.count = s => s.split(/\\s+/).length;\n")
    write(root, "test/cli.test.js", 'require("assert").equal(require("../src/count").count("a b"), 2);\n')
    git(root, "init", "-q", "-b", "main")
    git(root, "add", "-A")
    git(root, "commit", "-qm", "tidy baseline", date="2026-06-01T00:00:00")


PLAN = """# Untangle plan

<!-- untangle-plan: v1 -->

## 1. Spine

Notely is a command-line note-taking app.

Source: README.md

## 2. Threads

| ID | Thread | Role | Evidence | Decision | Decided by |
|----|--------|------|----------|----------|------------|
| T1 | Command-line notes | spine | README.md | keep | survey |
| T2 | Web server | contradicting | src/server | park | user |
| T3 | AI summarizer | abandoned | experiments/ai-summarizer | delete | user |

## 3. Checklist

- [ ] C1 (H1) Stop tracking .env | paths: .env, .gitignore | verify: git ls-files omits .env
- [ ] C2 (T3) Delete the summarizer experiment | paths: experiments/ai-summarizer | verify: directory absent
- [ ] C3 (T2) Move the server into archive/server | paths: src/server, archive/server | verify: src/server absent

## 4. Foundations

| ID | Finding | Evidence | Cost of keeping | Cost of changing now | Cost of changing later |
|----|---------|----------|-----------------|----------------------|------------------------|
| F1 | Two auth libraries and no auth need | src/auth | confusion | small | grows |

## 5. Suggested next moves

### Next

- N1 (T1) Build the bin/notely command the README promises

### Then

- N2 (F1) Decide whether sync needs auth

### Parked ideas

- T2: A web view of the notes folder
"""


class ScanTest(unittest.TestCase):
    def test_scan_reports_every_planted_signal_and_writes_nothing(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "sprawl"
            build_sprawl(root)
            before = tree_digest(root)
            completed = run("scan", "--root", str(root))
            self.assertEqual(completed.returncode, 0, completed.stderr)
            self.assertEqual(tree_digest(root), before)
            data = json.loads(completed.stdout)

            self.assertEqual(data["schema"], "untangle-scan/v1")
            self.assertIn("command-line note-taking", data["purpose_sources"][0]["first_paragraph"])
            self.assertEqual(data["sentinel_names"]["items"], ["experiments", "old"])
            self.assertEqual(data["unreferenced_top_level_directories"]["items"], ["experiments", "old"])
            stale = {item["path"] for item in data["stale_directories"]["items"]}
            self.assertIn("experiments", stale)
            self.assertIn("old", stale)
            self.assertNotIn("src/server", stale)
            families = {item["family"]: item["members"] for item in data["duplicate_capabilities"]}
            self.assertEqual(families["web framework (node)"], ["express", "fastify"])
            self.assertEqual(families["auth (node)"], ["jsonwebtoken", "passport"])
            self.assertEqual(data["tool_config_without_dependency"], [{"tool": "eslint", "config": [".eslintrc.json"]}])
            self.assertEqual(data["script_targets_missing"], [{"script": "cli", "target": "src/cli.js"}])
            missing_docs = {(item["doc"], item["path"]) for item in data["doc_paths_missing"]["items"]}
            self.assertEqual(
                missing_docs,
                {("README.md", "scripts/install.sh"), ("docs/SETUP.md", "src/missing/file.js")},
            )
            self.assertNotIn(("README.md", "docs/SETUP.md"), missing_docs)
            env_names = [item["name"] for item in data["env_vars"]["undocumented"]["items"]]
            self.assertEqual(env_names, ["JWT_SECRET", "SYNC_TOKEN"])
            self.assertEqual(data["todos"]["total"], 1)
            hygiene = data["hygiene"]
            self.assertFalse(hygiene["gitignore_present"])
            self.assertFalse(hygiene["lockfile_present"])
            self.assertFalse(hygiene["tests_present"])
            self.assertTrue(hygiene["readme_has_run_section"])
            self.assertEqual(hygiene["committed_env_files"], [".env"])
            self.assertEqual(hygiene["secret_like_content"]["items"], [{"path": ".env", "kind": "aws access key"}])
            self.assertNotIn(FAKE_AWS_KEY, completed.stdout)
            self.assertNotIn("placeholder", completed.stdout)

    def test_clean_repository_produces_no_findings(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "clean"
            build_clean(root)
            data = json.loads(run("scan", "--root", str(root)).stdout)
            self.assertEqual(data["sentinel_names"]["items"], [])
            self.assertEqual(data["duplicate_capabilities"], [])
            self.assertEqual(data["tool_config_without_dependency"], [])
            self.assertEqual(data["script_targets_missing"], [])
            self.assertEqual(data["doc_paths_missing"]["items"], [])
            self.assertEqual(data["stale_directories"]["items"], [])
            self.assertEqual(data["unreferenced_top_level_directories"]["items"], [])
            hygiene = data["hygiene"]
            self.assertTrue(hygiene["gitignore_present"])
            self.assertTrue(hygiene["lockfile_present"])
            self.assertTrue(hygiene["tests_present"])
            self.assertEqual(hygiene["committed_env_files"], [])
            self.assertEqual(hygiene["secret_like_content"]["items"], [])

    def test_scan_skips_symlinks_and_heavy_directories(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "links"
            build_clean(root)
            outside = Path(temp) / "outside.txt"
            outside.write_text("AKIA" + "QQQQQQQQQQQQQQQQ\n", encoding="utf-8")
            (root / "leak.txt").symlink_to(outside)
            write(root, "node_modules/dep/old/index.js", "// TODO vendored\n")
            data = json.loads(run("scan", "--root", str(root)).stdout)
            self.assertEqual(data["hygiene"]["secret_like_content"]["items"], [])
            self.assertEqual(data["todos"]["total"], 0)
            self.assertNotIn("node_modules", data["top_level_directories"])

    def test_scan_out_inside_root_must_use_the_reserved_name(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "clean"
            build_clean(root)
            refused = run("scan", "--root", str(root), "--out", str(root / "scan.json"))
            self.assertEqual(refused.returncode, 1)
            self.assertFalse((root / "scan.json").exists())
            accepted = run("scan", "--root", str(root), "--out", str(root / ".untangle-scan.json"))
            self.assertEqual(accepted.returncode, 0, accepted.stderr)
            self.assertTrue((root / ".untangle-scan.json").is_file())


class PlanTest(unittest.TestCase):
    def test_template_and_sample_plan_parse(self) -> None:
        template = (SKILL_DIR / "templates/plan.md").read_text(encoding="utf-8")
        parsed, errors = untangle.parse_plan(template)
        self.assertEqual(errors, [])
        self.assertEqual(parsed["pending_decisions"], ["T2"])
        parsed, errors = untangle.parse_plan(PLAN)
        self.assertEqual(errors, [])
        self.assertEqual(sorted(parsed["threads"]), ["T1", "T2", "T3"])
        self.assertEqual(parsed["roadmap"], {"next": ["N1"], "then": ["N2"], "parked": ["T2"]})

    def test_check_rejects_structural_defects(self) -> None:
        cases = {
            "cites unknown id T9": PLAN.replace("- N1 (T1)", "- N1 (T9)"),
            "Next may hold exactly one move": PLAN.replace(
                "### Then\n", "- N9 (T1) A second next move\n\n### Then\n"
            ),
            "Parked ideas must list exactly the parked threads": PLAN.replace("- T2: A web view", "- T3: A web view"),
            "has no checklist item": PLAN.replace(
                "- [ ] C2 (T3) Delete the summarizer experiment | paths: experiments/ai-summarizer | verify: directory absent\n",
                "",
            ),
            "Foundations is capped at three": PLAN.replace(
                "| F1 | Two auth libraries and no auth need | src/auth | confusion | small | grows |\n",
                "".join(
                    f"| F{n} | Finding {n} | src/auth | a | b | c |\n" for n in range(1, 5)
                ),
            ),
            "the spine can only be kept": PLAN.replace("| keep | survey |", "| delete | survey |"),
            "missing plan marker": PLAN.replace(untangle.PLAN_MARKER, ""),
            "malformed checklist line": PLAN.replace(
                "- [ ] C1 (H1) Stop tracking .env | paths: .env, .gitignore | verify: git ls-files omits .env",
                "- [ ] C1 Stop tracking .env",
            ),
        }
        for expected, text in cases.items():
            with self.subTest(expected=expected):
                _, errors = untangle.parse_plan(text)
                self.assertTrue(any(expected in error for error in errors), errors)

    def test_next_requires_clean_tree_except_the_plan_itself(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "sprawl"
            build_sprawl(root)
            plan = root / "UNTANGLE.md"
            plan.write_text(PLAN, encoding="utf-8")
            completed = run("plan", "next", "--plan", str(plan), "--root", str(root))
            self.assertEqual(completed.returncode, 0, completed.stderr)
            self.assertEqual(json.loads(completed.stdout)["next"]["id"], "C1")

            (root / "README.md").write_text("changed\n", encoding="utf-8")
            dirty = run("plan", "next", "--plan", str(plan), "--root", str(root))
            self.assertEqual(dirty.returncode, 2)
            self.assertEqual(json.loads(dirty.stdout)["dirty"], ["README.md"])

    def test_next_refuses_pending_decisions(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "sprawl"
            build_sprawl(root)
            plan = root / "UNTANGLE.md"
            plan.write_text(PLAN.replace("| park | user |", "| pending | — |"), encoding="utf-8")
            completed = run("plan", "next", "--plan", str(plan), "--root", str(root))
            self.assertEqual(completed.returncode, 1)
            self.assertIn("pending decisions: T2", completed.stderr)

    def test_tick_records_done_line_and_refuses_repeat(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "sprawl"
            build_sprawl(root)
            plan = root / "UNTANGLE.md"
            plan.write_text(PLAN, encoding="utf-8")
            first = run(
                "plan", "tick", "--plan", str(plan), "--item", "C1",
                "--note", "untracked .env and ignored it", "--verified", "git ls-files omits .env",
            )
            self.assertEqual(first.returncode, 0, first.stderr)
            text = plan.read_text(encoding="utf-8")
            self.assertIn("- [x] C1 (H1) Stop tracking .env", text)
            self.assertIn("| untracked .env and ignored it | verified: git ls-files omits .env", text)
            self.assertIn("- [ ] C2 (T3)", text)
            _, errors = untangle.parse_plan(text)
            self.assertEqual(errors, [])

            again = run("plan", "tick", "--plan", str(plan), "--item", "C1", "--note", "x", "--verified", "y")
            self.assertEqual(again.returncode, 1)
            self.assertIn("already ticked", again.stderr)
            unknown = run("plan", "tick", "--plan", str(plan), "--item", "C9", "--note", "x", "--verified", "y")
            self.assertEqual(unknown.returncode, 1)
            piped = run("plan", "tick", "--plan", str(plan), "--item", "C2", "--note", "a | b", "--verified", "y")
            self.assertEqual(piped.returncode, 1)
            self.assertIn("- [ ] C2 (T3)", plan.read_text(encoding="utf-8"))

            nxt = json.loads(run("plan", "next", "--plan", str(plan), "--root", str(root)).stdout)
            self.assertEqual(nxt["next"]["id"], "C2")
            self.assertEqual(nxt["remaining"], 2)

    def test_next_reports_completion(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "sprawl"
            build_sprawl(root)
            plan = root / "UNTANGLE.md"
            plan.write_text(PLAN, encoding="utf-8")
            for item in ("C1", "C2", "C3"):
                done = run("plan", "tick", "--plan", str(plan), "--item", item, "--note", "did it", "--verified", "checked")
                self.assertEqual(done.returncode, 0, done.stderr)
            completed = run("plan", "next", "--plan", str(plan), "--root", str(root))
            self.assertEqual(completed.returncode, 3)
            self.assertIsNone(json.loads(completed.stdout)["next"])

    def test_plan_must_not_be_a_symlink(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            real = Path(temp) / "real.md"
            real.write_text(PLAN, encoding="utf-8")
            link = Path(temp) / "UNTANGLE.md"
            link.symlink_to(real)
            completed = run("plan", "check", "--plan", str(link))
            self.assertEqual(completed.returncode, 1)
            self.assertIn("symlink", completed.stderr)


if __name__ == "__main__":
    unittest.main()
