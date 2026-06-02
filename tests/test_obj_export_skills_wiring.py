import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
INIT_SRC = (ROOT / "agent_skills" / "__init__.py").read_text(encoding="utf-8")
SKILLS_SRC = (ROOT / "agent_skills" / "obj_export_skills.py").read_text(encoding="utf-8")

NEW_SKILLS = {
    "EXPORT_OBJ_BATCH": {
        "skill_name": "poptools.export_obj_batch",
        "writes_files": True,
        "confirmation": "always",
    },
    "OPEN_EXPORT_DIR": {
        "skill_name": "poptools.open_export_dir",
        "launches_external": True,
        "confirmation": "always",
    },
}


def _skill_block(const_name):
    m = re.search(const_name + r"\s*=\s*\{(.*?)\n\}", SKILLS_SRC, re.DOTALL)
    return m.group(1) if m else None


class ObjExportSkillsWiringTests(unittest.TestCase):
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

    def test_export_obj_batch_writes_files(self):
        block = _skill_block("EXPORT_OBJ_BATCH")
        self.assertIn('"writes_files": True', block)
        self.assertIn('"requires_confirmation": "always"', block)
        self.assertIn('"undoable": False', block)

    def test_open_export_dir_launches_external(self):
        block = _skill_block("OPEN_EXPORT_DIR")
        self.assertIn('"launches_external_process": True', block)
        self.assertIn('"requires_confirmation": "always"', block)

    def test_export_path_param_is_output_path(self):
        """Plan requires path param named output_path for _build_risk_lines compat."""
        block = _skill_block("EXPORT_OBJ_BATCH")
        self.assertIn('"output_path"', block)


if __name__ == "__main__":
    unittest.main()
