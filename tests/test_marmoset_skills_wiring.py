import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
INIT_SRC = (ROOT / "agent_skills" / "__init__.py").read_text(encoding="utf-8")
SKILLS_SRC = (ROOT / "agent_skills" / "marmoset_skills.py").read_text(encoding="utf-8")

# skill const name -> expected metadata facts
NEW_SKILLS = {
    "AUTO_MARK_HIGH_LOW": {
        "skill_name": "poptools.auto_mark_high_low",
        "modifies_scene": True,
        "undoable": True,
        "confirmation": "first",
    },
    "SHOW_POLYCOUNT": {
        "skill_name": "poptools.show_polycount",
        "readonly": True,
    },
    "FIND_MISSING_TEXTURES": {
        "skill_name": "poptools.find_missing_textures",
        "readonly": True,
    },
    "GENERATE_LOWPOLY": {
        "skill_name": "poptools.generate_lowpoly",
        "modifies_scene": True,
        "undoable": True,
        "confirmation": "first",
    },
    "SECURE_TEXTURE_RESOURCES": {
        "skill_name": "poptools.secure_texture_resources",
        "writes_files": True,
        "confirmation": "always",
    },
    "AUTO_DETECT_TOOLBAG": {
        "skill_name": "poptools.auto_detect_toolbag",
        "readonly": True,
    },
}


def _skill_block(const_name):
    m = re.search(const_name + r"\s*=\s*\{(.*?)\n\}", SKILLS_SRC, re.DOTALL)
    return m.group(1) if m else None


class MarmosetSkillsWiringTests(unittest.TestCase):
    def test_all_skills_imported_and_listed(self):
        for const in NEW_SKILLS:
            self.assertIn(const, INIT_SRC, f"{const} not wired into __init__.py")
        list_block = re.search(r"_ALL_SKILLS\s*=\s*\[(.*?)\]", INIT_SRC, re.DOTALL).group(1)
        for const in NEW_SKILLS:
            self.assertIn(const, list_block, f"{const} missing from _ALL_SKILLS")

    def test_skill_names_and_owner(self):
        for const, facts in NEW_SKILLS.items():
            block = _skill_block(const)
            self.assertIsNotNone(block, f"could not locate {const} dict")
            self.assertIn(f'"name": "{facts["skill_name"]}"', block)
            self.assertIn('"owner": "poptools"', block)

    def test_readonly_skills_are_safe(self):
        for const in ("SHOW_POLYCOUNT", "FIND_MISSING_TEXTURES", "AUTO_DETECT_TOOLBAG"):
            block = _skill_block(const)
            self.assertIn('"modifies_scene": False', block)
            self.assertIn('"requires_confirmation": "never"', block)
            self.assertIn('"undoable": False', block)

    def test_mutating_skills_require_confirmation(self):
        for const in ("AUTO_MARK_HIGH_LOW", "GENERATE_LOWPOLY"):
            block = _skill_block(const)
            self.assertIn('"modifies_scene": True', block)
            self.assertIn('"undoable": True', block)
            self.assertNotIn('"requires_confirmation": "never"', block)

    def test_writes_files_skill_always_confirm(self):
        block = _skill_block("SECURE_TEXTURE_RESOURCES")
        self.assertIn('"writes_files": True', block)
        self.assertIn('"requires_confirmation": "always"', block)

    def test_show_polycount_no_overlay(self):
        """Plan P3: show_polycount must NOT trigger viewport overlay."""
        block = _skill_block("SHOW_POLYCOUNT")
        self.assertNotIn("ensure_polycount_overlay", block)
        self.assertNotIn("POLYCOUNT_OVERLAY", block)

    def test_find_missing_is_read_only(self):
        """Plan P3: find_missing_textures must NOT call smart_find_missing_textures."""
        # Check handler body, not skill dict (description may mention "relink")
        handler_match = re.search(
            r"def _handler_find_missing_textures\(.*?\n(.*?)(?=\ndef |\Z)",
            SKILLS_SRC, re.DOTALL
        )
        self.assertIsNotNone(handler_match, "handler not found")
        handler_body = handler_match.group(1)
        self.assertNotIn("smart_find_missing_textures", handler_body)
        self.assertNotIn("image.filepath", handler_body)


if __name__ == "__main__":
    unittest.main()
