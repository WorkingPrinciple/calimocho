import unittest

from tools.prepare_native_xaml_recipe import merge_overrides


class NativeXamlRecipeTests(unittest.TestCase):
    def test_retained_native_override_preserves_unrelated_baseline(self):
        result = merge_overrides("mscoree,mshtml=;amd_ags_x64=b",
                                 "mscoree,mshtml=;windows.ui.xaml=n")
        values = dict(item.split("=", 1) for item in result.split(";"))
        self.assertEqual(values, {"mscoree": "", "mshtml": "", "amd_ags_x64": "b",
                                  "windows.ui.xaml": "n"})

    def test_missing_native_only_or_malformed_settings_fail(self):
        for value in ("mscoree=", "windows.ui.xaml=b", "windows.ui.xaml=n,b",
                      "windows.ui.xaml", "windows.ui.xaml=n;SECRET=x"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                merge_overrides("mscoree,mshtml=", value)
