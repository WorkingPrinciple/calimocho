"""Source-only invariants for REQ-104's width-parameterized shader oracle."""

import unittest

from make_sampler_probe import shader


class FixtureTests(unittest.TestCase):
    def test_every_descriptor_is_sampled_once(self):
        for width in (17, 32, 64, 128):
            for mode in ("regular", "push", "mixed", "graphics", "combined"):
                with self.subTest(width=width, mode=mode):
                    source = shader(mode, width)
                    self.assertEqual(source.count("OpImageSampleExplicitLod"), width)
                    operation = "OpBitwiseOr" if width == 17 else "OpIAdd"
                    self.assertEqual(source.count(operation), width)

    def test_combined_has_no_extra_image(self):
        for width in (17, 32, 64, 128):
            source = shader("combined", width)
            self.assertNotIn("OpDecorate %image ", source)
            self.assertNotIn("%image = OpVariable", source)
            self.assertNotIn("%tex = OpLoad", source)
            self.assertIn(f"%array = OpTypeArray %sampled %u{width}", source)

    def test_mixed_partitions_cover_the_width(self):
        for width in (17, 32, 64, 128):
            source = shader("mixed", width)
            self.assertIn(f"%array = OpTypeArray %sampler %u{width // 2}", source)
            self.assertIn(f"%array2 = OpTypeArray %sampler %u{width - width // 2}", source)

    def test_weighted_outputs_do_not_overflow(self):
        for width in (32, 64, 128):
            first = sum(i + 1 for i in range(width) if i % 2)
            second = sum(i + 1 for i in range(width) if not i % 2)
            self.assertEqual(first, (width // 2) * (width // 2 + 1))
            self.assertEqual(second, (width // 2) ** 2)
            self.assertLess(first + second, 2**32)


if __name__ == "__main__":
    unittest.main()
