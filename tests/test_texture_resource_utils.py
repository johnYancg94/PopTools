import os
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from texture_resource_utils import (
    sanitize_texture_filename_stem,
    select_best_scored_texture_candidate,
    select_best_texture_candidate,
    unique_texture_target_path,
)


class TextureResourceUtilsTests(unittest.TestCase):
    def test_exact_filename_in_textures_beats_same_stem_elsewhere(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            textures = root / "textures"
            old = root / "old"
            textures.mkdir()
            old.mkdir()
            correct = textures / "wood_basecolor.png"
            stale = old / "wood_basecolor.jpg"
            correct.write_text("correct")
            stale.write_text("stale")

            selected = select_best_texture_candidate(
                [str(stale), str(correct)],
                expected_name="wood_basecolor.png",
                image_name="wood_basecolor",
                preferred_roots=[str(textures), str(root)],
            )

            self.assertEqual(os.path.abspath(selected), os.path.abspath(correct))

    def test_preferred_root_breaks_exact_filename_ties(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            textures = root / "textures"
            old = root / "old"
            textures.mkdir()
            old.mkdir()
            correct = textures / "normal.png"
            stale = old / "normal.png"
            correct.write_text("correct")
            stale.write_text("stale")

            selected = select_best_texture_candidate(
                [str(stale), str(correct)],
                expected_name="normal.png",
                image_name="normal",
                preferred_roots=[str(textures), str(root)],
            )

            self.assertEqual(os.path.abspath(selected), os.path.abspath(correct))

    def test_texture_filename_sanitizer_preserves_version_like_numeric_suffixes(self):
        self.assertEqual(sanitize_texture_filename_stem("tile_color.01"), "tile_color.01")
        self.assertEqual(sanitize_texture_filename_stem("asset.1001"), "asset.1001")

    def test_unique_texture_target_path_has_collision_fallback(self):
        with tempfile.TemporaryDirectory() as tmp:
            texture_dir = Path(tmp)
            source = texture_dir / "rock.png"
            source.write_text("existing")
            for index in range(1, 4):
                (texture_dir / f"rock_{index:02d}.png").write_text("collision")

            target = unique_texture_target_path(
                str(texture_dir),
                str(Path(tmp) / "other" / "rock.png"),
                max_collisions=3,
            )

            self.assertTrue(os.path.basename(target).startswith("rock_"))
            self.assertTrue(target.endswith(".png"))
            self.assertNotIn("rock_04.png", target)

    def test_scored_candidate_tie_prefers_textures_root(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            textures = root / "textures"
            old = root / "old"
            textures.mkdir()
            old.mkdir()
            correct = textures / "normal.png"
            stale = old / "normal.png"
            correct.write_text("correct")
            stale.write_text("stale")

            selected = select_best_scored_texture_candidate(
                [(str(stale), 80), (str(correct), 80)],
                preferred_roots=[str(textures), str(root)],
                min_score=20,
            )

            self.assertEqual(os.path.abspath(selected), os.path.abspath(correct))

    def test_unique_texture_target_path_checks_hash_fallback_collision(self):
        with tempfile.TemporaryDirectory() as tmp:
            texture_dir = Path(tmp)
            source = Path(tmp) / "other" / "stone.png"
            source.parent.mkdir()
            source.write_text("source")
            (texture_dir / "stone.png").write_text("base")

            import hashlib

            short_digest = hashlib.sha1(os.path.abspath(source).encode("utf-8")).hexdigest()[:8]
            full_digest = hashlib.sha1(os.path.abspath(source).encode("utf-8")).hexdigest()
            (texture_dir / f"stone_{short_digest}.png").write_text("collision")

            target = unique_texture_target_path(str(texture_dir), str(source), max_collisions=0)

            self.assertEqual(
                os.path.abspath(target),
                os.path.abspath(texture_dir / f"stone_{full_digest}.png"),
            )


if __name__ == "__main__":
    unittest.main()
