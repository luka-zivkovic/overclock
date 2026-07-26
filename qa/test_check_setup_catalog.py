import importlib.util
import unittest
from pathlib import Path


REPO = Path(__file__).resolve().parent.parent
SCRIPT = REPO / "tools/check_setup_catalog.py"
SPEC = importlib.util.spec_from_file_location("check_setup_catalog", SCRIPT)
assert SPEC and SPEC.loader
catalog_check = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(catalog_check)


def package(version: str = "1.0.0") -> dict:
    return {
        "id": "example",
        "version": version,
        "publication_status": "published",
        "provides": ["example-capability"],
        "skill_names": ["example-skill"],
        "depends_on": [],
        "conflicts_with": [],
        "hooks": [],
        "persistent_files": [],
    }


class SetupCatalogValidationTests(unittest.TestCase):
    def test_detects_manifest_version_drift(self):
        catalog = {"schema_version": 1, "packages": [package("1.0.0")]}
        marketplace = {
            "plugins": [{"name": "example", "version": "1.0.0"}]
        }
        errors = catalog_check.validate(
            catalog,
            marketplace,
            {"example": {"name": "example", "version": "1.0.1"}},
            {"example": {"example-skill"}},
        )
        self.assertTrue(any("manifest version" in error for error in errors))

    def test_detects_catalog_skill_name_drift(self):
        catalog = {"schema_version": 1, "packages": [package()]}
        marketplace = {
            "plugins": [{"name": "example", "version": "1.0.0"}]
        }
        errors = catalog_check.validate(
            catalog,
            marketplace,
            {"example": {"name": "example", "version": "1.0.0"}},
            {"example": {"renamed-skill"}},
        )
        self.assertTrue(any("shipped skills" in error for error in errors))


if __name__ == "__main__":
    unittest.main()
