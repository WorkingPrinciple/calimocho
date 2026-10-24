import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from tools import emit_vulkan_registry
from tools.emit_vulkan_registry import observation
from tools.probe_wine_source import sha256
from tools.runtime_recipe import export_recipe


ROOT = Path(__file__).resolve().parents[1]
LOCAL = ROOT / "build/winehq-11.20/metal-port-11"
RECORD = LOCAL / "calimocho-wine11.20-gptk4b3-tls-vulkan.registry.local.json"


class VulkanRegistryObservationTests(unittest.TestCase):
    @unittest.skipUnless(
        (ROOT / "build/winehq-11.20/metal-port-11b-private-binding-01/"
         "calimocho-wine11.20-gptk4b3-tls-vulkan-private.registry.local.json").is_file(),
        "Requires actual local private qualification")
    def test_private_record_matches_actual_matrix_and_loader(self):
        evidence = json.loads(
            (ROOT / "docs/evidence/port11b-private-qualification.json").read_text())
        local = ROOT / evidence["local_root"]
        record = local / f'{evidence["engine_name"]}.registry.local.json'
        self.assertEqual(sha256(record), evidence["local_registry_sha256"])
        engine = export_recipe(record, evidence["engine_name"])["engines"][0]
        self.assertEqual(engine["environment"]["MVK_CONFIG_USE_METAL_PRIVATE_API"], "1")
        self.assertEqual(engine["environment"]["WINELOADER"], str(local / "install/bin/wine"))
        self.assertEqual(engine["environment"]["WINESERVER"], str(local / "install/bin/wineserver"))
        for kind in ("vulkan", "d3d12", "d3d11", "https", "https-expired"):
            expected = evidence[kind]
            wrapper = local / f'{kind}-passive-{expected["attempt"]:02}.json'
            self.assertEqual(sha256(wrapper), expected["guard_sha256"])
            actual = observation(wrapper, kind)
            self.assertEqual(actual["receipt_sha256"], expected["receipt_sha256"])
            receipt = json.loads(Path(actual["receipt_path"]).read_text())
            self.assertEqual(receipt["environment"]["MVK_CONFIG_USE_METAL_PRIVATE_API"], "1")
            if kind == "vulkan":
                load = receipt["window_capture"]["private_moltenvk_load"]
                self.assertEqual(load["sha256"], evidence["moltenvk_sha256"])
                self.assertEqual(sha256(Path(load["path"])), load["sha256"])
                self.assertTrue(all(line.startswith(f'dyld[{load["owned_pid"]}]:')
                                    and load["path"] in line for line in load["dyld_lines"]))

    def test_private_emission_refuses_missing_runtime_binding(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            stdout = root / "stdout"
            stdout.write_text("wideLines supported=1 required=1 enabled=1\nvkCreateDevice VkResult=0\n")
            receipt = root / "receipt.json"
            receipt.write_text(json.dumps({
                "commands": [{"name": "create-device", "stdout_log": str(stdout)}],
                "environment": {"MVK_CONFIG_USE_METAL_PRIVATE_API": "1"},
            }))
            with patch.object(emit_vulkan_registry, "observation",
                              return_value={"receipt_path": str(receipt)}):
                with self.assertRaisesRegex(ValueError, "bound dylib"):
                    emit_vulkan_registry.emit(
                        {kind: root / kind for kind in
                         ("vulkan", "d3d11", "d3d12", "https", "https-expired")},
                        private_api=True)

    @unittest.skipUnless(RECORD.is_file(), "Requires actual local qualification")
    def test_frozen_local_record_matches_actual_observations_and_contract(self):
        evidence = json.loads((ROOT / "docs/evidence/req78-vulkan-qualification.json").read_text())
        self.assertEqual(sha256(RECORD), evidence["local_registry_sha256"])
        recipe = export_recipe(RECORD, evidence["engine_name"])
        self.assertEqual(recipe["engines"][0]["provider"], evidence["provider"])
        for kind, attempt, key in (
            ("vulkan", 1, "vulkan"), ("d3d12", 2, "d3d12"), ("d3d11", 3, "d3d11"),
            ("https", 4, "https"), ("https-expired", 5, "expired_https"),
        ):
            actual = observation(LOCAL / f"{kind}-passive-{attempt:02}.json", kind)
            self.assertEqual(actual["receipt_sha256"], evidence[key]["receipt_sha256"])

    def check(self, kind, stdout, stderr="", code=0, **overrides):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            out, err = root / "stdout.log", root / "stderr.log"
            out.write_text(stdout)
            err.write_text(stderr)
            step = {
                "name": "create-device", "command": ["owned.exe"], "exit_code": code,
                "timed_out": False, "stdout_log": str(out), "stderr_log": str(err),
                "stdout_sha256": sha256(out), "stderr_sha256": sha256(err),
            }
            receipt = {
                "payload_hashes_unchanged": True, "residual_process_groups": [],
                "prefix_open_files_check": {"exit_code": 1, "stdout": "", "stderr": ""},
                "commands": [step],
                "window_capture": {"nonoverlap": True}, "probe_sha256": "a" * 64,
                "environment": {}, "prefix": str(root / "prefix"),
            }
            receipt.update(overrides)
            path = root / "receipt.json"
            path.write_text(json.dumps(receipt))
            wrapper = root / "guard.json"
            wrapper.write_text(json.dumps({
                "probe": kind, "receipt": str(path),
                "foreground_unchanged": True, "port10_unchanged": True,
            }))
            return observation(wrapper, kind)

    def test_requires_all_120_actual_successful_presents_and_exact_pixel(self):
        text = ("vkQueuePresentKHR VkResult=0\n" * 120 +
                "readback RGBA=51,102,204,255 expected=51,102,204,255\n"
                "SUMMARY presented=120 expected=120 result=0\n")
        self.assertEqual(self.check("vulkan", text)["kind"], "vulkan")
        for altered in (text.replace("VkResult=0", "VkResult=-1", 1),
                        text.replace("RGBA=51", "RGBA=50"), text.replace("presented=120", "presented=119")):
            with self.assertRaises(ValueError):
                self.check("vulkan", altered)

    def test_rejects_payload_or_cleanup_failure(self):
        for value in ({"payload_hashes_unchanged": False}, {"residual_process_groups": [1]},
                      {"prefix_open_files_check": {"stdout": "123"}},
                      {"prefix_open_files_check": {"exit_code": 2, "stdout": "", "stderr": "failed"}},
                      {"prefix_open_files_check": {"exit_code": 1, "stdout": "", "stderr": "warning"}}):
            with self.subTest(value=value), self.assertRaises(ValueError):
                self.check("https", "HTTPS status=200 certificate_validation=enabled\nHTTPS result=0\n",
                           **value)

    def test_tls_requires_specific_success_and_honest_expired_failure(self):
        self.check("https", "HTTPS status=200 certificate_validation=enabled\nHTTPS result=0\n")
        self.check("https-expired", "", "cert verify failed: 12037\n", 1)
        for kind, stdout, stderr, code in (
            ("https", "failure 200", "", 0),
            ("https-expired", "", "network error", 1),
            ("https-expired", "", "cert verify failed: 12037\n", 0),
        ):
            with self.subTest(kind=kind), self.assertRaises(ValueError):
                self.check(kind, stdout, stderr, code)


if __name__ == "__main__":
    unittest.main()
