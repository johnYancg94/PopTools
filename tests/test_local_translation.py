import sys
import types
import unittest
import importlib
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PARENT = ROOT.parent
if str(PARENT) not in sys.path:
    sys.path.insert(0, str(PARENT))

if "bpy" not in sys.modules:
    bpy = types.ModuleType("bpy")
    bpy_types = types.ModuleType("bpy.types")
    bpy_types.Panel = object
    bpy_types.Operator = object
    bpy_types.PropertyGroup = object
    bpy_props = types.ModuleType("bpy.props")
    bpy_props.StringProperty = lambda **_kwargs: None
    bpy_props.EnumProperty = lambda **_kwargs: None
    bpy_props.BoolProperty = lambda **_kwargs: None
    bpy_props.CollectionProperty = lambda **_kwargs: None
    bpy.types = bpy_types
    bpy.props = bpy_props
    sys.modules["bpy"] = bpy
    sys.modules["bpy.types"] = bpy_types
    sys.modules["bpy.props"] = bpy_props

if "bmesh" not in sys.modules:
    sys.modules["bmesh"] = types.ModuleType("bmesh")

if "poptools.utils" not in sys.modules:
    utils = types.ModuleType("poptools.utils")
    utils.show_message_box = lambda *_args, **_kwargs: None
    sys.modules["poptools.utils"] = utils

if "poptools" not in sys.modules:
    poptools = types.ModuleType("poptools")
    poptools.__path__ = [str(ROOT)]
    sys.modules["poptools"] = poptools

translation_tools = importlib.import_module("poptools.translation_tools")


class LocalTranslationTests(unittest.TestCase):
    def test_exact_local_translation(self):
        self.assertEqual(translation_tools.local_rule_translate("果蔬篮"), "produceBasket")

    def test_token_local_translation(self):
        self.assertEqual(translation_tools.local_rule_translate("竹篮"), "bambooBasket")

    def test_enriched_dictionary_translation(self):
        self.assertEqual(translation_tools.local_rule_translate("木栅栏"), "woodenFence")

    def test_match_three_game_exact_translation(self):
        self.assertEqual(translation_tools.local_rule_translate("彩虹球"), "rainbowBall")

    def test_match_three_token_translation(self):
        self.assertEqual(translation_tools.local_rule_translate("横向火箭"), "horizontalRocket")

    def test_island_exact_translation(self):
        self.assertEqual(translation_tools.local_rule_translate("椰子树"), "coconutTree")

    def test_island_token_translation(self):
        self.assertEqual(translation_tools.local_rule_translate("破碎贝壳"), "brokenShell")

    def test_dictionary_file_loaded(self):
        self.assertIn("果蔬篮", translation_tools.LOCAL_TRANSLATION_EXACT)
        self.assertIn("栅栏", translation_tools.LOCAL_TRANSLATION_TOKENS)
        self.assertIn("彩虹球", translation_tools.LOCAL_TRANSLATION_EXACT)
        self.assertIn("海岛", translation_tools.LOCAL_TRANSLATION_TOKENS)

    def test_unknown_text_falls_back_to_ai(self):
        self.assertEqual(translation_tools.local_rule_translate("未收录资产"), "")


if __name__ == "__main__":
    unittest.main()
