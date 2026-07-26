from __future__ import annotations

import json
import os
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from eval_packaging import materialize_installation, resolve_install_modes
from eval_provenance import installation_source_hash

REPO = Path(__file__).resolve().parents[1]


class EvalPackagingTests(unittest.TestCase):
    def write_plugin(
        self,
        root: Path,
        name: str = "group",
        *,
        sibling: bool = True,
        hooks: bool = True,
    ) -> Path:
        plugin = root / name
        (plugin / ".claude-plugin").mkdir(parents=True)
        (plugin / ".claude-plugin/plugin.json").write_text(
            json.dumps(
                {
                    "name": name,
                    "displayName": "Group marker",
                    "description": "GROUP_DESCRIPTION_MARKER",
                    "version": "1.2.3",
                    "components": {"hooks": "./hooks/hooks.json"},
                }
            ),
            encoding="utf-8",
        )
        target = plugin / "skills" / "target"
        (target / "references").mkdir(parents=True)
        (target / "SKILL.md").write_text(
            '---\nname: target\ndescription: "Target: decoded description"\n'
            "---\n\nRead references/guide.md.\n",
            encoding="utf-8",
        )
        (target / "references/guide.md").write_text(
            "TARGET_RESOURCE\n",
            encoding="utf-8",
        )
        if sibling:
            sibling_dir = plugin / "skills" / "sibling"
            sibling_dir.mkdir(parents=True)
            (sibling_dir / "SKILL.md").write_text(
                "---\nname: sibling\n"
                "description: SIBLING_DESCRIPTION_MARKER\n---\n",
                encoding="utf-8",
            )
        if hooks:
            (plugin / "hooks").mkdir()
            (plugin / "hooks/hooks.json").write_text(
                '{"marker":"HOOK_MARKER"}\n',
                encoding="utf-8",
            )
        return plugin

    def test_skill_mode_contains_only_target_skill_resources_and_minimal_manifest(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            sources = root / "sources"
            self.write_plugin(sources)
            destination = root / "installed"
            result = materialize_installation(
                source_plugin_root=sources,
                destination_root=destination,
                target_plugin="group",
                target_skill="target",
                mode="skill",
                config={"plugins": ["group", "companion"]},
            )

            self.assertEqual(result.mode, "skill")
            self.assertEqual(result.source_plugins, ("group",))
            files = sorted(
                path.relative_to(destination / "group").as_posix()
                for path in (destination / "group").rglob("*")
                if path.is_file()
            )
            self.assertEqual(
                files,
                [
                    ".claude-plugin/plugin.json",
                    "skills/target/SKILL.md",
                    "skills/target/references/guide.md",
                ],
            )
            manifest = json.loads(
                (
                    destination / "group/.claude-plugin/plugin.json"
                ).read_text(encoding="utf-8")
            )
            self.assertEqual(
                manifest,
                {
                    "name": "group",
                    "displayName": "target",
                    "description": "Target: decoded description",
                    "version": "1.2.3",
                },
            )
            self.assertNotIn("hooks", manifest)
            self.assertNotIn("components", manifest)
            self.assertEqual(
                stat.S_IMODE(
                    (
                        destination / "group/.claude-plugin/plugin.json"
                    ).stat().st_mode
                ),
                0o644,
            )
            installed_text = "\n".join(
                path.read_text(encoding="utf-8")
                for path in (destination / "group").rglob("*")
                if path.is_file()
            )
            self.assertNotIn("GROUP_DESCRIPTION_MARKER", installed_text)
            self.assertNotIn("SIBLING_DESCRIPTION_MARKER", installed_text)
            self.assertNotIn("HOOK_MARKER", installed_text)
            self.assertFalse((destination / "group/hooks").exists())
            self.assertFalse((destination / "group/skills/sibling").exists())

    def test_every_shipped_skill_materializes_without_its_siblings_or_hooks(
        self,
    ) -> None:
        distributions = sorted(
            (REPO / "plugins").glob("*/skills/*/SKILL.md")
        )
        self.assertEqual(len(distributions), 15)
        with tempfile.TemporaryDirectory() as temp:
            destination_root = Path(temp)
            for index, skill_md in enumerate(distributions):
                skill_dir = skill_md.parent
                skill = skill_dir.name
                plugin = skill_dir.parent.parent.name
                destination = destination_root / str(index)
                result = materialize_installation(
                    source_plugin_root=REPO / "plugins",
                    destination_root=destination,
                    target_plugin=plugin,
                    target_skill=skill,
                    mode="skill",
                    config={},
                )

                with self.subTest(plugin=plugin, skill=skill):
                    self.assertEqual(result.source_plugins, (plugin,))
                    installed = destination / plugin
                    self.assertFalse((installed / "hooks").exists())
                    self.assertEqual(
                        sorted(
                            child.name
                            for child in (installed / "skills").iterdir()
                        ),
                        [skill],
                    )
                    manifest = json.loads(
                        (
                            installed / ".claude-plugin" / "plugin.json"
                        ).read_text(encoding="utf-8")
                    )
                    self.assertEqual(
                        set(manifest),
                        {"name", "displayName", "description", "version"},
                    )
                    self.assertEqual(manifest["name"], plugin)
                    self.assertEqual(manifest["displayName"], skill)
                    self.assertIsNone(
                        next(
                            (
                                path
                                for path in installed.rglob("*")
                                if path.is_symlink()
                            ),
                            None,
                        )
                    )

    def test_plugin_and_stack_modes_are_distinct(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            sources = root / "sources"
            self.write_plugin(sources)
            self.write_plugin(
                sources,
                "companion",
                sibling=False,
                hooks=False,
            )
            plugin_result = materialize_installation(
                source_plugin_root=sources,
                destination_root=root / "plugin",
                target_plugin="group",
                target_skill="target",
                mode="plugin",
                config={"plugins": ["group", "companion"]},
            )
            stack_result = materialize_installation(
                source_plugin_root=sources,
                destination_root=root / "stack",
                target_plugin="group",
                target_skill="target",
                mode="stack",
                config={"plugins": ["group", "companion"]},
            )

            self.assertEqual(plugin_result.source_plugins, ("group",))
            self.assertTrue((root / "plugin/group/hooks/hooks.json").is_file())
            self.assertTrue((root / "plugin/group/skills/sibling/SKILL.md").is_file())
            self.assertFalse((root / "plugin/companion").exists())
            self.assertEqual(
                stack_result.source_plugins,
                ("group", "companion"),
            )
            self.assertTrue((root / "stack/companion/skills/target/SKILL.md").is_file())

    def test_python_entrypoints_import_from_the_target_only_package(self) -> None:
        failures: list[str] = []
        environment = dict(os.environ)
        environment.pop("PYTHONPATH", None)
        with tempfile.TemporaryDirectory() as temp:
            destination_root = Path(temp)
            for index, skill_md in enumerate(
                sorted((REPO / "plugins").glob("*/skills/*/SKILL.md"))
            ):
                skill_dir = skill_md.parent
                skill = skill_dir.name
                plugin = skill_dir.parent.parent.name
                destination = destination_root / str(index)
                materialize_installation(
                    source_plugin_root=REPO / "plugins",
                    destination_root=destination,
                    target_plugin=plugin,
                    target_skill=skill,
                    mode="skill",
                    config={},
                )
                installed_skill = destination / plugin / "skills" / skill
                for script in sorted((installed_skill / "scripts").glob("*.py")):
                    completed = subprocess.run(
                        [sys.executable, str(script), "--help"],
                        cwd=installed_skill,
                        env=environment,
                        capture_output=True,
                        text=True,
                    )
                    if completed.returncode != 0:
                        detail = completed.stderr.strip() or completed.stdout.strip()
                        failures.append(
                            f"{plugin}/{skill}/{script.name}: "
                            f"exit {completed.returncode}: {detail}"
                        )
        self.assertEqual(failures, [])

    def test_matrix_resolution_is_explicit_and_override_selects_one_mode(self) -> None:
        suite = {"install_modes": ["skill", "plugin"]}
        case = {
            "plugins": ["group", "companion"],
            "install_modes": ["skill", "stack"],
        }
        self.assertEqual(
            resolve_install_modes(case, "group", suite=suite),
            ["skill", "stack"],
        )
        self.assertEqual(
            resolve_install_modes(
                case,
                "group",
                suite=suite,
                override="plugin",
            ),
            ["plugin"],
        )
        self.assertEqual(
            resolve_install_modes({}, "group"),
            ["plugin"],
        )

    def test_skill_provenance_ignores_siblings_but_plugin_provenance_does_not(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temp:
            sources = Path(temp) / "sources"
            plugin = self.write_plugin(sources)
            case: dict[str, object] = {}
            skill_before = installation_source_hash(
                sources,
                plugin="group",
                skill="target",
                install_mode="skill",
                case=case,
            )
            plugin_before = installation_source_hash(
                sources,
                plugin="group",
                skill="target",
                install_mode="plugin",
                case=case,
            )
            (plugin / "skills/sibling/SKILL.md").write_text(
                "SIBLING_CHANGED\n",
                encoding="utf-8",
            )
            self.assertEqual(
                installation_source_hash(
                    sources,
                    plugin="group",
                    skill="target",
                    install_mode="skill",
                    case=case,
                ),
                skill_before,
            )
            self.assertNotEqual(
                installation_source_hash(
                    sources,
                    plugin="group",
                    skill="target",
                    install_mode="plugin",
                    case=case,
                ),
                plugin_before,
            )

    def test_symlinked_target_resource_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            sources = root / "sources"
            plugin = self.write_plugin(sources)
            outside = root / "outside.txt"
            outside.write_text("secret\n", encoding="utf-8")
            (plugin / "skills/target/references/linked.md").symlink_to(outside)
            with self.assertRaisesRegex(ValueError, "symlinked skill source"):
                materialize_installation(
                    source_plugin_root=sources,
                    destination_root=root / "installed",
                    target_plugin="group",
                    target_skill="target",
                    mode="skill",
                    config={},
                )


if __name__ == "__main__":
    unittest.main()
