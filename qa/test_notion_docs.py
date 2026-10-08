"""Deterministic tests for the notion-docs recorder helper.

Covers the offline surface that needs no browser: scene validation and the secrets rule,
`doctor` and `record` behaviour without Playwright, and a PNG-to-GIF round trip verified by an
independent GIF decoder written here. Recording itself is exercised manually and in live evals.
"""
from __future__ import annotations

import json
import os
import struct
import subprocess
import tempfile
import unittest
import zlib
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SKILL = REPO / "plugins" / "notion-docs" / "skills" / "notion-docs"
SCRIPT = SKILL / "scripts" / "record_clip.mjs"
TEMPLATE = SKILL / "templates" / "scene.json"


def run(*args: str, env: dict | None = None) -> subprocess.CompletedProcess:
    merged = dict(os.environ)
    merged.pop("NOTION_DOCS_DEPS", None)
    if env:
        merged.update(env)
    return subprocess.run(
        ["node", str(SCRIPT), *args],
        cwd=REPO,
        env=merged,
        capture_output=True,
        text=True,
        check=False,
    )


def validate(scene: dict, directory: Path) -> tuple[int, dict]:
    path = directory / f"{scene.get('name', 'scene')}.json"
    path.write_text(json.dumps(scene), encoding="utf-8")
    result = run("validate", str(path))
    return result.returncode, json.loads(result.stdout)


def base_scene(**overrides) -> dict:
    scene = {
        "name": "create-suite",
        "url": "http://localhost:5173/suites",
        "steps": [
            {"action": "click", "selector": 'role=button[name="New suite"]', "caption": "Click New suite"},
            {"action": "type", "selector": 'role=textbox[name="Suite name"]', "text": "Billing flows"},
            {"action": "click", "selector": 'role=button[name="Create suite"]'},
            {"action": "wait", "selector": "text=Billing flows"},
        ],
    }
    scene.update(overrides)
    return scene


# ---------------------------------------------------------------- PNG writer and GIF decoder (test oracles)


def write_png(path: Path, width: int, height: int, pixel) -> list[tuple[int, int, int]]:
    """Write an 8-bit RGB PNG from pixel(x, y) -> (r, g, b); return the pixels row-major."""
    pixels: list[tuple[int, int, int]] = []
    raw = bytearray()
    for y in range(height):
        raw.append(0)
        for x in range(width):
            rgb = pixel(x, y)
            pixels.append(rgb)
            raw.extend(rgb)

    def chunk(kind: bytes, data: bytes) -> bytes:
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)

    png = b"\x89PNG\r\n\x1a\n"
    png += chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
    png += chunk(b"IDAT", zlib.compress(bytes(raw), 9))
    png += chunk(b"IEND", b"")
    path.write_bytes(png)
    return pixels


def lzw_decode(data: bytes, min_code_size: int, expected: int) -> list[int]:
    clear = 1 << min_code_size
    eoi = clear + 1
    code_size = min_code_size + 1
    table: list[list[int]] = []

    def reset() -> None:
        nonlocal table, code_size
        table = [[i] for i in range(clear)] + [[], []]
        code_size = min_code_size + 1

    reset()
    out: list[int] = []
    acc = 0
    bits = 0
    pos = 0
    prev: list[int] | None = None
    while True:
        while bits < code_size and pos < len(data):
            acc |= data[pos] << bits
            bits += 8
            pos += 1
        if bits < code_size:
            raise AssertionError("LZW stream ended without EOI")
        code = acc & ((1 << code_size) - 1)
        acc >>= code_size
        bits -= code_size
        if code == clear:
            reset()
            prev = None
            continue
        if code == eoi:
            break
        if code < len(table) and (code < clear or table[code]):
            entry = table[code]
            if prev is not None and len(table) < 4096:
                table.append(prev + [entry[0]])
        elif code == len(table) and prev is not None:
            entry = prev + [prev[0]]
            if len(table) < 4096:
                table.append(entry)
        else:
            raise AssertionError(f"bad LZW code {code} with table size {len(table)}")
        out.extend(entry)
        prev = entry
        if len(table) == (1 << code_size) and code_size < 12:
            code_size += 1
    if len(out) != expected:
        raise AssertionError(f"decoded {len(out)} pixels, expected {expected}")
    return out


