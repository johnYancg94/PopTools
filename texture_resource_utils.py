import hashlib
import os
import re


IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".tga", ".tif", ".tiff", ".exr", ".psd", ".bmp", ".hdr"}


def sanitize_texture_filename_stem(name):
    stem = (name or "").strip()
    stem = re.sub(r"[<>:\"/\\|?*\x00-\x1f]+", "_", stem)
    stem = re.sub(r"\s+", "_", stem).strip("._ ")
    return stem or "texture"


def _normalized_path(path):
    return os.path.normcase(os.path.abspath(path))


def _root_rank(path, preferred_roots):
    normalized_path = _normalized_path(path)
    best = len(preferred_roots) + 1
    for index, root in enumerate(preferred_roots or []):
        normalized_root = _normalized_path(root)
        try:
            common = os.path.commonpath([normalized_path, normalized_root])
        except ValueError:
            continue
        if common == normalized_root:
            best = min(best, index)
    return best


def _match_rank(path, expected_name="", image_name=""):
    filename = os.path.basename(path).lower()
    stem = os.path.splitext(filename)[0]
    expected_filename = os.path.basename(expected_name or "").lower()
    expected_stem = os.path.splitext(expected_filename)[0]
    image_stem = os.path.splitext(os.path.basename(image_name or ""))[0].lower()

    if expected_filename and filename == expected_filename:
        return 0
    if expected_stem and stem == expected_stem:
        return 1
    if image_stem and stem == image_stem:
        return 2
    if expected_stem and (expected_stem in stem or stem in expected_stem):
        return 3
    if image_stem and (image_stem in stem or stem in image_stem):
        return 4
    return 99


def select_best_texture_candidate(candidates, expected_name="", image_name="", preferred_roots=None):
    valid_candidates = [
        path
        for path in candidates
        if os.path.splitext(path)[1].lower() in IMAGE_EXTENSIONS and os.path.isfile(path)
    ]
    if not valid_candidates:
        return ""

    def sort_key(path):
        normalized = os.path.abspath(path)
        return (
            _match_rank(path, expected_name, image_name),
            _root_rank(path, preferred_roots or []),
            normalized.count(os.sep),
            os.path.basename(path).lower(),
            normalized.lower(),
        )

    best = min(valid_candidates, key=sort_key)
    return best if _match_rank(best, expected_name, image_name) < 99 else ""


def select_best_scored_texture_candidate(scored_candidates, preferred_roots=None, min_score=1):
    valid_candidates = [
        (path, score)
        for path, score in scored_candidates
        if score >= min_score
        and os.path.splitext(path)[1].lower() in IMAGE_EXTENSIONS
        and os.path.isfile(path)
    ]
    if not valid_candidates:
        return ""

    def sort_key(item):
        path, score = item
        normalized = os.path.abspath(path)
        return (
            -score,
            _root_rank(path, preferred_roots or []),
            normalized.count(os.sep),
            os.path.basename(path).lower(),
            normalized.lower(),
        )

    return min(valid_candidates, key=sort_key)[0]


def unique_texture_target_path(texture_dir, source_path, max_collisions=9999):
    source_stem = os.path.splitext(os.path.basename(source_path))[0]
    base_name = sanitize_texture_filename_stem(source_stem)
    extension = os.path.splitext(source_path)[1] or ".png"
    target_path = os.path.join(texture_dir, f"{base_name}{extension}")
    if not os.path.exists(target_path) or os.path.abspath(source_path) == os.path.abspath(target_path):
        return target_path

    for index in range(1, max_collisions + 1):
        candidate = os.path.join(texture_dir, f"{base_name}_{index:02d}{extension}")
        if not os.path.exists(candidate):
            return candidate

    full_digest = hashlib.sha1(os.path.abspath(source_path).encode("utf-8")).hexdigest()
    short_target = os.path.join(texture_dir, f"{base_name}_{full_digest[:8]}{extension}")
    if not os.path.exists(short_target):
        return short_target
    return os.path.join(texture_dir, f"{base_name}_{full_digest}{extension}")
