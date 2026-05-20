import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from retex_naming import build_texture_name_from_object_name


class ReTexNamingTests(unittest.TestCase):
    def test_replaces_mesh_prefix_with_tex_prefix(self):
        self.assertEqual(
            build_texture_name_from_object_name("mesh_strawstack_03"),
            "tex_strawstack_03",
        )

    def test_adds_tex_prefix_when_object_has_no_mesh_prefix(self):
        self.assertEqual(
            build_texture_name_from_object_name("strawstack_03"),
            "tex_strawstack_03",
        )

    def test_keeps_existing_tex_prefix(self):
        self.assertEqual(
            build_texture_name_from_object_name("tex_strawstack_03"),
            "tex_strawstack_03",
        )

    def test_applies_suffix_before_prefix_conversion(self):
        self.assertEqual(
            build_texture_name_from_object_name("mesh_strawstack_03", texture_suffix="clean"),
            "tex_strawstack_03_clean",
        )


if __name__ == "__main__":
    unittest.main()
