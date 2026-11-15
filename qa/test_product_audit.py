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
SKILL_DIR = REPO / "plugins/product-audit/skills/product-audit"
SCRIPT = SKILL_DIR / "scripts/product_audit.py"
sys.path.insert(0, str(SKILL_DIR / "scripts"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import product_audit  # noqa: E402
from fixtures.additional import (  # noqa: E402
    PRODUCT_AUDIT_REPORT,
    build_product_audit_bloat,
    build_product_audit_focused,
)

GIT_ENV = {
    **os.environ,
    "GIT_AUTHOR_NAME": "fixture",
    "GIT_AUTHOR_EMAIL": "fixture@example.com",
    "GIT_COMMITTER_NAME": "fixture",
    "GIT_COMMITTER_EMAIL": "fixture@example.com",
}
PLANTED_VALUE = "planted-" + "value-9f3c1b7e"


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


def run(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args], env=GIT_ENV, capture_output=True, text=True, check=False
    )


def scan(root: Path, *extra: str) -> dict:
    completed = run("scan", "--root", str(root), *extra)
    if completed.returncode != 0:
        raise AssertionError(completed.stderr)
    return json.loads(completed.stdout)


def tree_digest(root: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(root.rglob("*")):
        if ".git" in path.parts:
            continue
        digest.update(path.relative_to(root).as_posix().encode())
        if path.is_file() and not path.is_symlink():
            digest.update(path.read_bytes())
    return digest.hexdigest()


def routes(inventory: dict) -> list[str]:
    return [screen.get("route") for screen in inventory["surface"]["screens"]["items"]]


def next_manifest(*dependencies: str) -> str:
    return json.dumps({"name": "fixture", "dependencies": {name: "^1" for name in dependencies}}) + "\n"


class ScanPlantedProductTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.temp = tempfile.TemporaryDirectory()
        cls.root = Path(cls.temp.name) / "streakly"
        build_product_audit_bloat(cls.root)
        cls.inventory = scan(cls.root)

    @classmethod
    def tearDownClass(cls) -> None:
        cls.temp.cleanup()

    def test_schema_and_purpose_sources(self) -> None:
        self.assertEqual(self.inventory["schema"], "product-audit-scan/v1")
        sources = {source["kind"]: source for source in self.inventory["purpose_sources"]}
        self.assertIn("simple daily habit tracker", sources["readme"]["opening"])
        self.assertNotIn("AI assistants", sources["readme"]["opening"])
        self.assertEqual(sources["manifest"]["description"], "A simple daily habit tracker")
        self.assertEqual(sources["page-metadata"]["title"], "Streakly")
        claims = [claim["text"] for claim in self.inventory["claimed_features"]["items"]]
        self.assertEqual(claims, ["Track daily habits", "See your current streak", "Reminders (coming soon)"])

    def test_recalls_every_planted_screen_endpoint_and_model(self) -> None:
        self.assertEqual({"next", "prisma", "react"}, set(self.inventory["stack"]))
        self.assertEqual(
            sorted(routes(self.inventory)),
            sorted([
                "/", "/friends", "/habits", "/habits/[id]", "/journal", "/login", "/recipes",
                "/recipes/[id]", "/recipes/new", "/settings", "/stats", "/today",
            ]),
        )
        endpoints = {(e["method"], e["route"]) for e in self.inventory["surface"]["endpoints"]["items"]}
        self.assertIn(("POST", "/api/recipes/suggest"), endpoints)
        self.assertIn(("GET", "/api/export"), endpoints)
        self.assertIn(("POST", "/api/settings"), endpoints)
        self.assertEqual(len(endpoints), 10)
        models = [model["name"] for model in self.inventory["surface"]["data_models"]["items"]]
        self.assertEqual(models, ["Checkin", "Habit", "Ingredient", "JournalEntry", "Recipe", "User"])
        self.assertEqual(self.inventory["coverage"]["screens"], 12)
        self.assertTrue(self.inventory["coverage"]["recognized"])

    def test_reports_integrations_navigation_and_settings_weight(self) -> None:
        integrations = {i["service"]: i for i in self.inventory["surface"]["integrations"]}
        self.assertEqual({(i["service"], i["kind"]) for i in integrations.values()}, {("OpenAI", "ai"), ("Auth provider", "auth")})
        self.assertEqual(integrations["OpenAI"]["imported_by_files"], 1)
        self.assertEqual(integrations["Auth provider"]["imported_by_files"], 2)
        self.assertEqual(
            self.inventory["surface"]["settings"]["environment_variables"]["items"],
            [{"name": "OPENAI_API_KEY", "path": "app/api/recipes/suggest/route.ts"}],
        )
        navigation = self.inventory["surface"]["navigation"]
        self.assertEqual(navigation[0]["path"], "components/Sidebar.tsx")
        self.assertEqual(navigation[0]["destinations"], 7)
        self.assertTrue(navigation[0]["named_like_navigation"])
        settings = self.inventory["surface"]["settings"]["settings_screens"]
        self.assertEqual(settings[0]["path"], "app/settings/page.tsx")
        self.assertEqual(settings[0]["total"], 14)
        self.assertEqual(settings[0]["toggles"], 10)
        self.assertEqual(settings[0]["settings"], 13)  # the save button is a control, not a setting
        self.assertEqual(self.inventory["signals"]["dense_ui_files"][0]["path"], "app/settings/page.tsx")

    def test_leads_point_at_the_dead_and_the_unfinished_surface(self) -> None:
        unlinked = self.inventory["signals"]["unlinked_screens"]["items"]
        self.assertEqual([item["route"] for item in unlinked], ["/stats"])
        markers = self.inventory["signals"]["unfinished_markers"]["items"]
        self.assertEqual([(m["path"], m["line"]) for m in markers], [("app/friends/page.tsx", 2)])
        self.assertEqual(self.inventory["signals"]["usage_evidence"]["analytics"], [])
        linked = {s["route"]: s["linked_from"] for s in self.inventory["surface"]["screens"]["items"]}
        self.assertIsNone(linked["/"])
        self.assertEqual(linked["/habits/[id]"], 1)  # app/habits/page.tsx builds /habits/${id}
        self.assertEqual(linked["/recipes/[id]"], 1)
        self.assertGreaterEqual(linked["/recipes"], 2)

    def test_history_is_measured_from_the_newest_commit(self) -> None:
        history = self.inventory["history"]
        self.assertEqual(history["head_date"], "2026-06-20")
        self.assertEqual(history["first_commit_date"], "2025-09-10")
        self.assertEqual((history["commits"], history["recent_commits"]), (9, 7))
        self.assertFalse(history["shallow"])
        self.assertFalse(any(key.startswith("_") for key in history))
        added = {s["route"]: s["added"] for s in self.inventory["surface"]["screens"]["items"]}
        self.assertEqual(added["/today"], "2025-09-10")
        self.assertEqual(added["/recipes"], "2026-04-03")
        self.assertEqual(added["/friends"], "2026-06-20")
        narrow = scan(self.root, "--window-days", "30")
        self.assertEqual(narrow["history"]["recent_commits"], 2)

    def test_growth_and_areas_show_where_the_work_went(self) -> None:
        latest = self.inventory["growth"]["by_quarter"][-1]
        self.assertEqual(latest["quarter"], "2026-Q2")
        self.assertEqual((latest["commits"], latest["screens"], latest["endpoints"]), (6, 4, 3))
        models_by_quarter = {row["quarter"]: row["data_models"] for row in self.inventory["growth"]["by_quarter"]}
        self.assertEqual(models_by_quarter, {"2025-Q3": 3, "2025-Q4": 0, "2026-Q1": 1, "2026-Q2": 2})
        areas = {area["path"]: area for area in self.inventory["areas"]["items"]}
        self.assertEqual(areas["app/recipes"]["added"], "2026-04-03")
        self.assertEqual(areas["app/recipes"]["recent_commits"], 3)
        self.assertEqual(areas["app/habits"]["recent_commits"], 0)
        self.assertEqual(self.inventory["areas"]["window_days"], 180)

    def test_items_sharing_a_file_are_dated_by_their_own_line(self) -> None:
        models = {model["name"]: model for model in self.inventory["surface"]["data_models"]["items"]}
        self.assertEqual(models["Habit"]["added"], "2025-09-10")
        self.assertEqual(models["JournalEntry"]["added"], "2026-01-20")
        self.assertEqual(models["Recipe"]["added"], "2026-04-03")
        self.assertEqual(models["Recipe"]["dated_by"], "line")
        self.assertNotIn("commits", models["Recipe"])  # a file-level count would mislead
        endpoints = {(e["method"], e["route"]): e for e in self.inventory["surface"]["endpoints"]["items"]}
        alone = endpoints[("POST", "/api/checkins")]
        self.assertNotIn("dated_by", alone)
        self.assertEqual((alone["added"], alone["commits"], alone["line"]), ("2025-09-10", 1, 4))

    def test_recent_commits_say_what_each_one_touched(self) -> None:
        log = self.inventory["recent_commits"]
        self.assertEqual(log["total"], 7)
        self.assertEqual(log["items"][0], {
            "date": "2026-06-20", "subject": "friends feed placeholder", "touched": ["app/friends", "components"],
        })
        self.assertEqual(log["items"][-1]["subject"], "journal and stats")
        recipes = [entry for entry in log["items"] if any("recipes" in path for path in entry["touched"])]
        self.assertEqual(len(recipes), 4)

    def test_scan_changes_nothing_and_never_opens_environment_files(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "streakly"
            build_product_audit_bloat(root)
            env_files = (".env", ".env.local", "production.env", "config/.env.production")
            for name in env_files:
                write(root, name, f"SERVICE_KEY={PLANTED_VALUE}\n")
            before = tree_digest(root)
            completed = run("scan", "--root", str(root))
            self.assertEqual(completed.returncode, 0, completed.stderr)
            self.assertEqual(tree_digest(root), before)
            self.assertNotIn(PLANTED_VALUE, completed.stdout)
            self.assertNotIn(PLANTED_VALUE, completed.stderr)

            opened: list[str] = []
            original = product_audit.read_text

            def recording(path: Path) -> str | None:
                opened.append(path.relative_to(root).as_posix())
                return original(path)

            product_audit.read_text = recording
            try:
                product_audit.scan(root, 180)
            finally:
                product_audit.read_text = original
            self.assertIn("README.md", opened)
            self.assertEqual([name for name in opened if name in env_files], [])

    def test_out_inside_the_project_must_use_the_reserved_name(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "pace"
            build_product_audit_focused(root)
            refused = run("scan", "--root", str(root), "--out", str(root / "scan.json"))
            self.assertEqual(refused.returncode, 1)
            self.assertIn(".product-audit-scan.json", refused.stderr)
            self.assertFalse((root / "scan.json").exists())
            allowed = run("scan", "--root", str(root), "--out", str(root / ".product-audit-scan.json"))
            self.assertEqual(allowed.returncode, 0, allowed.stderr)
            self.assertTrue(json.loads(allowed.stdout)["ok"])
            written = json.loads((root / ".product-audit-scan.json").read_text(encoding="utf-8"))
            self.assertEqual(written["coverage"]["screens"], 2)
            outside = run("scan", "--root", str(root), "--out", str(Path(temp) / "anything.json"))
            self.assertEqual(outside.returncode, 0, outside.stderr)


class ScanConventionTests(unittest.TestCase):
    def test_a_focused_product_produces_no_leads(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "pace"
            build_product_audit_focused(root)
            inventory = scan(root)
            self.assertEqual(routes(inventory), ["/", "/splits"])
            self.assertEqual(inventory["signals"]["unlinked_screens"]["total"], 0)
            self.assertEqual(inventory["signals"]["unfinished_markers"]["total"], 0)
            self.assertEqual(inventory["surface"]["integrations"], [])
            self.assertEqual(inventory["surface"]["settings"]["settings_screens"], [])
            self.assertEqual(inventory["surface"]["navigation"], [])

    def test_a_renamed_screen_keeps_its_original_arrival_date(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            write(root, "package.json", next_manifest("next", "react"))
            write(root, "app/reports/page.tsx", "export default function Reports() {\n  return <p>Reports</p>;\n}\n")
            git(root, "init", "-q", "-b", "main")
            git(root, "add", "-A")
            git(root, "commit", "-qm", "reports", date="2025-01-10T10:00:00")
            git(root, "mv", "app/reports", "app/insights")
            git(root, "commit", "-qm", "rename reports to insights", date="2026-03-01T10:00:00")
            inventory = scan(root)
            screen = inventory["surface"]["screens"]["items"][0]
            self.assertEqual(screen["route"], "/insights")
            self.assertEqual(screen["added"], "2025-01-10")
            self.assertEqual(screen["last_touched"], "2026-03-01")
            self.assertEqual(screen["commits"], 2)

    def test_without_git_the_surface_is_still_inventoried(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            write(root, "package.json", next_manifest("next", "react"))
            write(root, "app/page.tsx", "export default function Home() {\n  return <p>Home</p>;\n}\n")
            inventory = scan(root)
            self.assertFalse(inventory["history"]["available"])
            self.assertFalse(inventory["growth"]["available"])
            self.assertEqual(routes(inventory), ["/"])
            self.assertNotIn("added", inventory["surface"]["screens"]["items"][0])
            self.assertNotIn("commits", inventory["areas"]["items"][0])

    def test_an_unrecognized_stack_says_so_instead_of_reporting_nothing(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            write(root, "README.md", "# Gridlock\n\nGridlock is a puzzle game about parking cars in a crowded lot.\n")
            write(root, "src/main.c", "int main(void) {\n  return 0;\n}\n")
            inventory = scan(root)
            self.assertFalse(inventory["coverage"]["recognized"])
            self.assertIn("Inventory the surface by reading", inventory["coverage"]["note"])
            self.assertIn("puzzle game", inventory["purpose_sources"][0]["opening"])

    def test_server_command_and_model_conventions(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            write(root, "requirements.txt", "flask>=3\nclick\nstripe==9.1\nposthog\n# comment\n")
            write(
                root,
                "pyproject.toml",
                '[project]\nname = "notes"\ndescription = "Notes from the terminal"\n\n[project.scripts]\nnotes = "cli:main"\n',
            )
            write(
                root,
                "api/app.py",
                'from flask import Blueprint\n\nbp = Blueprint("notes", __name__, url_prefix="/notes")\n\n\n'
                '@bp.route("/", methods=["GET", "POST"])\ndef index():\n    return ""\n\n\n'
                '@bp.get("/<note_id>")\ndef show(note_id):\n    return ""\n',
            )
            write(
                root,
                "server/index.js",
                'const app = require("express")();\nconst itemsRouter = require("express").Router();\n'
                'app.get("/health", (req, res) => res.end());\n'
                'itemsRouter.post("/items", (req, res) => res.end());\n'
                'const api = require("axios").create();\napi.get("/users");\nrequire("axios").get("/remote");\n',
            )
            write(
                root,
                "cli.py",
                "import argparse\nimport click\n\n\n@click.group()\ndef cli():\n    pass\n\n\n"
                "@cli.command()\n@click.option(\"--dry-run\", is_flag=True)\ndef export_data(dry_run):\n    pass\n\n\n"
                '@cli.command("sync")\ndef run_sync():\n    pass\n\n\n'
                'def legacy():\n    parser = argparse.ArgumentParser()\n    sub = parser.add_subparsers()\n'
                '    sub.add_parser("migrate").add_argument("--force")\n',
            )
            write(
                root,
                "db/models.py",
                "from django.db import models\n\n\nclass Note(models.Model):\n    text = models.TextField()\n\n\n"
                'class Tag:\n    __tablename__ = "tags"\n',
            )
            write(root, "db/schema.sql", "CREATE TABLE IF NOT EXISTS notes (id integer);\nCREATE TABLE schema_migrations (v text);\n")
            inventory = scan(root)
            endpoints = {(e["method"], e["route"]) for e in inventory["surface"]["endpoints"]["items"]}
            self.assertEqual(
                endpoints,
                {("GET", "/notes/"), ("POST", "/notes/"), ("GET", "/notes/<note_id>"), ("GET", "/health"), ("POST", "/items")},
            )
            commands = {(c["name"], c["kind"]) for c in inventory["surface"]["commands"]["items"]}
            self.assertEqual(
                commands,
                {("export-data", "click-command"), ("sync", "click-command"), ("migrate", "argparse"), ("notes", "executable")},
            )
            options = inventory["surface"]["settings"]["command_options"]["items"]
            self.assertEqual(options, ["--dry-run", "--force"])
            models = inventory["surface"]["data_models"]
            self.assertEqual([m["name"] for m in models["items"]], ["Note", "tags"])
            self.assertEqual(models["sql_tables_folded_into_orm_models"], 1)
            self.assertEqual(inventory["signals"]["usage_evidence"]["analytics"], ["posthog"])
            integrations = {i["service"]: i for i in inventory["surface"]["integrations"]}
            self.assertEqual(integrations["Stripe"]["kind"], "payments")
            # Python import names differ from package names, so "not imported" is left unsaid.
            self.assertIsNone(integrations["Stripe"]["imported_by_files"])
            self.assertIn("ask the owner for the numbers", inventory["signals"]["usage_evidence"]["note"])

    def test_declared_routes_merge_with_their_screen_files(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            write(root, "package.json", next_manifest("react", "react-dom", "react-router-dom"))
            for name in ("Home", "Reports", "Orphan"):
                write(root, f"src/pages/{name}.tsx", f"export function {name}() {{\n  return <p>{name}</p>;\n}}\n")
            write(
                root,
                "src/App.tsx",
                'import { Routes, Route } from "react-router-dom";\nimport { Home } from "./pages/Home";\n'
                'import { Reports } from "./pages/Reports";\n\nexport function App() {\n  return (\n    <Routes>\n'
                '      <Route path="/" element={<Home />} />\n'
                '      <Route path="/reports" element={<Reports />} />\n'
                '      <Route path="*" element={<Home />} />\n'
                "    </Routes>\n  );\n}\n",
            )
            write(
                root,
                "src/components/Nav.tsx",
                'import { Link } from "react-router-dom";\n\nexport function Nav() {\n'
                '  return <nav><Link to="/">Home</Link><Link to="/reports">Reports</Link></nav>;\n}\n',
            )
            inventory = scan(root)
            screens = {s["path"]: s for s in inventory["surface"]["screens"]["items"]}
            self.assertEqual(set(screens), {"src/pages/Home.tsx", "src/pages/Reports.tsx", "src/pages/Orphan.tsx"})
            self.assertEqual(screens["src/pages/Reports.tsx"]["route"], "/reports")
            self.assertEqual(screens["src/pages/Reports.tsx"]["linked_from"], 1)
            self.assertEqual(screens["src/pages/Home.tsx"]["route"], "/")
            self.assertIsNone(screens["src/pages/Orphan.tsx"]["route"])
            self.assertEqual(
                [item["path"] for item in inventory["signals"]["unlinked_screens"]["items"]],
                ["src/pages/Orphan.tsx"],
            )
            self.assertEqual(inventory["surface"]["navigation"][0]["path"], "src/components/Nav.tsx")

    def test_dynamic_routes_and_declared_dependencies_are_checked_for_use(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            write(root, "package.json", next_manifest("next", "react", "stripe", "posthog-js"))
            write(root, "app/page.tsx", 'import posthog from "posthog-js";\n\nexport default function Home() {\n  return <a href="/items/new">New</a>;\n}\n')
            write(root, "app/items/new/page.tsx", "export default function New() {\n  return null;\n}\n")
            write(root, "app/items/[id]/page.tsx", "export default function Item() {\n  return null;\n}\n")
            write(root, "app/orders/[id]/page.tsx", "export default function Order() {\n  return null;\n}\n")
            write(root, "app/orders/list.tsx", "export function List({ orders }) {\n  return orders.map((o) => <a href={`/orders/${o.id}`}>{o.id}</a>);\n}\n")
            inventory = scan(root)
            linked = {s["route"]: s["linked_from"] for s in inventory["surface"]["screens"]["items"]}
            self.assertEqual(linked["/orders/[id]"], 1)
            self.assertEqual(linked["/items/[id]"], 0)  # /items/new is a sibling, not a link into it
            self.assertEqual(linked["/items/new"], 1)
            # Dynamic routes stay out of the lead list: their links often come from data.
            self.assertEqual(inventory["signals"]["unlinked_screens"]["total"], 0)
            integrations = {i["service"]: i["imported_by_files"] for i in inventory["surface"]["integrations"]}
            self.assertEqual(integrations, {"Stripe": 0, "Product analytics": 1})

    def test_layouts_colocated_components_and_content_folders_are_not_screens(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            write(root, "kit/package.json", json.dumps({"devDependencies": {"@sveltejs/kit": "^2", "svelte": "^5"}}))
            write(root, "kit/src/routes/+page.svelte", "<h1>Home</h1>\n")
            write(root, "kit/src/routes/+layout.svelte", "<slot />\n")
            write(root, "kit/src/routes/Nav.svelte", "<nav></nav>\n")
            write(root, "kit/src/routes/(app)/items/[id]/+page.svelte", "<h1>Item</h1>\n")
            write(root, "kit/src/routes/api/items/+server.ts", "export const GET = () => new Response();\n")
            write(root, "web/package.json", next_manifest("next", "react"))
            write(root, "web/app/@modal/(.)photo/page.tsx", "export default function Photo() {\n  return null;\n}\n")
            write(root, "web/app/layout.tsx", "export default function Layout() {\n  return null;\n}\n")
            write(root, "web/content/pages/privacy.mdx", "# Privacy\n")
            write(root, "spa/package.json", next_manifest("react", "@tanstack/react-router"))
            write(root, "spa/src/routes/_layout.tsx", "export const Route = {};\n")
            write(root, "spa/src/routes/_layout/items.tsx", "export const Route = {};\n")
            write(root, "spa/src/routes/__root.tsx", "export const Route = {};\n")
            inventory = scan(root)
            found = {(s["path"], s["route"]) for s in inventory["surface"]["screens"]["items"]}
            self.assertEqual(
                found,
                {
                    ("kit/src/routes/+page.svelte", "/"),
                    ("kit/src/routes/(app)/items/[id]/+page.svelte", "/items/[id]"),
                    ("web/app/@modal/(.)photo/page.tsx", "/photo"),
                    ("spa/src/routes/_layout/items.tsx", "/items"),
                },
            )
            endpoints = {(e["method"], e["route"], e["kind"]) for e in inventory["surface"]["endpoints"]["items"]}
            self.assertEqual(endpoints, {("GET", "/api/items", "sveltekit")})

    def test_tests_examples_and_documentation_are_not_product_surface(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            write(root, "package.json", next_manifest("next", "react"))
            write(root, "app/page.tsx", "export default function Home() {\n  return <p>Home</p>;\n}\n")
            write(root, "examples/demo/app/page.tsx", "export default function Demo() {\n  return <p>coming soon</p>;\n}\n")
            write(root, "tests/app/page.test.tsx", "test('home', () => {});\n")
            write(root, "docs/app/guide/page.tsx", "export default function Guide() {\n  return null;\n}\n")
            inventory = scan(root)
            self.assertEqual(routes(inventory), ["/"])
            self.assertEqual(inventory["signals"]["unfinished_markers"]["total"], 0)
            self.assertEqual(inventory["weight"]["source_files"], 1)

    def test_a_plugin_collection_is_inventoried_as_packages(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            write(
                root,
                "README.md",
                '<p align="center"><img src="assets/hero.png" alt="hero"></p>\n\n<h1 align="center">Kit</h1>\n\n'
                '<p align="center"><strong>Skills that keep your drafts honest, short, and in your own voice.</strong></p>\n\n'
                "## Quick start\n\nRun these commands inside the host to install the first plugin:\n",
            )
            write(root, ".claude-plugin/marketplace.json", json.dumps({"name": "kit", "description": "A kit of agent skills for writing."}))
            write(root, "plugins/alpha/.claude-plugin/plugin.json", json.dumps({"name": "alpha", "description": "Draft with discipline."}))
            write(
                root,
                "plugins/alpha/skills/draft/SKILL.md",
                "---\nname: draft\ndescription: >\n  Draft long prose in the author's voice.\n  Use when asked to write.\n"
                'argument-hint: "[topic]"\ndisable-model-invocation: true\n---\n\n# Draft\n',
            )
            write(
                root,
                "plugins/alpha/skills/draft/scripts/helper.py",
                'import argparse\n\nparser = argparse.ArgumentParser()\nparser.add_subparsers().add_parser("outline")\n'
                'parser.add_argument("--depth")\n',
            )
            write(root, "plugins/alpha/hooks/hooks.json", "{}\n")
            write(root, ".ai/loop-backlog.md", "# Backlog\n")
            write(root, "docs/q3-plan.md", "# Plan\n")
            write(root, "docs/planets.md", "# Not a plan\n")
            write(root, "CHANGELOG.md", "# Changelog\n")
            write(root, ".claude/skills/local/SKILL.md", "---\nname: local\ndescription: The developer's own helper.\n---\n")
            write(root, "qa/experiments/trial/skills/trial/SKILL.md", "---\nname: trial\ndescription: Unpublished.\n---\n")
            write(root, "scripts/release.py", 'import argparse\n\nargparse.ArgumentParser().add_subparsers().add_parser("publish")\n')
            write(root, "packages/ui/package.json", json.dumps({"name": "@kit/ui", "description": "Shared buttons"}))
            write(root, "package.json", json.dumps({"name": "kit-root", "private": True}))
            git(root, "init", "-q", "-b", "main")
            git(root, "add", "-A")
            git(root, "commit", "-qm", "alpha", date="2026-01-10T10:00:00")
            write(root, "plugins/beta/.claude-plugin/plugin.json", json.dumps({"name": "beta", "description": "Edit with restraint."}))
            write(root, "plugins/beta/skills/edit/SKILL.md", '---\nname: edit\ndescription: "Tighten a draft. Use when asked to edit."\n---\n')
            git(root, "add", "-A")
            git(root, "commit", "-qm", "beta", date="2026-05-02T10:00:00")

            inventory = scan(root)
            sources = {source["path"]: source for source in inventory["purpose_sources"]}
            self.assertEqual(sources["README.md"]["title"], "Kit")
            self.assertEqual(sources["README.md"]["opening"], "Skills that keep your drafts honest, short, and in your own voice.")
            self.assertEqual(sources[".claude-plugin/marketplace.json"]["description"], "A kit of agent skills for writing.")

            packages = {(p["kind"], p["name"]): p for p in inventory["surface"]["packages"]["items"]}
            self.assertEqual(
                set(packages),
                {("plugin", "alpha"), ("agent-skill", "draft"), ("plugin", "beta"), ("agent-skill", "edit"), ("package", "@kit/ui")},
            )
            draft = packages[("agent-skill", "draft")]
            self.assertTrue(draft["user_invoked"])
            self.assertEqual(draft["description"], "Draft long prose in the author's voice. Use when asked to write.")
            self.assertEqual(draft["added"], "2026-01-10")
            self.assertFalse(packages[("agent-skill", "edit")]["user_invoked"])
            self.assertEqual(packages[("agent-skill", "edit")]["added"], "2026-05-02")
            self.assertEqual(inventory["coverage"]["packages"], 5)
            self.assertTrue(inventory["coverage"]["recognized"])
            quarters = {row["quarter"]: row["packages"] for row in inventory["growth"]["by_quarter"]}
            self.assertEqual(quarters, {"2026-Q1": 3, "2026-Q2": 2})

            self.assertEqual(draft["plugin"], "alpha")
            self.assertEqual(draft["argument_hint"], "[topic]")
            self.assertTrue(packages[("plugin", "alpha")]["has_hooks"])
            self.assertFalse(packages[("plugin", "beta")]["has_hooks"])

            # A skill's bundled helper counts as shipped code, but the agent runs it: its
            # subcommands and flags are not commands a user types. Developer scripts are neither.
            self.assertEqual(inventory["surface"]["commands"]["items"], [])
            self.assertEqual(inventory["surface"]["settings"]["command_options"]["items"], [])
            self.assertEqual(inventory["weight"]["source_files"], 1)
            self.assertEqual(inventory["direction_documents"], [".ai/loop-backlog.md", "docs/q3-plan.md"])
            self.assertEqual(inventory["release_notes"], ["CHANGELOG.md"])
            areas = {area["path"]: area for area in inventory["areas"]["items"]}
            self.assertNotIn("non_product", areas["plugins/alpha"])
            self.assertTrue(areas["scripts"]["non_product"])
            self.assertTrue(areas["qa"]["non_product"])
            self.assertEqual(areas["plugins/alpha"]["added"], "2026-01-10")
            self.assertEqual(areas["plugins/beta"]["added"], "2026-05-02")
            self.assertIn("plugins/alpha/skills", areas)
            self.assertNotIn("plugins/alpha/skills/draft", areas)  # its parent holds nothing else
            self.assertFalse(any(path.startswith(".") for path in areas))

    def test_readme_opening_is_the_statement_of_purpose_not_setup_text(self) -> None:
        cases = [
            ("# Tool\n\n[![build](https://x/b.svg)](https://x)\n\nTool turns messy spreadsheets into tidy CSV files.\n\n## Install\n", "Tool", "Tool turns messy spreadsheets into tidy CSV files."),
            ("# ![Tool logo](logo.png)\n\n> ### Tool turns messy spreadsheets into tidy CSV files.\n\n## Install\n\nRun the installer and wait for it to finish.\n", "Tool logo", "Tool turns messy spreadsheets into tidy CSV files."),
            ("# Tool\n\n## Install\n\nRun the installer and wait for it to finish.\n\n## About\n\nTool turns messy spreadsheets into tidy CSV files.\n", "Tool", "Tool turns messy spreadsheets into tidy CSV files."),
            ("# Tool\n\n## Install\n\nRun the installer and wait for it to finish.\n", "Tool", None),
            ("Tool turns messy spreadsheets into tidy CSV files.\n", None, "Tool turns messy spreadsheets into tidy CSV files."),
        ]
        for text, title, opening in cases:
            with self.subTest(text=text[:40]):
                self.assertEqual(product_audit.readme_purpose(text), (title, opening))

    def test_marker_definitions_are_not_markers_and_each_line_counts_once(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            write(root, "package.json", next_manifest("next", "react"))
            write(
                root,
                "app/page.tsx",
                "// TODO wire the real data\n"
                'const MARKERS = /coming soon|not implemented|under construction/;\n'
                'const NOTES = /TODO|FIXME|HACK/;\n'
                "export default function Home() {\n"
                "  return <p>Coming soon, coming soon</p>;\n}\n",
            )
            inventory = scan(root)
            markers = inventory["signals"]["unfinished_markers"]["items"]
            self.assertEqual([(m["path"], m["line"]) for m in markers], [("app/page.tsx", 5)])
            self.assertEqual(inventory["signals"]["todos_in_surface_files"]["items"], [{"path": "app/page.tsx", "count": 1}])

    def test_uncommitted_work_is_counted_so_the_reader_knows_the_tree_moved(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "pace"
            build_product_audit_focused(root)
            self.assertEqual(scan(root)["history"]["uncommitted"], {"modified": 0, "untracked": 0})
            write(root, "app/extra/page.tsx", "export default function Extra() {\n  return null;\n}\n")
            with (root / "README.md").open("a", encoding="utf-8") as handle:
                handle.write("\nEdited.\n")
            written = run("scan", "--root", str(root), "--out", str(root / ".product-audit-scan.json"))
            self.assertEqual(written.returncode, 0, written.stderr)
            inventory = scan(root)
            # The scan's own output file is not the owner's work.
            self.assertEqual(inventory["history"]["uncommitted"], {"modified": 1, "untracked": 1})
            extra = next(s for s in inventory["surface"]["screens"]["items"] if s["route"] == "/extra")
            self.assertIsNone(extra["added"])

    def test_a_commit_touching_many_places_says_how_many_are_not_listed(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            for index in range(13):
                write(root, f"area{index:02d}/file.py", "x = 1\n")
            git(root, "init", "-q", "-b", "main")
            git(root, "add", "-A")
            git(root, "commit", "-qm", "everything at once", date="2026-02-01T10:00:00")
            entry = scan(root)["recent_commits"]["items"][0]
            self.assertEqual(len(entry["touched"]), 10)
            self.assertEqual(entry["more_places"], 3)

    def test_symlinks_are_not_followed(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            outside = Path(temp) / "outside"
            leak = f"export default function Leak() {{\n  return <p>coming soon {PLANTED_VALUE}</p>;\n}}\n"
            write(outside, "page.tsx", leak)
            write(outside, "nested/page.tsx", leak)
            root = Path(temp) / "project"
            write(root, "package.json", next_manifest("next", "react"))
            write(root, "app/page.tsx", "export default function Home() {\n  return <p>Home</p>;\n}\n")
            (root / "app/file-link").mkdir()
            (root / "app/file-link/page.tsx").symlink_to(outside / "page.tsx")
            (root / "app/dir-link").symlink_to(outside / "nested", target_is_directory=True)
            completed = run("scan", "--root", str(root))
            self.assertEqual(completed.returncode, 0, completed.stderr)
            self.assertNotIn(PLANTED_VALUE, completed.stdout)
            inventory = json.loads(completed.stdout)
            self.assertEqual(routes(inventory), ["/"])
            self.assertEqual(inventory["signals"]["unfinished_markers"]["total"], 0)

    def test_long_lists_are_capped_and_say_so(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            write(root, "package.json", next_manifest("next", "react"))
            for index in range(230):
                write(root, f"app/item{index:03d}/page.tsx", "export default function Item() {\n  return null;\n}\n")
            screens = scan(root)["surface"]["screens"]
            self.assertEqual((screens["total"], len(screens["items"]), screens["truncated"]), (230, 200, True))

    def test_bad_arguments_fail_closed(self) -> None:
        missing = run("scan", "--root", "/nonexistent/product-audit-root")
        self.assertEqual(missing.returncode, 1)
        self.assertIn("root is not a directory", missing.stderr)
        with tempfile.TemporaryDirectory() as temp:
            window = run("scan", "--root", temp, "--window-days", "0")
            self.assertEqual(window.returncode, 1)
            self.assertIn("--window-days must be positive", window.stderr)


class ReportCheckTests(unittest.TestCase):
    def check(self, text: str) -> subprocess.CompletedProcess:
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "PRODUCT-AUDIT.md"
            path.write_text(text, encoding="utf-8")
            return run("check", "--report", str(path))

    def assert_rejects(self, text: str, expected: str) -> None:
        completed = self.check(text)
        self.assertEqual(completed.returncode, 1, completed.stdout)
        self.assertIn(expected, completed.stderr)

    def edit(self, old: str, new: str) -> str:
        self.assertEqual(PRODUCT_AUDIT_REPORT.count(old), 1, old)
        return PRODUCT_AUDIT_REPORT.replace(old, new)

    def test_a_complete_report_passes_with_a_summary(self) -> None:
        completed = self.check(PRODUCT_AUDIT_REPORT)
        self.assertEqual(completed.returncode, 0, completed.stderr)
        summary = json.loads(completed.stdout)
        self.assertEqual(summary["features"], 11)
        self.assertEqual(summary["verdicts"], {"keep": 5, "simplify": 1, "park": 2, "cut": 3})
        self.assertEqual(summary["pending_decisions"], [])
        self.assertEqual((summary["direction"], summary["outside_view"], summary["audits"]), ("drifting", "not run", 1))
        self.assertEqual((summary["next"], summary["then"]), (["N1"], ["N2", "N3", "N4"]))

    def test_the_unfilled_template_is_rejected(self) -> None:
        template = (SKILL_DIR / "templates/report.md").read_text(encoding="utf-8")
        completed = self.check(template)
        self.assertEqual(completed.returncode, 1)
        self.assertIn("template placeholder left in report", completed.stderr)
        self.assertIn("History needs one dated line per audit", completed.stderr)
        self.assertIn("template guidance left in report", completed.stderr)
        self.assert_rejects(
            self.edit("## 4. Complexity\n", "## 4. Complexity\n\n<!-- guide: at most five findings -->\n"),
            "template guidance left in report",
        )
        self.assert_rejects(self.edit("| Packages | 0 |\n", ""), "Snapshot is missing the measure 'Packages'")

    def test_structure_is_required(self) -> None:
        self.assert_rejects(self.edit("<!-- product-audit: v1 -->\n", ""), "missing report marker")
        self.assert_rejects(self.edit("## 8. History", "## 8. Past"), "missing section: History")
        self.assert_rejects(self.edit("Source: README.md, package.json\n", ""), "needs a 'Source:' line")
        missing = run("check", "--report", "/nonexistent/PRODUCT-AUDIT.md")
        self.assertEqual(missing.returncode, 1)
        self.assertIn("report not found", missing.stderr)

    def test_cut_requires_usage_evidence(self) -> None:
        text = self.edit(
            "| light | owner: never | cut | cut | owner |\n| F8 |",
            "| light | unknown | cut | pending | — |\n| F8 |",
        )
        self.assert_rejects(text, "F7: cut needs usage evidence; with usage unknown the verdict is park")

    def test_a_core_feature_cannot_be_parked_or_cut(self) -> None:
        text = self.edit(
            "| light | owner: regular | keep | keep | audit |\n| F4 |",
            "| light | owner: never | cut | pending | — |\n| F4 |",
        )
        self.assert_rejects(text, "F3: a core feature cannot be parked or cut")

    def test_only_the_owner_decides_a_change(self) -> None:
        text = self.edit("| owner: rare | simplify | simplify | owner |", "| owner: rare | simplify | simplify | audit |")
        self.assert_rejects(text, "F5: only the owner decides anything other than keeping")
        text = self.edit("| owner: rare | simplify | simplify | owner |", "| owner: rare | simplify | pending | owner |")
        self.assert_rejects(text, "F5: a pending decision has no decider")
        text = self.edit("| owner: rare | simplify | simplify | owner |", "| owner: rare | simplify | simplify | — |")
        self.assert_rejects(text, "F5: decided by")
        delegated = self.edit("| owner: rare | simplify | simplify | owner |", "| owner: rare | simplify | park | owner-delegated |")
        self.assertEqual(self.check(delegated).returncode, 0)

    def test_pending_decisions_are_reported_not_rejected(self) -> None:
        text = self.edit("| owner: rare | park | park | owner |", "| unknown | park | pending | — |")
        completed = self.check(text)
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual(json.loads(completed.stdout)["pending_decisions"], ["F6"])

    def test_fixed_scales_are_enforced(self) -> None:
        self.assert_rejects(self.edit("| F9 | Export habits as CSV | adjacent |", "| F9 | Export habits as CSV | nice-to-have |"), "F9: class")
        self.assert_rejects(self.edit("app/api/export/route.ts | light |", "app/api/export/route.ts | tiny |"), "F9: cost")
        self.assert_rejects(self.edit("| owner: rare | simplify |", "| sometimes | simplify |"), "F5: usage")
        self.assert_rejects(self.edit("| owner: rare | simplify | simplify |", "| owner: rare | trim | simplify |"), "F5: verdict")
        self.assert_rejects(self.edit("| app/api/export/route.ts |", "| — |"), "F9: evidence column is empty")
        measured = self.edit("| owner: rare | simplify |", "| measured: 3 opens in 90 days | simplify |")
        self.assertEqual(self.check(measured).returncode, 0)

    def test_snapshot_must_match_the_features_table(self) -> None:
        self.assert_rejects(self.edit("| Core | 3 |", "| Core | 4 |"), "Snapshot 'Core' says 4 but the Features table has 3")
        self.assert_rejects(self.edit("| Screens | 12 |", "| Screens | about a dozen |"), "must be a whole number or n/a")
        self.assert_rejects(self.edit("| Integrations | 2 |\n", ""), "Snapshot is missing the measure 'Integrations'")
        unmeasured = self.edit("| Steps to the core action | 3 |", "| Steps to the core action | n/a |")
        self.assertEqual(self.check(unmeasured).returncode, 0)

    def test_complexity_is_capped_and_never_silently_empty(self) -> None:
        extra = "".join(f"| X{n} | Finding {n} | app/page.tsx | Remove it |\n" for n in (4, 5, 6))
        text = self.edit("| X3 | The menu links", extra + "| X3 | The menu links")
        self.assert_rejects(text, "Complexity is capped at five findings")
        rows = [line for line in PRODUCT_AUDIT_REPORT.splitlines(keepends=True) if line.startswith("| X")]
        empty = PRODUCT_AUDIT_REPORT
        for row in rows:
            empty = empty.replace(row, "")
        empty = empty.replace("- N2 (X1) Open the app on Today\n", "")
        self.assert_rejects(empty, "Complexity with no findings must say 'None.'")
        self.assertEqual(self.check(empty.replace("## 5. Direction", "None.\n\n## 5. Direction")).returncode, 0)
        self.assert_rejects(self.edit("| Remove the entry until the feature exists |", "| |"), "X3: needs a finding, its evidence, and the simpler shape")

    def test_direction_needs_a_verdict_and_a_real_choice(self) -> None:
        self.assert_rejects(self.edit("Verdict: drifting", "Verdict: wandering"), "Direction verdict 'wandering'")
        self.assert_rejects(self.edit("Verdict: drifting\n", ""), "exactly one 'Verdict:' line")
        self.assert_rejects(
            self.edit("- D2 Rename the product a daily-routine companion and make recipes a second core\n", ""),
            "A drifting direction needs at least two options",
        )
        self.assert_rejects(
            self.edit("make recipes a second core", "make recipes a second core (recommended)"),
            "Exactly one option under 'The choice' must be marked (recommended)",
        )
        focused = self.edit("Verdict: drifting", "Verdict: focused")
        focused = focused.replace("- D1 Narrow to the habit tracker: park recipes, cut friends, and open on Today (recommended)\n", "")
        focused = focused.replace("- D2 Rename the product a daily-routine companion and make recipes a second core\n", "None.\n")
        self.assertEqual(self.check(focused).returncode, 0)

    def test_outside_view_rows_need_a_dated_source(self) -> None:
        table = (
            "| ID | Product | Why comparable | What it covers | Source |\n|----|---|---|---|---|\n"
            "| O1 | Habit A | same job, one developer | habits, streaks, reminders | {source} |\n"
        )
        good = self.edit("Not run: no web access\n", table.format(source="https://example.com/features (checked 2026-06-21)"))
        completed = self.check(good)
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual(json.loads(completed.stdout)["outside_view"], "1 products")
        owner = self.edit("Not run: no web access\n", table.format(source="owner"))
        self.assertEqual(self.check(owner).returncode, 0)
        self.assert_rejects(
            self.edit("Not run: no web access\n", table.format(source="their website")),
            "O1: source must be a URL with 'checked YYYY-MM-DD', or 'owner'",
        )
        self.assert_rejects(
            self.edit("Not run: no web access\n", table.format(source="https://example.com/features")),
            "O1: source needs the date it was read",
        )
        self.assert_rejects(
            self.edit("Not run: no web access\n", "Not run: no web access\n\n" + table.format(source="owner")),
            "Outside view says 'Not run' but also lists products",
        )
        self.assert_rejects(self.edit("Not run: no web access\n", ""), "Outside view needs comparable products with sources")
        self.assert_rejects(self.edit("Not run: no web access\n", "Not run:\n"), "'Not run:' needs its reason")

    def test_outside_view_caps_products_gaps_and_checks_readings(self) -> None:
        rows = "".join(f"| O{n} | Product {n} | same job | habits | owner |\n" for n in range(1, 7))
        table = "| ID | Product | Why comparable | What it covers | Source |\n|----|---|---|---|---|\n" + rows
        self.assert_rejects(self.edit("Not run: no web access\n", table), "Outside view is capped at five products")
        base = "| ID | Product | Why comparable | What it covers | Source |\n|----|---|---|---|---|\n| O1 | Product | same job | habits | owner |\n"
        gaps = base + "\n### Gaps\n\n" + "".join(f"- G{n} Is a reminder needed for F2?\n" for n in range(1, 5))
        self.assert_rejects(self.edit("Not run: no web access\n", gaps), "Gaps are capped at three")
        readings = base + "\n### Readings\n\n- (F6) supports: none of them plans meals\n- (F9, F99) contradicts: all of them export\n"
        self.assert_rejects(self.edit("Not run: no web access\n", readings), "a reading cites unknown id F99")
        valid = (
            base + "\nSearched: habit tracker daily check-in app (2 searches, 4 pages)\n"
            "Differentiator: none of them mentions a meal plan\n"
            "\n### Readings\n\n- (F6, F7) supports: none of them plans meals\n- (F10) mixed: two of four chart completion\n"
            "\n### Gaps\n\n- G1 Does the daily check-in need a reminder?\n"
        )
        completed = self.check(self.edit("Not run: no web access\n", valid))
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual(json.loads(completed.stdout)["gaps"], 1)

    def test_next_moves_hold_one_next_and_cite_real_ids(self) -> None:
        self.assert_rejects(
            self.edit("- N1 (F6) Take Recipes out of the menu and off the dashboard\n", "- N1 (F6) Take Recipes out of the menu\n- N5 (F7) Delete friends\n"),
            "Next holds exactly one move",
        )
        self.assert_rejects(self.edit("- N2 (X1) Open the app on Today", "- N2 (X9) Open the app on Today"), "N2 cites unknown id X9")
        self.assert_rejects(
            self.edit("- N4 (F9) Remove the CSV export route and its link in Settings\n", "- N4 (F9) Remove export\n- N5 (F10) Remove stats\n- N6 (F7) Remove friends\n"),
            "Then is capped at four moves",
        )
        self.assert_rejects(self.edit("- N1 (F6) Take Recipes out of the menu and off the dashboard\n", ""), "Next needs one move citing an id")
        self.assert_rejects(self.edit("- N2 (X1) Open the app on Today", "- N2 Open the app on Today"), "malformed move")
        several = self.edit("- N2 (X1) Open the app on Today", "- N2 (X1, X3, F5) Open the app on Today and trim the menu")
        self.assertEqual(self.check(several).returncode, 0)
        self.assert_rejects(
            self.edit("- N2 (X1) Open the app on Today", "- N2 (X1, X9) Open the app on Today"), "N2 cites unknown id X9"
        )
        nothing = self.edit(
            "- N1 (F6) Take Recipes out of the menu and off the dashboard\n",
            "Nothing obvious; next is whatever you decide to build.\n",
        )
        self.assertEqual(self.check(nothing).returncode, 0)

    def test_history_is_dated_and_ordered(self) -> None:
        line = "- 2026-06-21: 11 features (3 core, 2 supporting, 4 adjacent, 2 off-promise); direction drifting\n"
        self.assert_rejects(self.edit(line, ""), "History needs one dated line per audit")
        self.assert_rejects(self.edit(line, line + "- 2026-01-05: 6 features; direction focused\n"), "History lines must run oldest to newest")
        self.assert_rejects(self.edit(line, "- 2026-13-45: 11 features; direction drifting\n"), "History has an invalid date")
        self.assert_rejects(self.edit(line, "- last June: 11 features\n"), "malformed history line")
        second = self.edit(line, line + "- 2026-09-01: 12 features; direction drifting\n")
        completed = self.check(second)
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual(json.loads(completed.stdout)["audits"], 2)

    def test_parser_is_importable_for_reuse(self) -> None:
        parsed, errors = product_audit.parse_report(PRODUCT_AUDIT_REPORT)
        self.assertEqual(errors, [])
        self.assertEqual(parsed["features"]["F8"]["decision"], "keep")
        self.assertEqual(parsed["features"]["F8"]["verdict"], "park")
        self.assertEqual(parsed["features"]["F8"]["decided_by"], "owner")


if __name__ == "__main__":
    unittest.main()