def decode_gif(data: bytes) -> dict:
    assert data[:6] == b"GIF89a", data[:6]
    width, height, packed, _bg, _aspect = struct.unpack("<HHBBB", data[6:13])
    pos = 13
    palette: list[tuple[int, int, int]] = []
    if packed & 0x80:
        size = 2 ** ((packed & 7) + 1)
        table = data[pos : pos + size * 3]
        palette = [tuple(table[i : i + 3]) for i in range(0, len(table), 3)]
        pos += size * 3
    frames: list[dict] = []
    loop = None
    delay_ms = 0
    while pos < len(data):
        marker = data[pos]
        if marker == 0x21:
            label = data[pos + 1]
            pos += 2
            if label == 0xF9:
                delay_ms = struct.unpack("<H", data[pos + 2 : pos + 4])[0] * 10
            if label == 0xFF and data[pos + 1 : pos + 12] == b"NETSCAPE2.0":
                loop = struct.unpack("<H", data[pos + 14 : pos + 16])[0]
            while data[pos] != 0:
                pos += data[pos] + 1
            pos += 1
        elif marker == 0x2C:
            left, top, fw, fh, fpacked = struct.unpack("<HHHHB", data[pos + 1 : pos + 10])
            assert (left, top, fw, fh) == (0, 0, width, height)
            assert fpacked & 0x80 == 0, "local palettes are not expected"
            pos += 10
            min_code_size = data[pos]
            pos += 1
            stream = bytearray()
            while data[pos] != 0:
                n = data[pos]
                stream.extend(data[pos + 1 : pos + 1 + n])
                pos += n + 1
            pos += 1
            indices = lzw_decode(bytes(stream), min_code_size, width * height)
            frames.append({"delay_ms": delay_ms, "pixels": [palette[i] for i in indices]})
        elif marker == 0x3B:
            break
        else:
            raise AssertionError(f"unexpected GIF byte {marker:#x} at {pos}")
    return {"width": width, "height": height, "loop": loop, "frames": frames, "palette": palette}


# ---------------------------------------------------------------- tests


class ValidateTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_valid_scene_passes_with_summary(self) -> None:
        code, result = validate(base_scene(), self.dir)
        self.assertEqual(code, 0, result)
        self.assertTrue(result["ok"])
        self.assertEqual(result["errors"], [])
        self.assertEqual(result["summary"]["recorded_steps"], 4)
        self.assertEqual((result["summary"]["output_width"], result["summary"]["output_height"]), (960, 600))
        self.assertGreater(result["summary"]["estimated_seconds"], 2)

    def test_template_scene_validates_once_storage_state_exists(self) -> None:
        scene = json.loads(TEMPLATE.read_text(encoding="utf-8"))
        state = self.dir / ".notion-docs-auth" / "state.json"
        state.parent.mkdir(parents=True)
        state.write_text("{}", encoding="utf-8")
        scene["storage_state"] = str(state)
        code, result = validate(scene, self.dir)
        self.assertEqual(code, 0, result)

    def test_missing_storage_state_is_an_error(self) -> None:
        code, result = validate(base_scene(storage_state="nope/state.json"), self.dir)
        self.assertEqual(code, 1)
        self.assertTrue(any(e.startswith("storage_state: file not found") for e in result["errors"]), result)

    def test_text_env_is_rejected_in_recorded_steps(self) -> None:
        scene = base_scene()
        scene["steps"].insert(0, {"action": "fill", "selector": 'role=textbox[name="Email"]', "text_env": "APP_EMAIL"})
        code, result = validate(scene, self.dir)
        self.assertEqual(code, 1)
        self.assertTrue(any("text_env is allowed only in setup steps" in e for e in result["errors"]), result)

    def test_text_env_is_allowed_in_setup_steps(self) -> None:
        scene = base_scene(setup=[
            {"action": "fill", "selector": 'role=textbox[name="Email"]', "text": "dev@example.test"},
            {"action": "fill", "selector": 'role=textbox[name="Password"]', "text_env": "APP_PASSWORD"},
            {"action": "click", "selector": 'role=button[name="Sign in"]'},
        ])
        code, result = validate(scene, self.dir)
        self.assertEqual(code, 0, result)
        self.assertEqual(result["summary"]["setup_steps"], 3)

    def test_literal_credential_in_recorded_step_is_an_error_and_in_setup_a_warning(self) -> None:
        recorded = base_scene()
        recorded["steps"].insert(0, {"action": "fill", "selector": "#password", "text": "hunter2"})
        code, result = validate(recorded, self.dir)
        self.assertEqual(code, 1)
        self.assertTrue(any("must not type into credential fields" in e for e in result["errors"]), result)
        setup = base_scene(name="setup-warn", setup=[{"action": "fill", "selector": "#password", "text": "hunter2"}])
        code, result = validate(setup, self.dir)
        self.assertEqual(code, 0, result)
        self.assertTrue(any("prefer text_env" in w for w in result["warnings"]), result)

    def test_structural_errors_are_named(self) -> None:
        scene = base_scene(name="Bad Name", url="localhost:5173", steps=[{"action": "tap", "selector": "#x"}])
        code, result = validate(scene, self.dir)
        self.assertEqual(code, 1)
        joined = "\n".join(result["errors"])
        self.assertIn("name:", joined)
        self.assertIn("url:", joined)
        self.assertIn("unknown action", joined)

    def test_empty_steps_and_bad_wait_are_errors(self) -> None:
        code, result = validate(base_scene(steps=[]), self.dir)
        self.assertEqual(code, 1)
        self.assertTrue(any(e.startswith("steps:") for e in result["errors"]))
        code, result = validate(base_scene(name="wait-both", steps=[{"action": "wait", "ms": 100, "selector": "#x"}]), self.dir)
        self.assertEqual(code, 1)
        self.assertTrue(any("exactly one of ms or selector" in e for e in result["errors"]))

    def test_long_scene_warns_against_max_seconds(self) -> None:
        steps = [{"action": "wait", "ms": 4000} for _ in range(5)] + [{"action": "click", "selector": "#go"}]
        code, result = validate(base_scene(name="long", steps=steps, max_seconds=5), self.dir)
        self.assertEqual(code, 0, result)
        self.assertTrue(any("exceeds max_seconds" in w for w in result["warnings"]), result)

    def test_mutates_flag_is_accepted_and_reported(self) -> None:
        code, result = validate(base_scene(mutates=True), self.dir)
        self.assertEqual(code, 0, result)
        self.assertTrue(result["summary"]["mutates"])
        self.assertEqual(result["warnings"], [])
        code, result = validate(base_scene(name="bad-mutates", mutates="yes"), self.dir)
        self.assertEqual(code, 1)
        self.assertIn("mutates: true or false", result["errors"])

    def test_invalid_json_fails_cleanly(self) -> None:
        path = self.dir / "broken.json"
        path.write_text("{not json", encoding="utf-8")
        result = run("validate", str(path))
        self.assertEqual(result.returncode, 1)
        self.assertIn("not valid JSON", result.stderr)


