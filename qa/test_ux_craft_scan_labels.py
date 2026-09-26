"""Deterministic checks for the ui-naming label scanner (ux-craft).

Evidence tier: objective. Each test plants one kind of drift in a small shadcn/ui app and checks
that the scanner reports it, and that it stays read-only and offline.
"""
from __future__ import annotations

import contextlib
import hashlib
import io
import json
import socket
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

REPO = Path(__file__).resolve().parent.parent
SKILL_DIR = REPO / "plugins/ux-craft/skills/ui-naming"
sys.path.insert(0, str(SKILL_DIR / "scripts"))
import scan_labels  # noqa: E402

UX_MD = """# UX decisions

## Casing

- Labels, buttons, headings: sentence case

## Glossary

| Term | Meaning | Rejected synonyms |
|---|---|---|
| Check | One automated evaluation of one thing that matters | Skill, judge |
| Review guide | The rubric a Check follows | rubric, guide |
| (term) | (one line) | (words not to use) |

## Scanner

- Label props: eyebrow
"""

SIDEBAR = """import { Home, Settings } from "lucide-react";
const data = {
  navMain: [
    { title: "Overview", url: "/", icon: Home },
    { title: "Skill Settings", url: "/skill", icon: Settings },
  ],
};
export function AppSidebar() {
  return (
    <Sidebar>
      <SidebarMenu>
        {data.navMain.map((item) => (
          <SidebarMenuItem key={item.title}>
            <SidebarMenuButton asChild tooltip={item.title}>
              <a href={item.url}><item.icon /><span>{item.title}</span></a>
            </SidebarMenuButton>
          </SidebarMenuItem>
        ))}
      </SidebarMenu>
    </Sidebar>
  );
}
"""

PAGE = """"use client";
import { toast } from "sonner";
import { z } from "zod";

const schema = z.object({
  email: z.string().email("Invalid email address"),
  name: z.string().min(1, { message: "Please enter a name" }),
});

export default function Page({ title = "Set up your evaluator" }) {
  const [saving, setSaving] = useState<boolean>(false);
  const label = status === "running" ? t("nav.home") : format(date, "MMM d");
  const onSave = async () => {
    toast.success("Success!");
    toast.error("Something went wrong");
  };
  if (count < limit && ready) return null;
  return (
    <div className="flex items-center gap-2">
      <SectionHead eyebrow="Overview" title="Project Overview" />
      <Card>
        <CardHeader>
          <CardTitle>Skill in production</CardTitle>
          <CardDescription>Open the Review guide to edit it.</CardDescription>
        </CardHeader>
      </Card>
      <Button onClick={() => void onSave()}>Submit</Button>
      <Button variant="outline" onClick={() => setOpen(true)}><Plus className="size-4" /> Add examples</Button>
      <Button disabled={saving}>{saving ? "Saving…" : "Save changes"}</Button>
      <Button title="Only owners can do this">Open Check</Button>
      <DropdownMenu>
        <DropdownMenuTrigger asChild><Button variant="ghost">Open menu</Button></DropdownMenuTrigger>
        <DropdownMenuContent>
          <DropdownMenuItem onSelect={() => remove()}><Trash2 /> Remove project</DropdownMenuItem>
          <DropdownMenuItem variant="destructive"><Trash2 /> Delete project</DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>
      <AlertDialogAction onClick={() => destroy()}>OK</AlertDialogAction>
      <Label htmlFor="email">Email address</Label>
      <Input id="email" placeholder="name@example.com" />
      <code>npm run dev</code>
      <Breadcrumb><BreadcrumbPage>Overview</BreadcrumbPage></Breadcrumb>
    </div>
  );
}
"""

VUE = """<template>
  <button class="btn">Submit</button>
</template>
"""

I18N = """{"deleteButton": "Remove", "title": "Project settings"}"""


def write(root: Path, relative: str, text: str) -> None:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def build_app(root: Path, ux: bool = True) -> None:
    if ux:
        write(root, "UX.md", UX_MD)
    write(root, "src/components/app-sidebar.tsx", SIDEBAR)
    write(root, "src/app/page.tsx", PAGE)
    write(root, "src/legacy/Banner.vue", VUE)
    write(root, "src/locales/en.json", I18N)


def scan(root: Path, *extra: str) -> dict:
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        code = scan_labels.main([str(root), "--format", "json", *extra])
    assert code == 0, code
    return json.loads(out.getvalue())


def texts(items: list[dict]) -> list[str]:
    return [item["text"] for item in items]


def by_text(report: dict, text: str) -> list[dict]:
    return [s for s in report["inventory"] if s["text"] == text]


