# -*- coding: utf-8 -*-
"""
TEMPLATE — wiring static check for new skills.

Copy to `poptools/tests/test_<domain>_skills_wiring.py` (or extend the existing
test_retex_skills_wiring.py). Skill modules import bpy, so we CANNOT import them
in a Blender-less CI; instead we check the source TEXT with regex.
See CONVENTIONS.md §11.

This template targets the real retex_skills.py so it runs as-is. For a new
domain, change SKILLS_SRC and the NEW_SKILLS table.
"""

import re
import unittest
from pathlib import Path


# From _TEMPLATES/, the poptools root is two levels up. In a real test copied
# to tests/, use: ROOT = Path(__file__).resolve().parents[1]
ROOT = Path(__file__).resolve().parents[2]
INIT_SRC = (ROOT / "agent_skills" / "__init__.py").read_text(encoding="utf-8")
SKILLS_SRC = (ROOT / "agent_skills" / "retex_skills.py").read_text(encoding="utf-8")

# const name -> facts to assert
NEW_SKILLS = {
    "CHECK_UVS": {"skill_name": "poptools.check_uvs", "readonly": True},
    "SMART_RENAME": {"skill_name": "poptools.smart_rename", "readonly": False},
}


def _block(const_name):
    m = re.search(const_name + r"\s*=\s*\{(.*?)\n\}", SKILLS_SRC, re.DOTALL)
    return m.group(1) if m else None


class WiringTests(unittest.TestCase):
    def test_imported_and_listed(self):
        list_block = re.search(r"_ALL_SKILLS\s*=\s*\[(.*?)\]", INIT_SRC, re.DOTALL).group(1)
        for const in NEW_SKILLS:
            self.assertIn(const, INIT_SRC, f"{const} not imported")
            self.assertIn(const, list_block, f"{const} missing from _ALL_SKILLS")

    def test_name_and_owner(self):
        for const, facts in NEW_SKILLS.items():
            block = _block(const)
            self.assertIsNotNone(block, f"{const} dict not found")
            self.assertIn(f'"name": "{facts["skill_name"]}"', block)
            self.assertIn('"owner": "poptools"', block)

    def test_metadata_matches_operation_type(self):
        for const, facts in NEW_SKILLS.items():
            block = _block(const)
            if facts["readonly"]:
                self.assertIn('"modifies_scene": False', block)
                self.assertIn('"requires_confirmation": "never"', block)
                self.assertIn('"undoable": False', block)
            else:
                self.assertIn('"modifies_scene": True', block)
                self.assertNotIn('"requires_confirmation": "never"', block)

    def test_names_unique(self):
        names = [f["skill_name"] for f in NEW_SKILLS.values()]
        self.assertEqual(len(names), len(set(names)), "duplicate skill names")


if __name__ == "__main__":
    unittest.main()