class DependencyTests(unittest.TestCase):
    def test_doctor_reports_not_ready_without_installing(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            result = run("doctor", "--deps", temp)
            self.assertEqual(result.returncode, 0, result.stderr)
            report = json.loads(result.stdout)
            self.assertFalse(report["ready"])
            self.assertIsNone(report["playwright_version"])
            self.assertIn("setup", report["next"])
            self.assertEqual(os.listdir(temp), [], "doctor must not write into the deps directory")

    def test_record_without_playwright_names_setup_and_writes_nothing(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            scene = root / "scene.json"
            scene.write_text(json.dumps(base_scene()), encoding="utf-8")
            out = root / "clips"
            result = run("record", str(scene), "--out", str(out), "--deps", str(root / "deps"))
            self.assertEqual(result.returncode, 1)
            self.assertIn("setup --deps", result.stderr)
            self.assertFalse(any(out.glob("*.gif")) if out.exists() else False)

    def test_check_without_playwright_names_setup(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            scene = root / "scene.json"
            scene.write_text(json.dumps(base_scene()), encoding="utf-8")
            result = run("check", str(scene), "--out", str(root / "checks"), "--deps", str(root / "deps"))
            self.assertEqual(result.returncode, 1)
            self.assertIn("setup --deps", result.stderr)

    def test_sheet_refuses_a_directory_without_frames(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            result = run("sheet", "--clips", temp, "--out", str(Path(temp) / "sheet.png"), "--deps", str(Path(temp) / "deps"))
            self.assertEqual(result.returncode, 1)
            self.assertIn("no <name>.last.png frames", result.stderr)

    def test_usage_without_a_command(self) -> None:
        result = run()
        self.assertEqual(result.returncode, 0)
        self.assertIn("Subcommands", result.stderr)


class EncodeRoundTripTests(unittest.TestCase):
    def test_png_frames_become_a_looping_gif_that_decodes_back(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            frames_dir = root / "frames"
            frames_dir.mkdir()
            width, height = 48, 32
            flat = [(255, 255, 255), (37, 99, 235), (17, 24, 39), (255, 90, 54)]

            def frame_a(x: int, y: int):
                return flat[1] if 8 <= x < 24 and 8 <= y < 24 else flat[0]

            def frame_b(x: int, y: int):
                return flat[2] if 16 <= x < 40 and 4 <= y < 28 else flat[0]

            def frame_c(x: int, y: int):
                return flat[3] if (x + y) % 7 == 0 else flat[0]

            expected = [
                write_png(frames_dir / "000.png", width, height, frame_a),
                write_png(frames_dir / "001.png", width, height, frame_a),  # duplicate: merged into the previous frame
                write_png(frames_dir / "002.png", width, height, frame_b),
                write_png(frames_dir / "003.png", width, height, frame_c),
            ]
            out = root / "clip.gif"
            result = run("encode", "--frames", str(frames_dir), "--out", str(out), "--delay-ms", "100")
            self.assertEqual(result.returncode, 0, result.stderr)
            summary = json.loads(result.stdout)
            self.assertEqual((summary["width"], summary["height"]), (width, height))
            self.assertEqual(summary["input_frames"], 4)
            self.assertEqual(summary["frames"], 3)
            self.assertEqual(summary["duration_ms"], 400)
            gif = decode_gif(out.read_bytes())
            self.assertEqual((gif["width"], gif["height"]), (width, height))
            self.assertEqual(gif["loop"], 0, "the GIF must loop forever")
            self.assertEqual(len(gif["frames"]), 3)
            self.assertEqual([f["delay_ms"] for f in gif["frames"]], [200, 100, 100])
            self.assertEqual(gif["frames"][0]["pixels"], expected[0])
            self.assertEqual(gif["frames"][1]["pixels"], expected[2])
            self.assertEqual(gif["frames"][2]["pixels"], expected[3])

    def test_many_colors_are_quantized_with_flat_colors_kept_exact(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            frames_dir = root / "frames"
            frames_dir.mkdir()
            width, height = 64, 64

            def gradient(x: int, y: int):
                if y < 16:
                    return (255, 255, 255)  # a flat band that must survive exactly
                return (x * 4 % 256, y * 4 % 256, (x * y) % 256)

            expected = write_png(frames_dir / "000.png", width, height, gradient)
            out = root / "gradient.gif"
            result = run("encode", "--frames", str(frames_dir), "--out", str(out), "--fps", "10")
            self.assertEqual(result.returncode, 0, result.stderr)
            summary = json.loads(result.stdout)
            self.assertLessEqual(summary["palette_size"], 256)
            gif = decode_gif(out.read_bytes())
            pixels = gif["frames"][0]["pixels"]
            self.assertEqual(pixels[: width * 16], expected[: width * 16], "flat band changed")
            error = sum(abs(a - b) for p, q in zip(pixels[width * 16 :], expected[width * 16 :]) for a, b in zip(p, q))
            per_channel = error / (len(pixels) - width * 16) / 3
            self.assertLess(per_channel, 24, f"mean per-channel error {per_channel:.1f} is too high for a 256-color palette")

    def test_encode_refuses_an_empty_directory(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            result = run("encode", "--frames", temp, "--out", str(Path(temp) / "x.gif"))
            self.assertEqual(result.returncode, 1)
            self.assertIn("no PNG frames", result.stderr)


class PackagingTests(unittest.TestCase):
    def test_skill_is_user_invoked_in_both_harnesses(self) -> None:
        skill_md = (SKILL / "SKILL.md").read_text(encoding="utf-8")
        self.assertIn("disable-model-invocation: true", skill_md.split("---", 2)[1])
        openai = (SKILL / "agents" / "openai.yaml").read_text(encoding="utf-8")
        self.assertIn("allow_implicit_invocation: false", openai)

    def test_every_linked_reference_and_template_exists(self) -> None:
        import re

        skill_md = (SKILL / "SKILL.md").read_text(encoding="utf-8")
        for link in re.findall(r"\]\(((?:references|templates)/[^)]+)\)", skill_md):
            self.assertTrue((SKILL / link).is_file(), link)
        for name in ["scene-spec.md", "page-craft.md", "notion-delivery.md", "notion-markdown.md"]:
            self.assertIn(f"references/{name}", skill_md)


if __name__ == "__main__":
    unittest.main()
