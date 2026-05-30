import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
INIT_SRC = (ROOT / "agent_skills" / "__init__.py").read_text(encoding="utf-8")
RETEX_SRC = (ROOT / "agent_skills" / "retex_skills.py").read_text(encoding="utf-8")

# skill const name -> expected metadata facts
NEW_SKILLS = {
    "CHECK_UVS": {"skill_name": "poptools.check_uvs", "readonly": True},
    "SMART_RENAME": {"skill_name": "poptools.smart_rename", "readonly": False},
    "ORGANIZE_MATERIALS": {"skill_name": "poptools.organize_materials", "readonly": False},
    "MARK_HIGH_LOW": {"skill_name": "poptools.mark_high_low", "readonly": False},
    "RENAME_BY_CATEGORY": {"skill_name": "poptools.rename_by_category", "readonly": False},
    "SET_TEXNAME_OF_OBJECT": {"skill_name": "poptools.set_texname_of_object", "readonly": False, "writes_files": True},
    "SYNC_TEXTURE_NAMES": {"skill_name": "poptools.sync_texture_names", "readonly": False, "writes_files": True},
    "ADJUST_SERIAL_NUMBER": {"skill_name": "poptools.adjust_serial_number", "readonly": False},
}


def _skill_block(const_name):
    """Return the dict literal text for a given top-level skill constant."""
    m = re.search(const_name + r"\s*=\s*\{(.*?)\n\}", RETEX_SRC, re.DOTALL)
    return m.group(1) if m else None


class RetexSkillsWiringTests(unittest.TestCase):
    def test_all_new_skills_imported_and_listed(self):
        for const in NEW_SKILLS:
            self.assertIn(const, INIT_SRC, f"{const} not wired into __init__.py")
        # All four appear inside the _ALL_SKILLS list.
        list_block = re.search(r"_ALL_SKILLS\s*=\s*\[(.*?)\]", INIT_SRC, re.DOTALL).group(1)
        for const in NEW_SKILLS:
            self.assertIn(const, list_block, f"{const} missing from _ALL_SKILLS")

    def test_skill_names_and_owner(self):
        for const, facts in NEW_SKILLS.items():
            block = _skill_block(const)
            self.assertIsNotNone(block, f"could not locate {const} dict")
            self.assertIn(f'"name": "{facts["skill_name"]}"', block)
            self.assertIn('"owner": "poptools"', block)

    def test_readonly_skill_is_safe(self):
        block = _skill_block("CHECK_UVS")
        self.assertIn('"modifies_scene": False', block)
        self.assertIn('"requires_confirmation": "never"', block)
        self.assertIn('"undoable": False', block)

    def test_mutating_skills_require_confirmation(self):
        for const in ("SMART_RENAME", "ORGANIZE_MATERIALS", "MARK_HIGH_LOW",
                       "RENAME_BY_CATEGORY", "ADJUST_SERIAL_NUMBER"):
            block = _skill_block(const)
            self.assertIn('"modifies_scene": True', block)
            self.assertNotIn('"requires_confirmation": "never"', block)

    def test_writes_files_skills_always_confirm(self):
        for const, facts in NEW_SKILLS.items():
            if facts.get("writes_files"):
                block = _skill_block(const)
                self.assertIn('"writes_files": True', block)
                self.assertIn('"requires_confirmation": "always"', block)


if __name__ == "__main__":
    unittest.main()
