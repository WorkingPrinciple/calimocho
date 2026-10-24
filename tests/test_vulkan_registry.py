import json
from pathlib import Path
import tempfile
import unittest

from tools.emit_vulkan_registry import observation
from tools.probe_wine_source import sha256


class VulkanRegistryObservationTests(unittest.TestCase):
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
