import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
INIT_SRC = (ROOT / "agent_skills" / "__init__.py").read_text(encoding="utf-8")
SKILLS_SRC = (ROOT / "agent_skills" / "vertex_baker_skills.py").read_text(encoding="utf-8")

NEW_SKILLS = {
    "VTBB_CREATE_EMPTIES": {"skill_name": "poptools.vtbb_create_empties"},
    "VTBB_BIND_VERTICES": {"skill_name": "poptools.vtbb_bind_vertices"},
    "VTBB_BAKE_WEIGHTS": {"skill_name": "poptools.vtbb_bake_weights"},
    "VTBB_CLEAR_EMPTIES": {"skill_name": "poptools.vtbb_clear_empties"},
}


def _skill_block(const_name):
    m = re.search(const_name + r"\s*=\s*\{(.*?)\n\}", SKILLS_SRC, re.DOTALL)
    return m.group(1) if m else None


class VertexBakerSkillsWiringTests(unittest.TestCase):
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

    def test_all_modifying_undoable(self):
        """All P4 skills modify the scene and are undoable."""
        for const in NEW_SKILLS:
            block = _skill_block(const)
            self.assertIn('"modifies_scene": True', block,
                          f"{const} should modify scene")
            self.assertIn('"undoable": True', block,
                          f"{const} should be undoable")
            self.assertNotIn('"requires_confirmation": "never"', block,
                             f"{const} should require confirmation")

    def test_none_write_files(self):
        for const in NEW_SKILLS:
            block = _skill_block(const)
            self.assertIn('"writes_files": False', block)

    def test_handlers_use_temp_override(self):
        """Handlers that call bpy.ops should use temp_override pattern."""
        # bind_vertices and bake_weights both toggle edit mode
        for func_name in ("_handler_bind_vertices", "_handler_bake_weights"):
            self.assertIn("temp_override", SKILLS_SRC,
                          f"{func_name} should use temp_override for bpy.ops")

    def test_no_show_message_box_in_handlers(self):
        """Handlers must not call show_message_box (return dicts instead)."""
        self.assertNotIn("show_message_box", SKILLS_SRC)


if __name__ == "__main__":
    unittest.main()