def tree_digest(root: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(root.rglob("*")):
        digest.update(str(path.relative_to(root)).encode())
        if path.is_file():
            digest.update(path.read_bytes())
            digest.update(str(path.stat().st_mtime_ns).encode())
    return digest.hexdigest()


class ScanLabelsTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        build_app(self.root)
        self.report = scan(self.root)

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_labels_behind_arrow_handlers_and_icons_are_read(self) -> None:
        generic = texts(self.report["generic"])
        self.assertIn("Submit", generic)  # <Button onClick={() => ...}>Submit</Button>
        self.assertIn("OK", generic)      # <AlertDialogAction onClick={() => ...}>OK</...>
        self.assertEqual([s["role"] for s in by_text(self.report, "Add examples")], ["action"])
        self.assertEqual([s["role"] for s in by_text(self.report, "Remove project")], ["action"])

    def test_both_branches_of_a_ternary_label_are_read(self) -> None:
        for label in ("Saving…", "Save changes"):
            self.assertEqual([s["role"] for s in by_text(self.report, label)], ["action"], label)

    def test_shadcn_components_get_roles(self) -> None:
        roles = {s["text"]: s["role"] for s in self.report["inventory"]}
        self.assertEqual(roles["Skill in production"], "title")
        self.assertEqual(roles["Open the Review guide to edit it."], "description")
        self.assertEqual(roles["Email address"], "field")
        self.assertEqual(roles["Project Overview"], "title")  # SectionHead title prop
        self.assertEqual(roles["Only owners can do this"], "text")  # Button title is a tooltip
        breadcrumb = [s for s in by_text(self.report, "Overview") if s["context"] == "BreadcrumbPage"]
        self.assertEqual([s["role"] for s in breadcrumb], ["nav"])

    def test_sidebar_block_config_is_navigation(self) -> None:
        nav = {(s["text"], s["context"]) for s in self.report["navigation"]}
        self.assertIn(("Overview", "title"), nav)
        self.assertIn(("Skill Settings", "title"), nav)

    def test_nested_trigger_reports_the_inner_control_once(self) -> None:
        self.assertEqual(len(by_text(self.report, "Open menu")), 1)

    def test_verb_drift_between_menu_items_is_clustered(self) -> None:
        cluster = self.report["drift_verbs"]["delete-remove"]
        # The menu item and the i18n key deleteButton ("Remove") both drift from "Delete".
        self.assertEqual(sorted(texts(cluster["remove"])), ["Remove", "Remove project"])
        self.assertEqual(texts(cluster["delete"]), ["Delete project"])

    def test_ux_glossary_rejected_synonyms_are_reported(self) -> None:
        check = self.report["rejected"]["Check"]
        self.assertIn("Skill in production", texts(check["Skill"]))
        self.assertIn("Skill Settings", texts(check["Skill"]))
        # "Review guide" is the canonical term, so its own "guide" is not drift.
        self.assertNotIn("Review guide", self.report["rejected"])

    def test_casing_follows_policy_and_treats_glossary_terms_as_names(self) -> None:
        deviations = texts(self.report["casing"]["deviations"])
        self.assertIn("Project Overview", deviations)
        self.assertIn("Skill Settings", deviations)
        self.assertNotIn("Open Check", deviations)          # Check is a glossary term
        self.assertNotIn("name@example.com", deviations)    # placeholders are format hints
        self.assertEqual(self.report["casing"]["policy"], "sentence")

    def test_toasts_and_zod_messages_are_checked(self) -> None:
        banned = {item["string"]["text"]: item["words"] for item in self.report["banned"]}
        self.assertIn("invalid", banned["Invalid email address"])
        self.assertIn("please", banned["Please enter a name"])
        self.assertIn("something went wrong", banned["Something went wrong"])
        self.assertIn("Success!", texts(self.report["exclamations"]))

    def test_code_comparisons_and_calls_are_not_copy(self) -> None:
        inventory = texts(self.report["inventory"])
        for not_copy in ("running", "nav.home", "MMM d", "npm run dev", "flex items-center gap-2"):
            self.assertNotIn(not_copy, inventory)
        # TypeScript generics and comparisons do not derail the JSX scan.
        self.assertIn("Save changes", inventory)
        self.assertIn("Set up your evaluator", inventory)  # destructured prop default

    def test_label_props_come_from_ux_md_or_flag(self) -> None:
        eyebrow = [s for s in by_text(self.report, "Overview") if s["context"] == "eyebrow"]
        self.assertEqual(len(eyebrow), 1)
        with tempfile.TemporaryDirectory() as other:
            root = Path(other)
            build_app(root, ux=False)
            plain = scan(root)
            self.assertFalse([s for s in by_text(plain, "Overview") if s["context"] == "eyebrow"])
            self.assertEqual(plain["rejected"], {})
            flagged = scan(root, "--prop", "eyebrow", "--term", "Check=Skill")
            self.assertTrue([s for s in by_text(flagged, "Overview") if s["context"] == "eyebrow"])
            self.assertIn("Skill in production", texts(flagged["rejected"]["Check"]["Skill"]))

    def test_markup_and_i18n_files_are_still_scanned(self) -> None:
        vue = [s for s in self.report["generic"] if s["file"].endswith("Banner.vue")]
        self.assertEqual(texts(vue), ["Submit"])
        self.assertEqual([s["role"] for s in by_text(self.report, "Remove")], ["action"])

    def test_scan_is_read_only_and_offline(self) -> None:
        before = tree_digest(self.root)

        def refuse(*args, **kwargs):
            raise AssertionError("scan_labels attempted network access")

        with mock.patch.object(socket, "socket", refuse), \
                mock.patch.object(socket, "create_connection", refuse):
            md = io.StringIO()
            with contextlib.redirect_stdout(md):
                self.assertEqual(scan_labels.main([str(self.root)]), 0)
        self.assertEqual(tree_digest(self.root), before)
        self.assertIn("## Rejected terms (UX.md glossary)", md.getvalue())

    def test_shipped_ux_template_parses_as_empty_settings(self) -> None:
        template = (SKILL_DIR / "templates/UX.md").read_text(encoding="utf-8")
        parsed = scan_labels.parse_ux(template)
        self.assertEqual(parsed["glossary"], {})
        self.assertEqual(parsed["props"], set())
        self.assertEqual(parsed["excludes"], [])
        self.assertEqual(parsed["casing"], "sentence")

    def test_missing_explicit_ux_file_is_an_error(self) -> None:
        err = io.StringIO()
        with contextlib.redirect_stderr(err), contextlib.redirect_stdout(io.StringIO()):
            code = scan_labels.main([str(self.root), "--ux", str(self.root / "missing.md")])
        self.assertEqual(code, 2)
        self.assertIn("UX.md not found", err.getvalue())


if __name__ == "__main__":
    unittest.main()
