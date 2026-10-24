import contextlib
import copy
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch


SPEC = importlib.util.spec_from_file_location(
    "runtime_recipe", Path(__file__).resolve().parents[1] / "tools/runtime_recipe.py")
recipe = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(recipe)


class RuntimeRecipeTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.install = self.root / "Wine With Spaces"
        self.install.mkdir()
        self.wine = self.file("wine", b"fixture, never execute")
        self.server = self.file("wineserver", b"server fixture")
        self.asset = self.file("renderer.dll", b"renderer fixture")
        self.dependency = self.file("dependency.dylib", b"dependency fixture")
        self.wine.chmod(0o700)
        self.server.chmod(0o700)
        self.entry = {
            "name": "selected-upstream", "kind": "free", "version": "fixture-1",
            "source_url": "fixture:source", "install_path": str(self.install),
            "wine": str(self.wine), "sha256": recipe.digest(self.wine),
            "wineserver": str(self.server), "local_only": True,
            "environment": {
                "WINEDLLOVERRIDES": "", "WINEMSYNC": "0",
                "DYLD_FALLBACK_LIBRARY_PATH": str(self.install),
                "WINELOADER": str(self.wine), "WINESERVER": str(self.server),
            },
            "dependencies": [{"path": str(self.dependency),
                              "sha256": recipe.digest(self.dependency)}],
            "profile_assets": {"files": [{"path": str(self.asset),
                                          "sha256": recipe.digest(self.asset)}]},
            "prefix_overlays": [{"source": str(self.asset),
                                 "destination": "drive_c/windows/system32/renderer.dll"}],
            "prefix_registry_imports": [{"source": str(self.asset),
                                         "sha256": recipe.digest(self.asset)}],
            "smoke_test": {"status": "fixture-only"},
            "future_metadata": {"renderer": "explicit", "unknown": [1, 2]},
        }
        self.registry = self.root / "registry.json"
        self.data = {"schema_version": 1, "host_architecture": "arm64",
                     "engines": [self.entry], "blocked": [{"name": "not-selected"}]}

    def file(self, name, contents):
        path = self.install / name
        path.write_bytes(contents)
        return path

    def export(self):
        self.registry.write_text(json.dumps(self.data))
        return recipe.export_recipe(self.registry, "selected-upstream")

    def test_preserves_entire_selected_record_without_ambient_defaults(self):
        # REQ-33: "No hidden fallback/substitution; changed digest or malformed
        # ownership marker cannot silently reuse a claimed prefix."
        # This exporter covers record preservation only, not prefix ownership.
        original = copy.deepcopy(self.entry)
        with patch.dict("os.environ", {
                "WINEDLLOVERRIDES": "d3d11,dxgi=b",
                "CX_APPLEGPTK_LIBD3DSHARED_PATH": "/retired/shim"}):
            exported = self.export()
        self.assertEqual(exported["engines"], [original])
        self.assertEqual(self.entry, original)
        self.assertNotIn("CX_APPLEGPTK_LIBD3DSHARED_PATH",
                         exported["engines"][0]["environment"])
        self.assertEqual(exported["blocked"], self.data["blocked"])
        self.assertEqual(exported["calimocho_recipe"]["qualification"],
                         "not-tested-by-this-export")

    def test_record_digest_changes_with_renderer_environment_and_dependencies(self):
        before = self.export()["calimocho_recipe"]["engine_record_sha256"]
        self.entry["future_metadata"]["renderer"] = "another-renderer"
        changed_renderer = self.export()["calimocho_recipe"]["engine_record_sha256"]
        self.entry["environment"]["WINEMSYNC"] = "1"
        changed_env = self.export()["calimocho_recipe"]["engine_record_sha256"]
        self.entry["dependencies"][0]["version"] = "another-version"
        changed_dep = self.export()["calimocho_recipe"]["engine_record_sha256"]
        self.assertEqual(len({before, changed_renderer, changed_env, changed_dep}), 4)

    def test_no_execution_or_prefix_mutation(self):
        prefix = self.root / "prefix"
        prefix.mkdir()
        save = prefix / "save"
        save.write_bytes(b"raw save")
        with patch("os.execve", side_effect=AssertionError("must not execute")), \
                patch("subprocess.Popen", side_effect=AssertionError("must not spawn")):
            self.export()
        self.assertEqual(list(prefix.iterdir()), [save])
        self.assertEqual(save.read_bytes(), b"raw save")

    def test_missing_or_duplicate_choice_has_no_fallback(self):
        self.registry.write_text(json.dumps(self.data))
        with self.assertRaisesRegex(ValueError, "Unknown selected engine"):
            recipe.export_recipe(self.registry, "calimocho")
        self.data["engines"].append(copy.deepcopy(self.entry))
        with self.assertRaisesRegex(ValueError, "duplicate engine names"):
            self.export()

    def test_changed_payloads_fail_without_export(self):
        for path in (self.wine, self.asset, self.dependency):
            with self.subTest(path=path):
                original = path.read_bytes()
                path.write_bytes(b"changed bytes")
                with self.assertRaisesRegex(ValueError, "SHA-256 mismatch"):
                    self.export()
                path.write_bytes(original)

    def test_missing_or_nonexecutable_server_is_not_inferred(self):
        self.entry.pop("wineserver")
        with self.assertRaisesRegex(ValueError, "nonempty string"):
            self.export()
        self.entry["wineserver"] = str(self.server)
        self.server.chmod(0o600)
        with self.assertRaisesRegex(ValueError, "non-executable"):
            self.export()

    def test_symlink_cannot_substitute_entrypoint_outside_installation(self):
        outside = self.root / "other-wine"
        outside.write_bytes(self.wine.read_bytes())
        self.wine.unlink()
        self.wine.symlink_to(outside)
        with self.assertRaisesRegex(ValueError, "escapes selected installation"):
            self.export()

    def test_relative_paths_and_unsafe_overlay_destinations_fail(self):
        for destination in ("../escape", "/absolute", "C:\\escape",
                            "drive_c\\..\\escape", ".", "drive_c/file:stream"):
            with self.subTest(destination=destination):
                self.entry["prefix_overlays"][0]["destination"] = destination
                with self.assertRaisesRegex(ValueError, "Unsafe prefix overlay"):
                    self.export()
        self.entry["wine"] = "wine"
        with self.assertRaisesRegex(ValueError, "absolute local path"):
            self.export()

    def test_environment_cannot_redirect_loader_server_or_prefix(self):
        for key in ("WINELOADER", "WINESERVER", "WINEPREFIX"):
            with self.subTest(key=key):
                saved = copy.deepcopy(self.entry["environment"])
                self.entry["environment"][key] = "/another"
                with self.assertRaises(ValueError):
                    self.export()
                self.entry["environment"] = saved

    def test_malformed_schema_and_field_shapes_fail(self):
        for field, value in (("environment", []), ("dependencies", {}),
                             ("profile_assets", []), ("sha256", "invalid"),
                             ("prefix_overlays", [None])):
            with self.subTest(field=field):
                saved = copy.deepcopy(self.entry)
                self.entry[field] = value
                with self.assertRaises(ValueError):
                    self.export()
                self.entry.clear()
                self.entry.update(saved)
        self.data["schema_version"] = True
        with self.assertRaisesRegex(ValueError, "schema_version"):
            self.export()

    def test_unpinned_overlay_is_rejected(self):
        self.entry["profile_assets"]["files"] = []
        with self.assertRaisesRegex(ValueError, "Unpinned overlay"):
            self.export()

    def test_null_dependency_pin_does_not_skip_verification(self):
        self.entry["dependencies"][0]["sha256"] = None
        with self.assertRaisesRegex(ValueError, "dependency sha256"):
            self.export()

    def test_directory_dependency_must_exist(self):
        self.entry["dependencies"] = [{"path": str(self.install)}]
        self.export()
        self.entry["dependencies"][0]["path"] = str(self.root / "absent")
        with self.assertRaisesRegex(ValueError, "Missing dependency directory"):
            self.export()

    def test_import_hash_and_nonfinite_json_are_rejected(self):
        self.entry["prefix_registry_imports"][0]["sha256"] = "0" * 64
        with self.assertRaisesRegex(ValueError, "SHA-256 mismatch"):
            self.export()
        self.registry.write_text('{"schema_version": 1, "unknown": NaN}')
        with self.assertRaisesRegex(ValueError, "Non-finite JSON number"):
            recipe.export_recipe(self.registry, "selected")

    def test_cli_errors_are_explicit_and_stdout_is_empty(self):
        self.registry.write_text('{"schema_version": 1, "schema_version": 1}')
        output, errors = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(output), contextlib.redirect_stderr(errors):
            code = recipe.main(["--registry", str(self.registry), "--engine", "selected"])
        self.assertEqual(code, 1)
        self.assertEqual(output.getvalue(), "")
        self.assertIn("calimocho: ERROR", errors.getvalue())
        self.assertIn("Duplicate JSON key", errors.getvalue())

    def test_bounded_input(self):
        self.registry.write_bytes(b" " * (recipe.MAX_REGISTRY_BYTES + 1))
        with self.assertRaisesRegex(ValueError, "exceeds 8 MiB"):
            recipe.export_recipe(self.registry, "selected")

    def test_cli_success_emits_standard_single_record_registry(self):
        self.export()
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            code = recipe.main(["--registry", str(self.registry),
                                "--engine", "selected-upstream"])
        self.assertEqual(code, 0)
        exported = json.loads(output.getvalue())
        self.assertEqual(exported["schema_version"], 1)
        self.assertEqual(exported["engines"], [self.entry])
        self.assertEqual(exported["calimocho_recipe"]["source_registry_sha256"],
                         hashlib.sha256(self.registry.read_bytes()).hexdigest())


if __name__ == "__main__":
    unittest.main()
