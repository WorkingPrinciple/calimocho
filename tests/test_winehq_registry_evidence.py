import json
from pathlib import Path
import unittest


REPO = Path(__file__).resolve().parents[1]
RECORD = REPO / "docs/evidence/calimocho-wine11.20-gptk4b3.registry.json"


class WineHQRegistryEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.raw = RECORD.read_text()
        self.registry = json.loads(self.raw)
        self.entry = self.registry["engines"][0]

    def test_public_record_preserves_explicit_identity_and_required_helper(self):
        self.assertNotIn("/Users/", self.raw)
        self.assertEqual(self.registry["schema_version"], 1)
        self.assertEqual(len(self.registry["engines"]), 1)
        self.assertEqual(self.entry["name"], "calimocho-wine11.20-gptk4b3")
        self.assertEqual(self.entry["source_commit"],
                         "7298a818b79446bae153b8d5aa27235ab3703bf9")
        self.assertEqual(self.entry["kind"], "free")
        self.assertTrue(self.entry["local_only"])
        self.assertNotIn("WINEPREFIX", self.entry["environment"])
        self.assertNotIn("DYLD_INSERT_LIBRARIES", self.entry["environment"])
        self.assertEqual(self.entry["environment"]["WINELOADER"], self.entry["wine"])
        self.assertEqual(self.entry["environment"]["WINESERVER"], self.entry["wineserver"])
        helper = next(d for d in self.entry["dependencies"]
                      if d["name"] == "source-built native-GS time-slot helper")
        self.assertEqual(helper["load_command"], "LC_LOAD_DYLIB")
        self.assertEqual(helper["install_name"], "@loader_path/libnative-gs-localtime.dylib")
        self.assertEqual(helper["path"], self.entry["install_path"] +
                         "/lib/wine/x86_64-unix/libnative-gs-localtime.dylib")
        self.assertEqual(self.entry["prefix_overlays"], [])
        self.assertEqual(self.entry["prefix_registry_imports"], [])

    def test_observed_smoke_binds_exact_thresholds_and_existing_renderer_links(self):
        smoke = self.entry["smoke_test"]
        self.assertEqual(smoke["status"], "pass")
        self.assertEqual(smoke["environment"], self.entry["environment"])
        self.assertEqual(len(smoke["commands"]), len(smoke["exit_codes"]))
        self.assertTrue(smoke["commands"])
        self.assertTrue(all(code == 0 for code in smoke["exit_codes"]))
        self.assertEqual(smoke["wine_sha256"], self.entry["sha256"])
        self.assertEqual(smoke["present_count"], 120)
        self.assertEqual(smoke["readback_pixel_rgba"], [51, 102, 204, 255])
        self.assertFalse(smoke["game_launched"])
        self.assertTrue(smoke["apple_payload_hashes_unchanged"])
        self.assertEqual(smoke["residual_process_groups"], [])
        self.assertEqual(len(self.entry["gptk_symlink_map"]), 10)
        for link in self.entry["gptk_symlink_map"]:
            self.assertTrue(link["target"].startswith("$APPLEGPTK_ENGINE/"))
            self.assertRegex(link["target_sha256"], r"^[a-f0-9]{64}$")


class TLSRegistryEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.raw = (REPO / "docs/evidence/calimocho-wine11.20-gptk4b3-tls.registry.json"
                    ).read_text()
        self.entry = json.loads(self.raw)["engines"][0]

    def test_tls_record_binds_shared_library_closure_and_explicit_rpath(self):
        self.assertNotIn("/Users/", self.raw)
        self.assertEqual(self.entry["name"], "calimocho-wine11.20-gptk4b3-tls")
        self.assertNotIn("WINEPREFIX", self.entry["environment"])
        self.assertNotIn("DYLD_INSERT_LIBRARIES", self.entry["environment"])
        self.assertNotIn("winhttp", self.entry["environment"]["WINEDEBUG"])
        self.assertNotIn("schannel", self.entry["environment"]["WINEDEBUG"])
        self.assertIn("/tls-x86_64-01/prefix/lib:",
                      self.entry["environment"]["DYLD_FALLBACK_LIBRARY_PATH"])
        closure = {
            Path(d["path"]).name for d in self.entry["dependencies"]
            if d["name"].startswith("source-built TLS:")
        }
        self.assertEqual(closure, {"libgnutls.30.dylib", "libgmp.10.dylib",
                                   "libhogweed.7.0.dylib", "libnettle.9.0.dylib",
                                   "libtasn1.6.dylib"})
        self.assertEqual(self.entry["build_evidence"]["soname"],
                         "@rpath/libgnutls.30.dylib")
        self.assertTrue(self.entry["rpath_resolution_test"]["tls_fallback_removed"])
        self.assertEqual(self.entry["rpath_resolution_test"]["http_status"], 200)
        self.assertTrue(self.entry["integrity"]["base_install_sha256_comparison"]
                        ["only_overlay_modules_changed"])

    def test_tls_and_graphics_observations_do_not_hide_negative_exit_or_claim_game(self):
        self.assertEqual(self.entry["smoke_test"]["https_status"], 200)
        self.assertFalse(self.entry["smoke_test"]["game_launched"])
        negative = self.entry["tls_negative_test"]
        self.assertEqual(negative["status"], "expected-certificate-rejection-observed")
        self.assertEqual(negative["probe_exit_code"], 1)
        self.assertEqual(negative["winhttp_returned_error"], 12157)
        self.assertEqual(negative["wine_certificate_error"], 12037)
        self.assertFalse(negative["certificate_checks_bypassed"])
        self.assertEqual(len(self.entry["graphics_tests"]), 2)
        for run in self.entry["graphics_tests"]:
            self.assertEqual(run["probe_exit_code"], 0)
            self.assertEqual(run["present_count"], 120)
            self.assertEqual(run["readback_pixel_rgba"], [51, 102, 204, 255])
            self.assertTrue(run["pixel_matches_exactly"])
            self.assertFalse(run["input_sent"])
            self.assertFalse(run["focus_requested"])


if __name__ == "__main__":
    unittest.main()
