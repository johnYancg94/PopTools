# -*- coding: utf-8 -*-
"""
Marmoset Toolbag one-click baking bridge.

MVP scope:
- identify Blender meshes by _low and _high suffixes
- export selected or scene meshes to one FBX
- generate a Toolbag boot script
- bake Normal, AO, and Curvature maps
- apply baked Normal/AO texture nodes back to low-poly materials
"""

import json
import os
import re
import shutil
import subprocess
import time
import glob

import bpy
import blf
from bpy_extras import view3d_utils
from bpy.types import Operator, Panel
from mathutils import Vector

from .utils import get_addon_preferences
from .translation_tools import (
    advance_ai_translate_job_progress,
    clear_ai_translate_job,
    get_ai_translate_job,
    start_ai_translate_job,
)
from .font_utils import get_mikado_black_font_id
from . import texture_resource_utils as texture_utils


LOW_SUFFIX = "_low"
HIGH_SUFFIX = "_high"
ACTIVE_BAKE_JOB = None
POLYCOUNT_OVERLAY_HANDLER = None
POLYCOUNT_OVERLAY_OBJECT_NAMES = []
POLYCOUNT_OVERLAY_COUNTS = {}
MARMORSET_MODEL_TRANSLATE_JOB_KEY = "marmoset_model_name"
MARMORSET_MODEL_TRANSLATE_PROMPT = (
    "你正在为游戏资产生成英文命名片段，用于unity游戏资产模型命名。"
    "请把输入转换成符合游戏开发习惯的简洁英文，不要直译成长词。"
    "要求："
    "1. 只返回结果，不要解释；"
    "2. 优先使用游戏行业常见简称和习惯叫法，例如 金币 -> coin，不要输出 goldcoin；"
    "3. 结果不要包含下划线、空格、连字符或其他符号；"
    "4. 多词请直接使用 lowerCamelCase；"
    "5. 保持简洁准确，避免冗长描述。"
)


def poll_marmoset_model_name_translation():
    job = advance_ai_translate_job_progress(MARMORSET_MODEL_TRANSLATE_JOB_KEY)
    scene = bpy.context.scene
    if not scene or not hasattr(scene, "poptools_props"):
        return None

    settings = scene.poptools_props.marmoset_baker_settings
    if not job:
        settings.model_name_translate_in_progress = False
        return None

    settings.model_name_translate_progress = float(job.get("progress", 0.0))
    settings.model_name_translate_status = job.get("message", "")

    if job.get("state") == "running":
        settings.model_name_translate_in_progress = True
        screen = bpy.context.screen
        if screen:
            for area in screen.areas:
                area.tag_redraw()
        return 0.2

    settings.model_name_translate_in_progress = False
    settings.model_name_translate_progress = 1.0
    translated = normalize_identifier(job.get("translated_text", ""))
    if job.get("state") == "done" and translated:
        settings.model_name_prefix = translated
        settings.model_name_translate_status = "AI翻译完成"
    else:
        settings.model_name_translate_status = job.get("error", "AI翻译失败")

    clear_ai_translate_job(MARMORSET_MODEL_TRANSLATE_JOB_KEY)
    screen = bpy.context.screen
    if screen:
        for area in screen.areas:
            area.tag_redraw()
    return None


def tag_view3d_redraw():
    screen = bpy.context.screen
    if not screen:
        return
    for area in screen.areas:
        if area.type == "VIEW_3D":
            area.tag_redraw()


def count_mesh_faces_and_tris(obj, depsgraph=None):
    mesh = obj.data
    evaluated_obj = None
    if depsgraph:
        try:
            evaluated_obj = obj.evaluated_get(depsgraph)
            mesh = evaluated_obj.to_mesh()
        except Exception:
            mesh = obj.data
            evaluated_obj = None

    face_count = len(mesh.polygons)
    tri_count = sum(max(1, len(poly.vertices) - 2) for poly in mesh.polygons)
    if evaluated_obj:
        evaluated_obj.to_mesh_clear()
    return face_count, tri_count


def polycount_color(tri_count):
    if tri_count < 5000:
        return (0.18, 0.9, 0.32, 1.0)
    if tri_count <= 12000:
        return (0.2, 0.55, 1.0, 1.0)
    if tri_count <= 25000:
        return (1.0, 0.86, 0.12, 1.0)
    if tri_count <= 45000:
        return (1.0, 0.48, 0.08, 1.0)
    return (1.0, 0.18, 0.12, 1.0)


def object_label_world_position(obj):
    world_corners = [obj.matrix_world @ Vector(corner) for corner in obj.bound_box]
    if not world_corners:
        return obj.location

    center_x = sum(corner.x for corner in world_corners) / len(world_corners)
    center_y = sum(corner.y for corner in world_corners) / len(world_corners)
    top_z = max(corner.z for corner in world_corners)
    height = max(corner.z for corner in world_corners) - min(corner.z for corner in world_corners)
    return Vector((center_x, center_y, top_z + max(height * 0.08, 0.08)))


def draw_text_segment(font_id, x, y, text, color):
    blf.position(font_id, x, y, 0)
    blf.color(font_id, *color)
    blf.draw(font_id, text)


def draw_outlined_text_segment(font_id, x, y, text, color):
    outline_color = (1.0, 1.0, 1.0, 1.0)
    outline_offsets = [
        (-2, -2), (-2, 0), (-2, 2),
        (0, -2), (0, 2),
        (2, -2), (2, 0), (2, 2),
    ]
    for offset_x, offset_y in outline_offsets:
        draw_text_segment(font_id, x + offset_x, y + offset_y, text, outline_color)
    draw_text_segment(font_id, x, y, text, color)


def draw_polycount_text(x, y, tri_count, color):
    font_id = get_mikado_black_font_id()
    font_size = 44
    try:
        blf.size(font_id, font_size)
    except TypeError:
        blf.size(font_id, font_size, 72)

    label = "Tris: "
    value = f"{tri_count:,}"
    draw_text_segment(font_id, x, y, label, color)
    label_width = blf.dimensions(font_id, label)[0]
    draw_outlined_text_segment(font_id, x + label_width, y, value, color)


def draw_polycount_overlay():
    context = bpy.context
    region = context.region
    region_data = context.region_data
    if not region or not region_data:
        return

    for obj_name in list(POLYCOUNT_OVERLAY_OBJECT_NAMES):
        obj = bpy.data.objects.get(obj_name)
        if not obj or obj.type != "MESH":
            continue

        screen_pos = view3d_utils.location_3d_to_region_2d(
            region,
            region_data,
            object_label_world_position(obj),
        )
        if not screen_pos:
            continue

        face_count, tri_count = POLYCOUNT_OVERLAY_COUNTS.get(obj_name) or count_mesh_faces_and_tris(obj)
        draw_polycount_text(
            screen_pos.x,
            screen_pos.y,
            tri_count,
            polycount_color(tri_count),
        )


def ensure_polycount_overlay():
    global POLYCOUNT_OVERLAY_HANDLER
    if POLYCOUNT_OVERLAY_HANDLER is None:
        POLYCOUNT_OVERLAY_HANDLER = bpy.types.SpaceView3D.draw_handler_add(
            draw_polycount_overlay,
            (),
            "WINDOW",
            "POST_PIXEL",
        )
    tag_view3d_redraw()


def clear_polycount_overlay():
    global POLYCOUNT_OVERLAY_HANDLER
    POLYCOUNT_OVERLAY_OBJECT_NAMES.clear()
    POLYCOUNT_OVERLAY_COUNTS.clear()
    if POLYCOUNT_OVERLAY_HANDLER is not None:
        bpy.types.SpaceView3D.draw_handler_remove(POLYCOUNT_OVERLAY_HANDLER, "WINDOW")
        POLYCOUNT_OVERLAY_HANDLER = None
    tag_view3d_redraw()

MAP_DEFINITIONS = {
    "normal": {
        "prop": "bake_normal",
        "marmoset_names": ["Normals", "Normal"],
        "canonical_suffix": "_normal",
        "suffixes": ["normal", "normals", "nrm"],
        "material_kind": "NORMAL",
    },
    "ao": {
        "prop": "bake_ao",
        "marmoset_names": ["Ambient Occlusion", "AO"],
        "canonical_suffix": "_ao",
        "suffixes": ["ao", "ambient_occlusion", "ambientocclusion"],
        "material_kind": "AO",
    },
    "albedo": {
        "prop": "bake_albedo",
        "marmoset_names": ["Albedo"],
        "canonical_suffix": "_albedo",
        "suffixes": ["albedo", "base_color", "basecolor", "diffuse"],
        "material_kind": "ALBEDO",
    },
    "curvature": {
        "prop": "bake_curvature",
        "marmoset_names": ["Curvature"],
        "canonical_suffix": "_curvature",
        "suffixes": ["curvature", "cavity"],
        "material_kind": None,
    },
}


def clean_base_name(name):
    clean_name = re.sub(r"\.\d+$", "", name or "")
    lowered = clean_name.lower()
    for suffix in (LOW_SUFFIX, HIGH_SUFFIX):
        if lowered.endswith(suffix):
            return clean_name[: -len(suffix)]
    return clean_name


def get_bake_role(obj):
    lowered = (obj.name or "").lower()
    if lowered.endswith(LOW_SUFFIX):
        return "LOW"
    if lowered.endswith(HIGH_SUFFIX):
        return "HIGH"
    return None


def mesh_complexity(obj):
    data = getattr(obj, "data", None)
    if not data:
        return 0
    return len(getattr(data, "polygons", [])) or len(getattr(data, "vertices", []))


def normalize_identifier(name):
    cleaned = re.sub(r"\.\d+$", "", name or "")
    cleaned = re.sub(r"[^0-9a-zA-Z_]+", "_", cleaned).strip("_")
    return cleaned or "marmoset_bake"


def rename_mesh_data(obj):
    if getattr(obj, "data", None):
        obj.data.name = obj.name


def selected_meshes(context):
    return [obj for obj in context.selected_objects if obj.type == "MESH"]


def build_pair_base_name(prefix, fallback_name, index, total):
    base = normalize_identifier(prefix or clean_base_name(fallback_name))
    if total > 1:
        return f"{base}{index + 1:02d}"
    return base


def infer_high_low_pairs(objects, prefix=""):
    pairs = []
    sorted_objects = sorted(objects, key=lambda obj: mesh_complexity(obj))
    if len(sorted_objects) < 2:
        return [], list(objects)

    pair_count = len(sorted_objects) // 2
    lows = sorted_objects[:pair_count]
    highs = sorted_objects[pair_count:]
    highs = sorted(highs, key=lambda obj: mesh_complexity(obj))

    for index, low_obj in enumerate(lows):
        high_obj = highs[index] if index < len(highs) else None
        if not high_obj:
            continue
        base_name = build_pair_base_name(prefix, high_obj.name, index, pair_count)
        low_obj.name = f"{base_name}{LOW_SUFFIX}"
        high_obj.name = f"{base_name}{HIGH_SUFFIX}"
        rename_mesh_data(low_obj)
        rename_mesh_data(high_obj)
        pairs.append({"base_name": base_name, "low": low_obj, "high": high_obj})

    leftovers = sorted_objects[pair_count * 2:]
    return pairs, leftovers


def infer_one_to_one_pairs(objects, prefix=""):
    tagged_lows, tagged_highs, untagged = split_high_low(objects)
    leftovers = list(untagged)
    lows_by_base = {}
    highs_by_base = {}
    for low_obj in tagged_lows:
        base_name = clean_base_name(low_obj.name).lower()
        if base_name in lows_by_base:
            leftovers.append(low_obj)
        else:
            lows_by_base[base_name] = low_obj
    for high_obj in tagged_highs:
        base_name = clean_base_name(high_obj.name).lower()
        if base_name in highs_by_base:
            leftovers.append(high_obj)
        else:
            highs_by_base[base_name] = high_obj

    pairs = []
    matched_bases = sorted(set(lows_by_base) & set(highs_by_base))
    for match_base in matched_bases:
        low_obj = lows_by_base[match_base]
        high_obj = highs_by_base[match_base]
        base_name = normalize_identifier(prefix or clean_base_name(high_obj.name))
        pairs.append({"base_name": base_name, "low": low_obj, "high": high_obj})

    for base_name, low_obj in lows_by_base.items():
        if base_name not in highs_by_base:
            leftovers.append(low_obj)
    for base_name, high_obj in highs_by_base.items():
        if base_name not in lows_by_base:
            leftovers.append(high_obj)
    return pairs, leftovers


def infer_many_to_many_group(objects, prefix=""):
    objects = [obj for obj in objects if obj.type == "MESH"]
    if len(objects) < 2:
        return None, list(objects)

    tagged_lows, tagged_highs, untagged = split_high_low(objects)
    if untagged:
        return None, untagged

    lows_by_base = {}
    highs_by_base = {}
    leftovers = []
    for low_obj in tagged_lows:
        base_name = clean_base_name(low_obj.name).lower()
        if base_name in lows_by_base:
            leftovers.append(low_obj)
        else:
            lows_by_base[base_name] = low_obj
    for high_obj in tagged_highs:
        base_name = clean_base_name(high_obj.name).lower()
        if base_name in highs_by_base:
            leftovers.append(high_obj)
        else:
            highs_by_base[base_name] = high_obj
    for base_name, low_obj in lows_by_base.items():
        if base_name not in highs_by_base:
            leftovers.append(low_obj)
    for base_name, high_obj in highs_by_base.items():
        if base_name not in lows_by_base:
            leftovers.append(high_obj)
    if leftovers:
        return None, leftovers

    matched_bases = sorted(set(lows_by_base) & set(highs_by_base))
    if not matched_bases:
        return None, objects

    pairs = [
        {
            "base_name": normalize_identifier(clean_base_name(highs_by_base[base_name].name)),
            "low": lows_by_base[base_name],
            "high": highs_by_base[base_name],
        }
        for base_name in matched_bases
    ]
    lows = [pair["low"] for pair in pairs]
    highs = [pair["high"] for pair in pairs]
    reference_high = max(highs, key=lambda obj: mesh_complexity(obj))
    base_name = normalize_identifier(prefix or clean_base_name(reference_high.name))

    return {
        "base_name": base_name,
        "lows": lows,
        "highs": highs,
        "pairs": pairs,
        "reference_high": reference_high,
    }, []


def infer_many_to_one_group(objects, prefix=""):
    objects = [obj for obj in objects if obj.type == "MESH"]
    if len(objects) < 2:
        return None, list(objects)

    tagged_lows, tagged_highs, untagged = split_high_low(objects)
    if untagged:
        return None, untagged
    if not tagged_lows or not tagged_highs:
        return None, objects

    lows = list(tagged_lows)
    highs = list(tagged_highs)
    reference_high = max(highs, key=lambda obj: mesh_complexity(obj))
    fallback_name = tagged_lows[0].name if len(tagged_lows) == 1 else reference_high.name
    base_name = normalize_identifier(prefix or clean_base_name(fallback_name))

    return {
        "base_name": base_name,
        "lows": lows,
        "highs": highs,
        "pairs": [],
        "reference_high": reference_high,
    }, []


def get_candidate_meshes(context, settings):
    if settings.bake_scope == "SCENE":
        return [obj for obj in context.scene.objects if obj.type == "MESH"]
    return [obj for obj in context.selected_objects if obj.type == "MESH"]


def split_high_low(objects):
    lows = []
    highs = []
    untagged = []

    for obj in objects:
        role = get_bake_role(obj)
        if role == "LOW":
            lows.append(obj)
        elif role == "HIGH":
            highs.append(obj)
        else:
            untagged.append(obj)

    return lows, highs, untagged


def mesh_has_uv(obj):
    data = getattr(obj, "data", None)
    uv_layers = getattr(data, "uv_layers", None)
    return bool(uv_layers and len(uv_layers) > 0)


def missing_uv_mesh_names(objects):
    return [obj.name for obj in objects if not mesh_has_uv(obj)]


def align_lows_to_high_origins(pairs):
    original_matrices = {}
    moved = []
    for pair in pairs:
        low_obj = pair.get("low")
        high_obj = pair.get("high")
        if not low_obj or not high_obj:
            continue
        low_origin = low_obj.matrix_world.translation
        high_origin = high_obj.matrix_world.translation
        if (low_origin - high_origin).length < 0.000001:
            continue
        original_matrices[low_obj.name] = low_obj.matrix_world.copy()
        aligned_matrix = low_obj.matrix_world.copy()
        aligned_matrix.translation = high_origin
        low_obj.matrix_world = aligned_matrix
        moved.append(low_obj.name)
    bpy.context.view_layer.update()
    return original_matrices, moved


def align_objects_to_origin(objects, target_obj):
    original_matrices = {}
    moved = []
    if not target_obj:
        return original_matrices, moved
    target_origin = target_obj.matrix_world.translation
    for obj in objects:
        obj_origin = obj.matrix_world.translation
        if (obj_origin - target_origin).length < 0.000001:
            continue
        original_matrices[obj.name] = obj.matrix_world.copy()
        aligned_matrix = obj.matrix_world.copy()
        aligned_matrix.translation = target_origin
        obj.matrix_world = aligned_matrix
        moved.append(obj.name)
    bpy.context.view_layer.update()
    return original_matrices, moved


def restore_low_locations(original_matrices):
    for object_name, matrix_world in original_matrices.items():
        obj = bpy.data.objects.get(object_name)
        if obj:
            obj.matrix_world = matrix_world
    if original_matrices:
        bpy.context.view_layer.update()


def clear_low_materials_for_export(lows):
    cleared = []
    for obj in lows:
        data = getattr(obj, "data", None)
        if not data:
            continue
        if data.materials:
            data.materials.clear()
            cleared.append(obj.name)
    return cleared


def apply_decimate_to_objects(context, objects, ratio):
    if context.mode != "OBJECT":
        bpy.ops.object.mode_set(mode="OBJECT")

    ratio = max(0.0001, min(1.0, float(ratio)))
    processed = 0
    previous_active = context.view_layer.objects.active
    previous_selection = list(context.selected_objects)

    try:
        for obj in objects:
            if obj.type != "MESH":
                continue
            for selected in context.selected_objects:
                selected.select_set(False)
            obj.select_set(True)
            context.view_layer.objects.active = obj

            decimate = obj.modifiers.new(name="High Asset Decimate", type="DECIMATE")
            decimate.decimate_type = "COLLAPSE"
            decimate.ratio = ratio
            bpy.ops.object.modifier_apply(modifier=decimate.name)
            processed += 1
    finally:
        if context.mode != "OBJECT":
            bpy.ops.object.mode_set(mode="OBJECT")
        for obj in context.scene.objects:
            obj.select_set(False)
        for obj in previous_selection:
            if obj.name in bpy.data.objects:
                obj.select_set(True)
        if previous_active and previous_active.name in bpy.data.objects:
            context.view_layer.objects.active = previous_active

    return processed


def insert_base_color_adjustment_nodes(material):
    if not material or not material.use_nodes or not material.node_tree:
        return False

    tree = material.node_tree
    processed = False
    for node in tree.nodes:
        if node.bl_idname != "ShaderNodeBsdfPrincipled":
            continue
        roughness = node.inputs.get("Roughness")
        if roughness:
            roughness.default_value = 0.5
            processed = True
        base_color = node.inputs.get("Base Color")
        if not base_color or not base_color.is_linked:
            continue

        existing_link = base_color.links[0]
        source_socket = existing_link.from_socket
        source_node = existing_link.from_node
        if source_node.bl_idname in {"ShaderNodeHueSaturation", "ShaderNodeRGBCurve"}:
            continue

        tree.links.remove(existing_link)
        hue_node = tree.nodes.new(type="ShaderNodeHueSaturation")
        hue_node.location = (source_node.location.x + 220, source_node.location.y)
        hue_node.inputs["Hue"].default_value = 0.49
        hue_node.inputs["Saturation"].default_value = 1.25

        curve_node = tree.nodes.new(type="ShaderNodeRGBCurve")
        curve_node.location = (hue_node.location.x + 220, hue_node.location.y)

        tree.links.new(source_socket, hue_node.inputs["Color"])
        tree.links.new(hue_node.outputs["Color"], curve_node.inputs["Color"])
        tree.links.new(curve_node.outputs["Color"], base_color)
        processed = True

    return processed


def insert_base_color_adjustments(objects):
    changed = 0
    seen_materials = set()
    for obj in objects:
        for slot in getattr(obj, "material_slots", []):
            material = slot.material
            if not material or material.name in seen_materials:
                continue
            seen_materials.add(material.name)
            if insert_base_color_adjustment_nodes(material):
                changed += 1
    return changed


def iter_node_tree_image_users(node_tree, owner_label, node_types):
    if not node_tree:
        return
    for node in getattr(node_tree, "nodes", []):
        if node.type in node_types and getattr(node, "image", None):
            yield owner_label, node, node.image


def iter_texture_image_users():
    shader_image_nodes = {"TEX_IMAGE", "TEX_ENVIRONMENT"}
    for obj in bpy.data.objects:
        if obj.type != "MESH":
            continue
        for slot in getattr(obj, "material_slots", []):
            material = slot.material
            node_tree = getattr(material, "node_tree", None)
            if not material or not getattr(material, "use_nodes", False) or not node_tree:
                continue
            owner_label = f"{obj.name}/{material.name}"
            yield from iter_node_tree_image_users(node_tree, owner_label, shader_image_nodes)

    for world in bpy.data.worlds:
        node_tree = getattr(world, "node_tree", None)
        if not world or not getattr(world, "use_nodes", False) or not node_tree:
            continue
        yield from iter_node_tree_image_users(node_tree, f"World/{world.name}", shader_image_nodes)

    for scene in bpy.data.scenes:
        node_tree = getattr(scene, "node_tree", None)
        if not scene or not getattr(scene, "use_nodes", False) or not node_tree:
            continue
        yield from iter_node_tree_image_users(node_tree, f"Scene/{scene.name}/Compositor", {"IMAGE"})


def image_is_packed(image):
    return bool(getattr(image, "packed_file", None) or getattr(image, "packed_files", None))


def image_is_regular_file(image):
    return getattr(image, "source", "FILE") == "FILE"


def image_source_path(image):
    filepath = getattr(image, "filepath", "")
    if not filepath:
        return ""
    return bpy.path.abspath(filepath)


def texture_search_roots(original_path="", work_dir=""):
    roots = []
    blend_dir = bpy.path.abspath("//")
    if blend_dir and os.path.isdir(blend_dir):
        roots.append(os.path.join(blend_dir, "textures"))
        roots.append(blend_dir)
    if work_dir and os.path.isdir(work_dir):
        roots.append(os.path.join(work_dir, "textures"))

    unique_roots = []
    seen = set()
    for root in roots:
        normalized = os.path.abspath(root)
        if normalized in seen or not os.path.isdir(normalized):
            continue
        seen.add(normalized)
        unique_roots.append(normalized)
    return unique_roots


def find_texture_candidate(image, original_path, work_dir=""):
    expected_name = os.path.basename(original_path) if original_path else ""
    roots = texture_search_roots(original_path, work_dir)

    if expected_name:
        exact_candidates = []
        expected_lower = expected_name.lower()
        for root in roots:
            direct = os.path.join(root, expected_name)
            if os.path.isfile(direct):
                exact_candidates.append(direct)
            for current_root, dirs, files in os.walk(root):
                dirs.sort()
                files.sort()
                for filename in files:
                    extension = os.path.splitext(filename)[1].lower()
                    if extension not in texture_utils.IMAGE_EXTENSIONS:
                        continue
                    if filename.lower() == expected_lower:
                        exact_candidates.append(os.path.join(current_root, filename))
        if exact_candidates:
            return texture_utils.select_best_texture_candidate(
                exact_candidates,
                expected_name=expected_name,
                image_name=getattr(image, "name", ""),
                preferred_roots=roots,
            )

    candidates = []
    for root in roots:
        for current_root, dirs, files in os.walk(root):
            dirs.sort()
            files.sort()
            for filename in files:
                extension = os.path.splitext(filename)[1].lower()
                if extension not in texture_utils.IMAGE_EXTENSIONS:
                    continue
                candidates.append(os.path.join(current_root, filename))

    return texture_utils.select_best_texture_candidate(
        candidates,
        expected_name=expected_name,
        image_name=getattr(image, "name", ""),
        preferred_roots=roots,
    )


def normalized_search_tokens(*values):
    tokens = []
    seen = set()
    for value in values:
        for part in re.split(r"[^0-9a-zA-Z]+", value or ""):
            part = part.lower().strip()
            if len(part) < 3 or part in seen:
                continue
            seen.add(part)
            tokens.append(part)
    return tokens


def texture_kind_tokens(node):
    text = " ".join([
        getattr(node, "name", ""),
        getattr(node, "label", ""),
        getattr(getattr(node, "image", None), "name", ""),
    ]).lower()
    groups = {
        "basecolor": ["basecolor", "base_color", "albedo", "diffuse", "diff", "color", "colour", "col"],
        "normal": ["normal", "norm", "nrm"],
        "roughness": ["roughness", "rough", "rgh"],
        "metallic": ["metallic", "metalness", "metal"],
        "ao": ["ao", "occlusion", "ambient"],
    }
    for keywords in groups.values():
        if any(keyword in text for keyword in keywords):
            return keywords
    return []


def score_texture_candidate(path, expected_names, tokens, kind_tokens):
    filename = os.path.basename(path).lower()
    stem = os.path.splitext(filename)[0]
    score = 0
    for expected_name in expected_names:
        expected_filename = os.path.basename(expected_name).lower()
        expected_stem = os.path.splitext(expected_filename)[0]
        if expected_filename and filename == expected_filename:
            score += 100
        elif expected_stem and stem == expected_stem:
            score += 80
        elif expected_stem and (expected_stem in stem or stem in expected_stem):
            score += 45
    for token in tokens:
        if token in stem:
            score += 8
    if kind_tokens and any(token in stem for token in kind_tokens):
        score += 20
    return score


def find_texture_candidate_smart(owner_label, node, image, original_path, work_dir=""):
    expected_names = [
        os.path.basename(original_path) if original_path else "",
        getattr(image, "name", ""),
        getattr(node, "name", ""),
        getattr(node, "label", ""),
    ]
    tokens = normalized_search_tokens(
        os.path.splitext(os.path.basename(original_path or ""))[0],
        image.name,
        node.name,
        node.label,
        owner_label,
    )
    kind_tokens = texture_kind_tokens(node)
    scored_candidates = []
    roots = texture_search_roots(original_path, work_dir)

    for root in roots:
        for current_root, dirs, files in os.walk(root):
            dirs.sort()
            files.sort()
            for filename in files:
                extension = os.path.splitext(filename)[1].lower()
                if extension not in texture_utils.IMAGE_EXTENSIONS:
                    continue
                path = os.path.join(current_root, filename)
                score = score_texture_candidate(path, expected_names, tokens, kind_tokens)
                scored_candidates.append((path, score))

    return texture_utils.select_best_scored_texture_candidate(
        scored_candidates,
        preferred_roots=roots,
        min_score=20,
    )


def unique_texture_target_path(texture_dir, source_path):
    return texture_utils.unique_texture_target_path(texture_dir, source_path)


def secure_project_textures(context):
    blend_dir = bpy.path.abspath("//")
    if not blend_dir or not os.path.isdir(blend_dir):
        raise RuntimeError("请先保存当前.blend文件，再执行资源贴图防丢失")

    texture_dir = ensure_directory(os.path.join(blend_dir, "textures"))
    work_dir = resolve_work_dir()
    stats = {
        "total_nodes": 0,
        "packed": 0,
        "copied": 0,
        "relinked": 0,
        "already_safe": 0,
        "skipped": 0,
        "missing": [],
        "errors": [],
    }
    processed_images = {}

    for owner_label, node, image in iter_texture_image_users():
        stats["total_nodes"] += 1
        image_key = image.as_pointer()
        if image_key in processed_images:
            continue
        processed_images[image_key] = True

        if image_is_packed(image):
            stats["packed"] += 1
            continue
        if not image_is_regular_file(image):
            stats["skipped"] += 1
            continue

        original_path = image_source_path(image)
        source_path = original_path if original_path and os.path.isfile(original_path) else ""
        was_relinked = False
        if not source_path:
            source_path = find_texture_candidate(image, original_path, work_dir)
            if source_path:
                was_relinked = True

        if not source_path or not os.path.isfile(source_path):
            stats["missing"].append(f"{image.name} ({owner_label})")
            continue

        try:
            target_path = unique_texture_target_path(texture_dir, source_path)
            if os.path.abspath(source_path) != os.path.abspath(target_path):
                shutil.copy2(source_path, target_path)
                stats["copied"] += 1
            else:
                stats["already_safe"] += 1
            image.filepath = bpy.path.relpath(target_path)
            try:
                image.reload()
            except Exception as reload_exc:
                stats["errors"].append(f"{image.name}: reload failed after relink: {reload_exc}")
            if was_relinked:
                stats["relinked"] += 1
        except Exception as exc:
            stats["errors"].append(f"{image.name}: {exc}")

    return stats


def smart_find_missing_textures(context):
    blend_dir = bpy.path.abspath("//")
    if not blend_dir or not os.path.isdir(blend_dir):
        raise RuntimeError("请先保存当前.blend文件，再执行智能查找丢失贴图")

    work_dir = resolve_work_dir()
    stats = {
        "total_nodes": 0,
        "missing_nodes": 0,
        "relinked": 0,
        "skipped": 0,
        "still_missing": [],
        "errors": [],
    }
    processed_images = {}

    for owner_label, node, image in iter_texture_image_users():
        stats["total_nodes"] += 1
        image_key = image.as_pointer()
        if image_key in processed_images:
            continue
        processed_images[image_key] = True

        if image_is_packed(image):
            continue
        if not image_is_regular_file(image):
            stats["skipped"] += 1
            continue

        original_path = image_source_path(image)
        if original_path and os.path.isfile(original_path):
            continue

        stats["missing_nodes"] += 1
        candidate = find_texture_candidate_smart(owner_label, node, image, original_path, work_dir)
        if not candidate:
            candidate = find_texture_candidate(image, original_path, work_dir)

        if not candidate or not os.path.isfile(candidate):
            stats["still_missing"].append(f"{image.name} ({owner_label})")
            continue

        try:
            image.filepath = bpy.path.relpath(candidate)
            stats["relinked"] += 1
            try:
                image.reload()
            except Exception as reload_exc:
                stats["errors"].append(f"{image.name}: reload failed after relink: {reload_exc}")
        except Exception as exc:
            stats["errors"].append(f"{image.name}: {exc}")

    return stats


def selected_map_keys(settings):
    return [
        key
        for key, definition in MAP_DEFINITIONS.items()
        if getattr(settings, definition["prop"], False)
    ]


def ensure_directory(path):
    os.makedirs(path, exist_ok=True)
    return path


def find_toolbag_executable():
    executable_names = [
        "toolbag.exe",
        "Toolbag.exe",
        "Marmoset Toolbag.exe",
        "marmosettoolbag.exe",
    ]

    for executable_name in executable_names:
        found_path = shutil.which(executable_name)
        if found_path and os.path.isfile(found_path):
            return found_path

    search_roots = []
    for env_name in ("ProgramFiles", "ProgramFiles(x86)", "LOCALAPPDATA"):
        env_path = os.environ.get(env_name)
        if env_path:
            search_roots.append(env_path)

    patterns = []
    for root in search_roots:
        patterns.extend([
            os.path.join(root, "Marmoset", "Toolbag*", "*.exe"),
            os.path.join(root, "Marmoset Toolbag*", "*.exe"),
            os.path.join(root, "*Marmoset*", "*Toolbag*", "*.exe"),
        ])

    candidates = []
    for pattern in patterns:
        for path in glob.glob(pattern):
            filename = os.path.basename(path).lower()
            if "toolbag" in filename and os.path.isfile(path):
                candidates.append(path)

    if not candidates:
        return ""

    candidates.sort(key=lambda path: os.path.getmtime(path), reverse=True)
    return candidates[0]


def resolve_toolbag_path(settings=None):
    prefs = get_addon_preferences()
    pref_path = getattr(prefs, "marmoset_toolbag_path", "")
    return bpy.path.abspath(pref_path) if pref_path else ""


def resolve_work_dir(settings=None):
    prefs = get_addon_preferences()
    pref_path = getattr(prefs, "marmoset_bake_work_dir", "")
    return bpy.path.abspath(pref_path) if pref_path else bpy.path.abspath("//marmoset_bake/")


def save_marmoset_path_to_preferences(context, toolbag_path):
    prefs = get_addon_preferences()
    if toolbag_path:
        prefs.marmoset_toolbag_path = toolbag_path
    bpy.ops.wm.save_userpref()


def iter_upstream_image_nodes(socket, visited=None):
    if visited is None:
        visited = set()
    if not socket:
        return

    for link in getattr(socket, "links", []):
        from_node = link.from_node
        if not from_node:
            continue
        node_key = from_node.as_pointer()
        if node_key in visited:
            continue
        visited.add(node_key)

        if from_node.type == "TEX_IMAGE" and from_node.image:
            yield from_node.image
            continue

        for input_socket in getattr(from_node, "inputs", []):
            yield from iter_upstream_image_nodes(input_socket, visited)


def image_node_matches_base_color(node):
    if node.type != "TEX_IMAGE" or not node.image:
        return False
    text = " ".join([
        getattr(node, "name", ""),
        getattr(node, "label", ""),
        getattr(node.image, "name", ""),
        getattr(node.image, "filepath", ""),
    ]).lower()
    keywords = (
        "basecolor",
        "base_color",
        "base color",
        "albedo",
        "diffuse",
        "diff",
        "color",
        "colour",
        "col",
    )
    return any(keyword in text for keyword in keywords)


def iter_named_base_color_images(obj):
    seen = set()
    for material_slot in getattr(obj, "material_slots", []):
        material = material_slot.material
        if not material or not material.use_nodes or not material.node_tree:
            continue
        for node in material.node_tree.nodes:
            if not image_node_matches_base_color(node):
                continue
            image_key = node.image.as_pointer()
            if image_key in seen:
                continue
            seen.add(image_key)
            yield node.image


def iter_base_color_images(obj):
    seen = set()
    for material_slot in getattr(obj, "material_slots", []):
        material = material_slot.material
        if not material or not material.use_nodes or not material.node_tree:
            continue
        for node in material.node_tree.nodes:
            if node.type != "BSDF_PRINCIPLED":
                continue
            base_color = node.inputs.get("Base Color")
            if not base_color:
                continue
            for image in iter_upstream_image_nodes(base_color):
                image_key = image.as_pointer()
                if image_key in seen:
                    continue
                seen.add(image_key)
                yield image

    for image in iter_named_base_color_images(obj):
        image_key = image.as_pointer()
        if image_key in seen:
            continue
        seen.add(image_key)
        yield image


def high_objects_missing_base_color_images(high_objects):
    missing = []
    for obj in high_objects:
        if not any(True for _image in iter_base_color_images(obj)):
            missing.append(obj.name)
    return missing


def first_vertex_color_attribute_name(obj):
    data = getattr(obj, "data", None)
    if not data:
        return ""

    color_attributes = getattr(data, "color_attributes", None)
    if color_attributes:
        active = getattr(color_attributes, "active_color", None) or getattr(color_attributes, "active", None)
        candidates = []
        if active:
            candidates.append(active)
        candidates.extend(attr for attr in color_attributes if attr not in candidates)
        for attr in candidates:
            try:
                if len(getattr(attr, "data", [])) > 0:
                    return getattr(attr, "name", "") or "Color"
            except Exception:
                continue

    vertex_colors = getattr(data, "vertex_colors", None)
    if vertex_colors:
        active = getattr(vertex_colors, "active", None)
        candidates = []
        if active:
            candidates.append(active)
        candidates.extend(attr for attr in vertex_colors if attr not in candidates)
        for attr in candidates:
            try:
                if len(getattr(attr, "data", [])) > 0:
                    return getattr(attr, "name", "") or "Color"
            except Exception:
                continue

    return ""


def object_has_albedo_source(obj):
    return any(True for _image in iter_base_color_images(obj)) or bool(first_vertex_color_attribute_name(obj))


def high_objects_missing_albedo_sources(high_objects):
    missing = []
    for obj in high_objects:
        if not object_has_albedo_source(obj):
            missing.append(obj.name)
    return missing


def export_image_for_toolbag(image, target_dir):
    ensure_directory(target_dir)
    source_path = bpy.path.abspath(image.filepath) if getattr(image, "filepath", "") else ""
    extension = os.path.splitext(source_path)[1].lower()
    if extension not in {".png", ".tga", ".tif", ".tiff", ".jpg", ".jpeg", ".exr", ".psd"}:
        extension = ".png"

    image_name = normalize_identifier(os.path.splitext(image.name)[0])
    target_path = os.path.join(target_dir, f"{image_name}{extension}")

    if source_path and os.path.isfile(source_path):
        if os.path.abspath(source_path) != os.path.abspath(target_path):
            shutil.copy2(source_path, target_path)
        return target_path

    original_filepath = image.filepath
    original_file_format = getattr(image, "file_format", None)
    try:
        if extension == ".png" and hasattr(image, "file_format"):
            image.file_format = "PNG"
        image.filepath_raw = target_path
        image.save()
        return target_path
    finally:
        image.filepath = original_filepath
        if original_file_format and hasattr(image, "file_format"):
            image.file_format = original_file_format


def prepare_high_material_textures(high_objects, target_dir):
    prepared = []
    assignments = []
    seen_images = set()
    for obj in high_objects:
        first_exported_path = ""
        for image in iter_base_color_images(obj):
            image_key = image.as_pointer()
            if image_key in seen_images:
                exported_path = next((item[2] for item in prepared if item[0] == image), "")
            else:
                seen_images.add(image_key)
                original_filepath = image.filepath
                try:
                    exported_path = export_image_for_toolbag(image, target_dir)
                    image.filepath = exported_path
                    prepared.append((image, original_filepath, exported_path))
                except Exception as exc:
                    print(f"PopTools Marmoset Baker: failed to prepare Base Color image '{image.name}': {exc}")
                    exported_path = ""
            if exported_path and not first_exported_path:
                first_exported_path = exported_path
        if first_exported_path:
            assignments.append({
                "object_name": obj.name,
                "source": "texture",
                "texture_path": first_exported_path.replace("\\", "/"),
            })
        else:
            color_attribute = first_vertex_color_attribute_name(obj)
            if color_attribute:
                assignments.append({
                    "object_name": obj.name,
                    "source": "vertex_color",
                    "color_attribute": color_attribute,
                    "texture_path": "",
                })
    return prepared, assignments


def restore_prepared_images(prepared_images):
    for image, original_filepath, _exported_path in prepared_images:
        try:
            image.filepath = original_filepath
        except Exception:
            pass


def export_bake_fbx(
    context,
    objects,
    fbx_path,
    high_objects=None,
    include_material_textures=False,
    flatten_hierarchy=False,
    merge_highs_name="",
):
    previous_active = context.view_layer.objects.active
    previous_selected = [obj for obj in context.scene.objects if obj.select_get()]
    prepared_images = []
    albedo_assignments = []
    original_parents = []
    original_names = []
    temp_export_objects = []

    try:
        if include_material_textures and high_objects:
            texture_dir = os.path.join(os.path.dirname(fbx_path), "source_textures")
            prepared_images, albedo_assignments = prepare_high_material_textures(high_objects, texture_dir)

        if merge_highs_name:
            high_ids = {obj.as_pointer() for obj in high_objects or []}
            lows = [obj for obj in objects if obj.as_pointer() not in high_ids]
            depsgraph = context.evaluated_depsgraph_get()

            def make_merged_export_object(source_objects, object_name):
                merge_parts = []
                for source_obj in source_objects:
                    evaluated_obj = source_obj.evaluated_get(depsgraph)
                    mesh = bpy.data.meshes.new_from_object(
                        evaluated_obj,
                        depsgraph=depsgraph,
                        preserve_all_data_layers=True,
                    )
                    temp_obj = bpy.data.objects.new(f"{object_name}_part", mesh)
                    temp_obj.matrix_world = source_obj.matrix_world.copy()
                    if not temp_obj.data.materials:
                        for material in getattr(source_obj.data, "materials", []):
                            temp_obj.data.materials.append(material)
                    context.collection.objects.link(temp_obj)
                    merge_parts.append(temp_obj)

                if not merge_parts:
                    return None
                if context.mode != "OBJECT":
                    bpy.ops.object.mode_set(mode="OBJECT")
                for obj in context.scene.objects:
                    obj.select_set(False)
                for obj in merge_parts:
                    obj.select_set(True)
                context.view_layer.objects.active = merge_parts[0]
                if len(merge_parts) > 1:
                    bpy.ops.object.join()
                merged_obj = context.view_layer.objects.active
                merged_obj.name = object_name
                rename_mesh_data(merged_obj)
                return merged_obj

            merged_high = make_merged_export_object(high_objects or [], f"{merge_highs_name}{HIGH_SUFFIX}")
            temp_export_objects = [obj for obj in [merged_high] if obj]

            if len(lows) == 1:
                original_names.append((lows[0], lows[0].name, getattr(lows[0].data, "name", "")))
                lows[0].name = f"{merge_highs_name}{LOW_SUFFIX}"
                rename_mesh_data(lows[0])
                export_lows = lows
            else:
                merged_low = make_merged_export_object(lows, f"{merge_highs_name}{LOW_SUFFIX}")
                export_lows = [merged_low] if merged_low else []
                temp_export_objects.extend(export_lows)

            objects = temp_export_objects[:1] + export_lows
            high_objects = [merged_high] if merged_high else []
        elif flatten_hierarchy:
            for obj in objects:
                original_parents.append((obj, obj.parent, obj.matrix_parent_inverse.copy(), obj.matrix_world.copy()))
                obj.parent = None
                obj.matrix_world = original_parents[-1][3]

        for obj in context.scene.objects:
            obj.select_set(False)

        for obj in objects:
            obj.select_set(True)

        context.view_layer.objects.active = objects[0]
        bpy.ops.export_scene.fbx(
            filepath=fbx_path,
            use_selection=True,
            object_types={"MESH"},
            apply_unit_scale=True,
            apply_scale_options="FBX_SCALE_NONE",
            bake_space_transform=False,
            use_mesh_modifiers=True,
            mesh_smooth_type="FACE",
            add_leaf_bones=False,
            path_mode="COPY",
            embed_textures=True,
        )
    finally:
        restore_prepared_images(prepared_images)

        for obj, parent, matrix_parent_inverse, matrix_world in original_parents:
            obj.parent = parent
            obj.matrix_parent_inverse = matrix_parent_inverse
            obj.matrix_world = matrix_world
        for obj, name, data_name in original_names:
            obj.name = name
            if getattr(obj, "data", None):
                obj.data.name = data_name
        for obj in temp_export_objects:
            if obj and obj.name in bpy.data.objects:
                mesh = obj.data
                bpy.data.objects.remove(obj, do_unlink=True)
                if mesh and mesh.users == 0:
                    bpy.data.meshes.remove(mesh)

        for obj in context.scene.objects:
            obj.select_set(False)

        for obj in previous_selected:
            if obj.name in context.scene.objects:
                obj.select_set(True)

        if previous_active and previous_active.name in context.scene.objects:
            context.view_layer.objects.active = previous_active

    return albedo_assignments


def prepare_single_bake_job(
    context,
    settings,
    map_keys,
    work_dir,
    output_dir,
    project_name,
    lows,
    highs,
    alignment_pairs=None,
    shared_output=False,
    reference_high=None,
    shared_material_name="",
    merge_shared_highs=False,
    allow_map_fallback_for_all=False,
    map_lookup_name="",
):
    fbx_path = os.path.join(work_dir, f"{project_name}_bake.fbx")
    script_path = os.path.join(work_dir, f"{project_name}_marmoset_bake.py")
    status_path = os.path.join(work_dir, f"{project_name}_marmoset_status.json")
    log_path = os.path.join(work_dir, f"{project_name}_marmoset_process.log")
    output_file = os.path.join(output_dir, f"{project_name}.png")

    if os.path.exists(status_path):
        os.remove(status_path)

    original_low_locations = {}
    moved_lows = []
    cleared_low_materials = []
    try:
        if alignment_pairs:
            original_low_locations, moved_lows = align_lows_to_high_origins(alignment_pairs)
        elif reference_high:
            original_low_locations, moved_lows = align_objects_to_origin(lows, reference_high)
        cleared_low_materials = clear_low_materials_for_export(lows)

        merge_highs_for_export = bool(shared_output and merge_shared_highs)
        export_objects = (list(highs) + list(lows)) if shared_output else (list(lows) + list(highs))
        high_albedo_textures = export_bake_fbx(
            context,
            export_objects,
            fbx_path,
            high_objects=highs,
            include_material_textures="albedo" in map_keys,
            flatten_hierarchy=shared_output and not merge_highs_for_export,
            merge_highs_name=project_name if merge_highs_for_export else "",
        )
    finally:
        restore_low_locations(original_low_locations)

    config = {
        "project_name": project_name,
        "fbx_path": fbx_path.replace("\\", "/"),
        "output_dir": output_dir.replace("\\", "/"),
        "output_file": output_file.replace("\\", "/"),
        "work_dir": work_dir.replace("\\", "/"),
        "high_albedo_textures": high_albedo_textures,
        "temporarily_aligned_lows": moved_lows,
        "cleared_low_materials": cleared_low_materials,
        "shared_output": bool(shared_output),
        "low_objects": [obj.name for obj in lows],
        "high_objects": [obj.name for obj in highs],
        "resolution": int(settings.resolution),
        "output_bits": int(settings.output_bits),
        "output_samples": int(settings.output_samples),
        "edge_padding": settings.edge_padding,
        "map_keys": map_keys,
        "close_toolbag_when_done": bool(settings.close_toolbag_when_done),
        "status_path": status_path.replace("\\", "/"),
    }
    write_toolbag_script(script_path, config)

    return {
        "lows": list(lows),
        "output_dir": output_dir,
        "work_dir": work_dir,
        "map_keys": list(map_keys),
        "apply_to_low_material": bool(settings.apply_to_low_material),
        "cleanup_when_done": bool(settings.close_toolbag_when_done),
        "shared_output": bool(shared_output),
        "shared_material_name": shared_material_name,
        "allow_map_fallback_for_all": bool(allow_map_fallback_for_all),
        "map_lookup_name": map_lookup_name or project_name,
        "fbx_path": fbx_path,
        "script_path": script_path,
        "status_path": status_path,
        "log_path": log_path,
    }


def write_toolbag_script(script_path, config):
    script = f'''# Auto-generated by PopTools. Run by Marmoset Toolbag at launch.
import json
import os
import time
import traceback
import mset

CONFIG = json.loads(r"""{json.dumps(config, ensure_ascii=False)}""")

MAP_ALIASES = {{
    "normal": ["Normals"],
    "ao": ["Ambient Occlusion", "AO"],
    "albedo": ["Albedo"],
    "curvature": ["Curvature"],
}}

STRICT_MAP_ALIASES = {{
    "normal": ["Normals"],
    "ao": ["Ambient Occlusion", "AO"],
    "albedo": ["Albedo"],
    "curvature": ["Curvature"],
}}

CANONICAL_SUFFIXES = {{
    "normal": "_normal",
    "ao": "_ao",
    "albedo": "_albedo",
    "curvature": "_curvature",
}}

IMAGE_EXTENSIONS = (".png", ".tga", ".tif", ".tiff", ".jpg", ".jpeg", ".exr", ".psd")
STATUS_EXTRA = {{}}

def write_status(state, message="", extra=None):
    if extra:
        STATUS_EXTRA.update(extra)
    payload = {{
        "state": state,
        "message": message,
        "time": time.time(),
    }}
    payload.update(STATUS_EXTRA)
    with open(CONFIG["status_path"], "w", encoding="utf-8") as status_file:
        json.dump(payload, status_file, ensure_ascii=False, indent=2)

def list_output_files():
    if not os.path.isdir(CONFIG["output_dir"]):
        return []
    return sorted(os.listdir(CONFIG["output_dir"]))

def try_set_attr(obj, attr, value):
    try:
        setattr(obj, attr, value)
        return True
    except Exception:
        return False

def force_png_output(obj):
    for attr in ("format", "outputFormat", "fileFormat", "imageFormat"):
        try_set_attr(obj, attr, "PNG")

def set_map_suffix(baker_map, key):
    suffix = CANONICAL_SUFFIXES.get(key)
    if suffix:
        try_set_attr(baker_map, "suffix", suffix)

def move_baked_files_to_output_dir():
    os.makedirs(CONFIG["output_dir"], exist_ok=True)
    moved = []
    work_dir = CONFIG["work_dir"]
    if not os.path.isdir(work_dir):
        return moved
    for filename in os.listdir(work_dir):
        source_path = os.path.join(work_dir, filename)
        if not os.path.isfile(source_path):
            continue
        if not filename.lower().endswith(IMAGE_EXTENSIONS):
            continue
        target_path = os.path.join(CONFIG["output_dir"], filename)
        try:
            os.replace(source_path, target_path)
            moved.append(filename)
        except Exception:
            pass
    return moved

def get_first_map(baker, aliases):
    for name in aliases:
        try:
            baker_map = baker.getMap(name)
            if baker_map:
                return baker_map
        except Exception:
            pass
    return None

def object_debug_name(obj):
    return getattr(obj, "name", type(obj).__name__)

def parent_chain_names(obj):
    names = []
    current = obj
    for _ in range(20):
        try:
            current = current.parent
        except Exception:
            current = None
        if not current:
            break
        names.append(object_debug_name(current))
    return names

def is_under_group(obj, group_name):
    return group_name in parent_chain_names(obj)

def scene_object_matches_high(obj, name):
    obj_name = getattr(obj, "name", "")
    base_name = name.rsplit("_high", 1)[0] if name.endswith("_high") else name
    if obj_name.lower() in {"low", "default", "scene", "render", "sky", "main camera"}:
        return False
    if obj_name.endswith("_low") or "_low" in obj_name:
        return False
    if not (is_under_group(obj, "High") or obj_name.endswith("_high") or "_high" in obj_name):
        return False
    return (
        obj_name == name
        or obj_name.startswith(name + ".")
        or obj_name.startswith(name + "_")
        or (obj_name == base_name and is_under_group(obj, "High"))
        or (obj_name.startswith(base_name + ".") and is_under_group(obj, "High"))
        or (obj_name.startswith(base_name + "_") and is_under_group(obj, "High"))
    )

def collect_children(obj):
    children = []
    try:
        direct_children = obj.getChildren()
    except Exception:
        direct_children = []
    for child in direct_children:
        children.append(child)
        children.extend(collect_children(child))
    return children

def find_high_scene_objects(name):
    matches = []
    try:
        obj = mset.findObject(name)
        if obj and scene_object_matches_high(obj, name):
            matches.append(obj)
    except Exception:
        pass

    try:
        all_objects = mset.getAllObjects()
    except Exception:
        all_objects = []

    for obj in all_objects:
        if scene_object_matches_high(obj, name):
            matches.append(obj)
        for child in collect_children(obj):
            if scene_object_matches_high(child, name):
                matches.append(child)

    if not matches:
        high_group = None
        try:
            high_group = mset.findObject("High")
        except Exception:
            high_group = None
        if high_group:
            high_children = collect_children(high_group)
            mesh_like_children = [
                child for child in high_children
                if object_debug_name(child).lower() not in {"high", "low"}
            ]
            if len(mesh_like_children) == 1:
                matches.append(mesh_like_children[0])

    unique_matches = []
    seen = set()
    for obj in matches:
        key = getattr(obj, "uid", None) or id(obj)
        if key in seen:
            continue
        seen.add(key)
        unique_matches.append(obj)
    return unique_matches

def assigned_object_matches(material, target_objects):
    target_ids = set(getattr(obj, "uid", None) or id(obj) for obj in target_objects)
    try:
        assigned_objects = material.getAssignedObjects()
    except Exception:
        assigned_objects = []
    for obj in assigned_objects:
        key = getattr(obj, "uid", None) or id(obj)
        if key in target_ids:
            return True
        for child in collect_children(obj):
            child_key = getattr(child, "uid", None) or id(child)
            if child_key in target_ids:
                return True
    return False

def find_materials_assigned_to_objects(target_objects):
    materials = []
    try:
        all_materials = mset.getAllMaterials()
    except Exception:
        all_materials = []
    for material in all_materials:
        if assigned_object_matches(material, target_objects):
            materials.append(material)
    return materials

def material_name_matches_high(material, object_name):
    material_name = getattr(material, "name", "").lower()
    object_name = (object_name or "").lower()
    base_name = object_name.rsplit("_high", 1)[0] if object_name.endswith("_high") else object_name
    if not material_name or "_low" in material_name:
        return False
    return (
        object_name in material_name
        or (base_name in material_name and ("high" in material_name or material_name.endswith("_mat")))
    )

def find_materials_named_like_high(object_name):
    try:
        all_materials = mset.getAllMaterials()
    except Exception:
        all_materials = []
    return [material for material in all_materials if material_name_matches_high(material, object_name)]

def list_scene_object_names():
    names = []
    try:
        all_objects = mset.getAllObjects()
    except Exception:
        all_objects = []
    for obj in all_objects:
        names.append(object_debug_name(obj))
        for child in collect_children(obj):
            names.append(object_debug_name(child))
    return sorted(set(names))

def set_subroutine_texture(material, slot_name, texture_path):
    assigned_fields = []
    srgb_fields = []
    field_names_seen = []
    try:
        material.setSubroutine(slot_name, "Albedo" if slot_name == "albedo" else "Texture")
    except Exception:
        pass

    subroutine = None
    for accessor in (
        lambda: getattr(material, slot_name),
        lambda: material.getSubroutine(slot_name),
    ):
        try:
            subroutine = accessor()
            if subroutine:
                break
        except Exception:
            pass

    if not subroutine:
        return {{
            "assigned_fields": assigned_fields,
            "srgb_fields": srgb_fields,
            "field_names": field_names_seen,
        }}

    common_fields = [
        "Albedo Map" if slot_name == "albedo" else "",
        "Texture",
        "texture",
        "Map",
        "map",
        "Albedo",
        "albedo",
        "Color",
        "color",
        "Base Color",
        "baseColor",
    ]
    try:
        field_names = list(subroutine.getFieldNames())
    except Exception:
        field_names = []
    field_names_seen = list(field_names)

    for field_name in common_fields + field_names:
        if not field_name:
            continue
        try:
            subroutine.setField(field_name, texture_path)
            assigned_fields.append(field_name)
            try:
                field_value = subroutine.getField(field_name)
                if hasattr(field_value, "sRGB"):
                    field_value.sRGB = True
                    srgb_fields.append(field_name)
            except Exception:
                pass
        except Exception:
            pass
    if slot_name == "albedo":
        try:
            subroutine.setField("sRGB Color", True)
            srgb_fields.append("sRGB Color")
        except Exception:
            pass

    return {{
        "assigned_fields": sorted(set(assigned_fields)),
        "srgb_fields": sorted(set(srgb_fields)),
        "field_names": field_names_seen,
    }}

def set_subroutine_vertex_color(material, color_attribute=""):
    field_results = []
    field_names_seen = []
    selected_subroutine = ""
    for subroutine_name in ("Vertex Color", "Vertex Colors", "VertexColor"):
        try:
            material.setSubroutine("albedo", subroutine_name)
            selected_subroutine = subroutine_name
            break
        except Exception as exc:
            field_results.append({{"target": "subroutine", "name": subroutine_name, "error": str(exc)}})

    subroutine = None
    for accessor in (
        lambda: getattr(material, "albedo"),
        lambda: material.getSubroutine("albedo"),
    ):
        try:
            subroutine = accessor()
            if subroutine:
                break
        except Exception:
            pass

    if subroutine:
        try:
            field_names_seen = list(subroutine.getFieldNames())
        except Exception:
            field_names_seen = []

        if color_attribute:
            for field_name in ["Vertex Color", "Vertex Color Map", "Color Attribute", "Attribute", "Channel", "Color Set"] + field_names_seen:
                if not field_name:
                    continue
                try:
                    subroutine.setField(field_name, color_attribute)
                    field_results.append({{"target": "field", "name": field_name, "value": color_attribute, "status": "set"}})
                except Exception:
                    pass
        try:
            subroutine.setField("sRGB Color", True)
            field_results.append({{"target": "field", "name": "sRGB Color", "value": True, "status": "set"}})
        except Exception:
            pass

    return {{
        "subroutine": selected_subroutine,
        "color_attribute": color_attribute,
        "field_results": field_results,
        "field_names": field_names_seen,
    }}

def create_blank_material(name):
    constructors = (
        lambda: mset.Material(),
        lambda: mset.Material(name),
    )
    last_error = ""
    for constructor in constructors:
        try:
            material = constructor()
            try:
                material.name = name
            except Exception:
                pass
            return material, ""
        except Exception as exc:
            last_error = str(exc)
    return None, last_error

def apply_high_albedo_materials():
    results = []
    for assignment in CONFIG.get("high_albedo_textures", []):
        object_name = assignment.get("object_name", "")
        source = assignment.get("source", "texture")
        texture_path = assignment.get("texture_path", "")
        color_attribute = assignment.get("color_attribute", "")
        if not object_name:
            results.append({{"object_name": object_name, "source": source, "texture_path": texture_path, "color_attribute": color_attribute, "status": "missing_object_name"}})
            continue
        if source == "texture" and (not texture_path or not os.path.isfile(texture_path)):
            results.append({{"object_name": object_name, "source": source, "texture_path": texture_path, "status": "missing_texture"}})
            continue

        objects = find_high_scene_objects(object_name)
        if not objects:
            results.append({{
                "object_name": object_name,
                "source": source,
                "texture_path": texture_path,
                "color_attribute": color_attribute,
                "status": "missing_object",
                "scene_objects": list_scene_object_names(),
            }})
            continue

        target_materials = find_materials_assigned_to_objects(objects)
        named_materials = find_materials_named_like_high(object_name)
        for named_material in named_materials:
            if named_material not in target_materials:
                target_materials.append(named_material)

        material = None
        material_source = "existing"
        if target_materials:
            material = target_materials[0]
        else:
            if source == "texture":
                material_source = "imported"
                try:
                    material = mset.importMaterial(texture_path)
                except Exception as exc:
                    results.append({{"object_name": object_name, "source": source, "texture_path": texture_path, "status": "import_failed", "error": str(exc)}})
                    continue
            else:
                material_source = "created"
                material, create_error = create_blank_material(object_name + "_vertex_color_mat")
                if not material:
                    results.append({{"object_name": object_name, "source": source, "color_attribute": color_attribute, "status": "material_create_failed", "error": create_error}})
                    continue

        materials_to_process = target_materials if target_materials else [material]
        material_results = []
        for current_material in materials_to_process:
            if source == "vertex_color":
                albedo_set_result = set_subroutine_vertex_color(current_material, color_attribute)
            else:
                albedo_set_result = set_subroutine_texture(current_material, "albedo", texture_path)
            material_results.append({{
                "material": getattr(current_material, "name", ""),
                "albedo_set_result": albedo_set_result,
            }})

        assigned_objects = []
        assigned_material_names = []
        assign_errors = []
        for obj in objects:
            for current_material in materials_to_process:
                try:
                    current_material.assign(obj, True)
                    assigned_objects.append(object_debug_name(obj))
                    assigned_material_names.append(getattr(current_material, "name", ""))
                except Exception as exc:
                    assign_errors.append({{"object": object_debug_name(obj), "material": getattr(current_material, "name", ""), "error": str(exc)}})

        results.append({{
            "object_name": object_name,
            "source": source,
            "texture_path": texture_path,
            "color_attribute": color_attribute,
            "material": getattr(material, "name", ""),
            "material_source": material_source,
            "existing_materials": [getattr(mat, "name", "") for mat in target_materials],
            "named_materials": [getattr(mat, "name", "") for mat in named_materials],
            "material_results": material_results,
            "matched_objects": [object_debug_name(obj) for obj in objects],
            "matched_parent_chains": dict((object_debug_name(obj), parent_chain_names(obj)) for obj in objects),
            "assigned_objects": assigned_objects,
            "assigned_materials": sorted(set(assigned_material_names)),
            "assign_errors": assign_errors,
            "status": "assigned" if assigned_objects else "assign_failed",
        }})
    return results

def map_identity(baker_map):
    parts = [type(baker_map).__name__]
    for attr in ("name", "suffix", "label"):
        try:
            value = getattr(baker_map, attr)
        except Exception:
            value = ""
        if value:
            parts.append(str(value))
    return " ".join(parts).lower()

def configure_maps(baker):
    enabled_maps = set(CONFIG["map_keys"])
    all_maps = []
    try:
        all_maps = baker.getAllMaps()
    except Exception:
        all_maps = []

    configured = []
    for baker_map in all_maps:
        identity = map_identity(baker_map)
        try:
            force_png_output(baker_map)
            baker_map.enabled = False
            configured.append({{"identity": identity, "enabled": False, "matched_key": None}})
        except Exception as exc:
            configured.append({{"identity": identity, "error": str(exc)}})

    enabled_exact = []
    missing_exact = []
    for key in sorted(enabled_maps):
        aliases = STRICT_MAP_ALIASES.get(key, [])
        baker_map = get_first_map(baker, aliases)
        if not baker_map:
            missing_exact.append({{"key": key, "aliases": aliases}})
            continue
        try:
            force_png_output(baker_map)
            set_map_suffix(baker_map, key)
            baker_map.enabled = True
            enabled_exact.append({{"key": key, "identity": map_identity(baker_map), "aliases": aliases}})
        except Exception as exc:
            missing_exact.append({{"key": key, "aliases": aliases, "error": str(exc)}})

    return {{"configured": configured, "enabled_exact": enabled_exact, "missing_exact": missing_exact}}

def main():
    write_status("starting", "Toolbag script started")
    mset.newScene()
    try:
        prefs = mset.getPreferences()
        prefs.importFbxWithMaterials = True
    except Exception as exc:
        write_status("preference_warning", "Could not enable FBX material import", {{"preference_error": str(exc)}})
    baker = mset.BakerObject()
    force_png_output(baker)
    baker.name = CONFIG["project_name"]
    write_status("importing", "Importing bake model")
    baker.importModel(CONFIG["fbx_path"])
    albedo_material_results = apply_high_albedo_materials()
    write_status("materials", "Applied high-poly albedo materials", {{"albedo_materials": albedo_material_results, "scene_objects_after_import": list_scene_object_names()}})
    baker.outputPath = CONFIG["output_file"]
    baker.outputBits = CONFIG["output_bits"]
    baker.outputSamples = CONFIG["output_samples"]
    baker.edgePadding = CONFIG["edge_padding"]
    baker.outputWidth = CONFIG["resolution"]
    baker.outputHeight = CONFIG["resolution"]

    configured_maps = configure_maps(baker)
    write_status("baking", "Bake started", {{"configured_maps": configured_maps, "albedo_materials": albedo_material_results, "output_path": baker.outputPath}})
    baker.bake()
    moved_files = move_baked_files_to_output_dir()
    write_status("complete", "Bake finished", {{"moved_files": moved_files, "output_files": list_output_files()}})

    if CONFIG["close_toolbag_when_done"]:
        mset.quit()

try:
    main()
except Exception as exc:
    write_status("failed", str(exc), {{"traceback": traceback.format_exc()}})
    raise
'''
    with open(script_path, "w", encoding="utf-8", newline="\n") as script_file:
        script_file.write(script)


def find_map_file(output_dir, low_obj_name, map_key, allow_fallback=False):
    definition = MAP_DEFINITIONS[map_key]
    image_extensions = {".png", ".tga", ".tif", ".tiff", ".jpg", ".jpeg", ".exr", ".psd"}
    low_base = clean_base_name(low_obj_name).lower()
    candidates = []

    if not os.path.isdir(output_dir):
        return None

    normalized_low_base = low_base.replace(" ", "_").replace("-", "_")
    for filename in os.listdir(output_dir):
        stem, extension = os.path.splitext(filename)
        if extension.lower() not in image_extensions:
            continue

        normalized_stem = stem.lower().replace(" ", "_").replace("-", "_")
        if not any(suffix in normalized_stem for suffix in definition["suffixes"]):
            continue
        if map_key == "normal" and ("bent" in normalized_stem or "object" in normalized_stem):
            continue

        if normalized_low_base and (
            normalized_stem == normalized_low_base
            or normalized_stem.startswith(normalized_low_base + "_")
        ):
            score = 20
        elif normalized_low_base and normalized_low_base in normalized_stem:
            score = 10
        elif allow_fallback:
            score = 1
        else:
            continue
        if extension.lower() == ".png":
            score += 2
        candidates.append((score, os.path.join(output_dir, filename)))

    if not candidates:
        return None

    candidates.sort(key=lambda item: (-item[0], item[1]))
    return candidates[0][1]


def ensure_material(obj):
    if obj.data.materials:
        material = obj.data.materials[0]
    else:
        material = bpy.data.materials.new(f"{clean_base_name(obj.name)}_mat")
        obj.data.materials.append(material)

    material.use_nodes = True
    return material


def ensure_shared_material(objects, material_name):
    material = bpy.data.materials.get(material_name)
    if material is None:
        material = bpy.data.materials.new(material_name)
    material.use_nodes = True

    for obj in objects:
        if not getattr(obj, "data", None):
            continue
        obj.data.materials.clear()
        obj.data.materials.append(material)

    return material


def get_principled_node(material):
    for node in material.node_tree.nodes:
        if node.type == "BSDF_PRINCIPLED":
            return node
    return None


def get_input(node, names):
    for name in names:
        socket = node.inputs.get(name)
        if socket:
            return socket
    return None


def apply_image_to_material(obj, map_key, image_path):
    material = ensure_material(obj)
    principled = get_principled_node(material)
    if not principled:
        return False

    nodes = material.node_tree.nodes
    links = material.node_tree.links
    image = bpy.data.images.load(image_path, check_existing=True)
    texture_node = nodes.new(type="ShaderNodeTexImage")
    texture_node.name = f"PopTools {map_key}"
    texture_node.label = f"PopTools {map_key}"
    texture_node.image = image

    material_kind = MAP_DEFINITIONS[map_key]["material_kind"]
    if material_kind == "NORMAL":
        image.colorspace_settings.name = "Non-Color"
        normal_node = nodes.new(type="ShaderNodeNormalMap")
        normal_node.name = "PopTools Normal Map"
        normal_node.label = "PopTools Normal Map"
        links.new(texture_node.outputs["Color"], normal_node.inputs["Color"])
        normal_input = get_input(principled, ["Normal"])
        if normal_input:
            links.new(normal_node.outputs["Normal"], normal_input)
            return True

    if material_kind == "AO":
        image.colorspace_settings.name = "Non-Color"
        texture_node.location.x -= 300
        texture_node.location.y -= 250
        return True

    if material_kind == "ALBEDO":
        color_input = get_input(principled, ["Base Color"])
        if color_input:
            links.new(texture_node.outputs["Color"], color_input)
            return True

    return False


def apply_maps_to_low_materials(
    lows,
    output_dir,
    map_keys,
    allow_fallback_for_all=False,
    shared_material_name="",
    map_lookup_name="",
):
    applied_count = 0
    missing = []
    allow_fallback = allow_fallback_for_all or len(lows) == 1
    target_lows = list(lows)

    if shared_material_name and target_lows:
        ensure_shared_material(target_lows, shared_material_name)
        target_lows = target_lows[:1]

    for low_obj in target_lows:
        lookup_name = map_lookup_name or low_obj.name
        for map_key in map_keys:
            image_path = find_map_file(output_dir, lookup_name, map_key, allow_fallback)
            if not image_path:
                missing.append(f"{lookup_name}:{map_key}")
                continue

            if apply_image_to_material(low_obj, map_key, image_path):
                applied_count += 1

    return applied_count, missing


def move_root_baked_files_to_textures(work_dir, output_dir):
    ensure_directory(output_dir)
    moved = []
    image_extensions = {".png", ".tga", ".tif", ".tiff", ".jpg", ".jpeg", ".exr", ".psd"}
    for filename in os.listdir(work_dir):
        source_path = os.path.join(work_dir, filename)
        if not os.path.isfile(source_path):
            continue
        if os.path.splitext(filename)[1].lower() not in image_extensions:
            continue
        target_path = os.path.join(output_dir, filename)
        try:
            shutil.move(source_path, target_path)
            moved.append(filename)
        except Exception as exc:
            print(f"PopTools Marmoset Baker failed to move {filename}: {exc}")
    return moved


def cleanup_bake_temp_files(job):
    work_dir = job.get("work_dir", "")
    temp_paths = [
        job.get("fbx_path"),
        job.get("script_path"),
        job.get("status_path"),
        job.get("log_path"),
    ]
    removed = []
    for path in temp_paths:
        if not path or not os.path.exists(path):
            continue
        try:
            os.remove(path)
            removed.append(path)
        except Exception as exc:
            print(f"PopTools Marmoset Baker failed to remove temp file {path}: {exc}")

    source_texture_dir = os.path.join(job.get("work_dir", ""), "source_textures")
    if os.path.isdir(source_texture_dir):
        try:
            shutil.rmtree(source_texture_dir)
            removed.append(source_texture_dir)
        except Exception as exc:
            print(f"PopTools Marmoset Baker failed to remove temp dir {source_texture_dir}: {exc}")

    if work_dir and os.path.isdir(work_dir):
        temp_dir_patterns = [
            os.path.join(work_dir, "*.fbm"),
        ]
        for pattern in temp_dir_patterns:
            for path in glob.glob(pattern):
                if not os.path.isdir(path):
                    continue
                try:
                    shutil.rmtree(path)
                    removed.append(path)
                except Exception as exc:
                    print(f"PopTools Marmoset Baker failed to remove temp dir {path}: {exc}")

        temp_file_patterns = [
            os.path.join(work_dir, "*_bake.fbx"),
            os.path.join(work_dir, "*_marmoset_bake.py"),
            os.path.join(work_dir, "*_marmoset_status.json"),
            os.path.join(work_dir, "*_marmoset_process.log"),
            os.path.join(work_dir, "*.log"),
            os.path.join(work_dir, "*.log.txt"),
        ]
        for pattern in temp_file_patterns:
            for path in glob.glob(pattern):
                if not os.path.isfile(path):
                    continue
                try:
                    os.remove(path)
                    removed.append(path)
                except Exception as exc:
                    print(f"PopTools Marmoset Baker failed to remove temp file {path}: {exc}")

    return removed


def notify_user(title, message, icon="INFO"):
    def draw(self, context):
        self.layout.label(text=message)

    try:
        bpy.context.window_manager.popup_menu(draw, title=title, icon=icon)
    except Exception:
        print(f"{title}: {message}")


def read_status_file(status_path):
    if not os.path.exists(status_path):
        return None
    try:
        with open(status_path, "r", encoding="utf-8") as status_file:
            return json.load(status_file)
    except Exception:
        return None


def launch_prepared_bake_job(toolbag_path, prepared_job, queued_jobs=None):
    log_file = open(prepared_job["log_path"], "w", encoding="utf-8")
    try:
        process = subprocess.Popen(
            [toolbag_path, prepared_job["script_path"]],
            stdout=log_file,
            stderr=subprocess.STDOUT,
        )
    except Exception:
        log_file.close()
        raise

    job = dict(prepared_job)
    job.update({
        "process": process,
        "log_file": log_file,
        "start_time": time.time(),
        "toolbag_path": toolbag_path,
        "queued_jobs": list(queued_jobs or []),
    })
    return job


def poll_active_bake_job():
    global ACTIVE_BAKE_JOB

    job = ACTIVE_BAKE_JOB
    if not job:
        return None

    status = read_status_file(job["status_path"])
    process = job["process"]
    process_returned = process.poll()

    if status and status.get("state") == "complete":
        moved = move_root_baked_files_to_textures(job["work_dir"], job["output_dir"])
        if moved:
            print("PopTools Marmoset Baker moved root output files: " + ", ".join(moved))
        applied_count = 0
        missing = []
        if job["apply_to_low_material"]:
            applied_count, missing = apply_maps_to_low_materials(
                job["lows"],
                job["output_dir"],
                job["map_keys"],
                allow_fallback_for_all=job.get("allow_map_fallback_for_all", False),
                shared_material_name=job.get("shared_material_name", ""),
                map_lookup_name=job.get("map_lookup_name", ""),
            )
        if missing:
            print("PopTools Marmoset Baker missing maps: " + ", ".join(missing))

        duration = time.time() - job["start_time"]
        message = f"烘焙完成，耗时 {duration:.1f}s"
        if job["apply_to_low_material"]:
            message += f"，已回填 {applied_count} 张贴图"
        queued_jobs = job.get("queued_jobs", [])
        if job.get("cleanup_when_done") and not queued_jobs:
            removed = cleanup_bake_temp_files(job)
            if removed:
                print("PopTools Marmoset Baker cleaned temp files: " + ", ".join(removed))
        job["log_file"].close()
        if queued_jobs:
            try:
                next_prepared_job = queued_jobs.pop(0)
                ACTIVE_BAKE_JOB = launch_prepared_bake_job(
                    job["toolbag_path"],
                    next_prepared_job,
                    queued_jobs,
                )
                notify_user("Marmoset烘焙", message + f"，继续下一组 ({len(queued_jobs) + 1} 组剩余)", "INFO")
                return 1.0
            except Exception as exc:
                ACTIVE_BAKE_JOB = None
                notify_user("Marmoset烘焙失败", f"启动下一组烘焙失败: {exc}", "ERROR")
                return None

        notify_user("Marmoset烘焙", message, "INFO")
        ACTIVE_BAKE_JOB = None
        return None

    if status and status.get("state") == "failed":
        notify_user("Marmoset烘焙失败", status.get("message", "未知错误"), "ERROR")
        print(status.get("traceback", ""))
        job["log_file"].close()
        ACTIVE_BAKE_JOB = None
        return None

    if process_returned is not None and process_returned != 0:
        notify_user("Marmoset烘焙失败", f"Toolbag进程退出码: {process_returned}", "ERROR")
        job["log_file"].close()
        ACTIVE_BAKE_JOB = None
        return None

    if process_returned == 0:
        notify_user("Marmoset烘焙失败", "Toolbag已退出，但没有写入完成状态文件", "ERROR")
        job["log_file"].close()
        ACTIVE_BAKE_JOB = None
        return None

    return 1.0


class POPTOOLS_OT_marmoset_mark_low(Operator):
    """给选中网格添加_low后缀"""
    bl_idname = "poptools.marmoset_mark_low"
    bl_label = "手动标记为_low"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        count = 0
        for obj in context.selected_objects:
            if obj.type != "MESH":
                continue
            obj.name = f"{clean_base_name(obj.name)}{LOW_SUFFIX}"
            count += 1

        self.report({"INFO"}, f"已标记 {count} 个低模对象")
        return {"FINISHED"}


class POPTOOLS_OT_marmoset_mark_high(Operator):
    """给选中网格添加_high后缀"""
    bl_idname = "poptools.marmoset_mark_high"
    bl_label = "手动标记为_high"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        count = 0
        for obj in context.selected_objects:
            if obj.type != "MESH":
                continue
            obj.name = f"{clean_base_name(obj.name)}{HIGH_SUFFIX}"
            count += 1

        self.report({"INFO"}, f"已标记 {count} 个高模对象")
        return {"FINISHED"}


class POPTOOLS_OT_marmoset_auto_mark_high_low(Operator):
    """自动识别并标记选中对象的高低模后缀"""
    bl_idname = "poptools.marmoset_auto_mark_high_low"
    bl_label = "自动标记高低模"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        settings = context.scene.poptools_props.marmoset_baker_settings
        objects = get_candidate_meshes(context, settings)
        pairs, leftovers = infer_high_low_pairs(objects, settings.model_name_prefix.strip())

        if leftovers:
            self.report({"ERROR"}, "存在无法自动配对的对象，请选择成对的高低模")
            return {"CANCELLED"}

        if not pairs:
            self.report({"ERROR"}, "需要至少两个网格对象才能自动标记")
            return {"CANCELLED"}

        self.report({"INFO"}, f"已自动标记 {len(pairs)} 组高低模")
        return {"FINISHED"}


class POPTOOLS_OT_marmoset_generate_lowpoly(Operator):
    """复制选中高模并使用Decimate与智能UV生成低模"""
    bl_idname = "poptools.marmoset_generate_lowpoly"
    bl_label = "一键快速低模"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        return hasattr(context.scene, "poptools_props") and any(
            obj.type == "MESH" for obj in context.selected_objects
        )

    def execute(self, context):
        settings = context.scene.poptools_props.marmoset_baker_settings
        high_objects = [obj for obj in context.selected_objects if obj.type == "MESH"]
        if not high_objects:
            self.report({"ERROR"}, "请先选择需要生成低模的高模对象")
            return {"CANCELLED"}

        if context.mode != "OBJECT":
            bpy.ops.object.mode_set(mode="OBJECT")

        ratio = max(0.0001, min(1.0, float(settings.lowpoly_decimate_ratio)))
        prefix = settings.model_name_prefix.strip()
        generated_lows = []
        original_selection = list(context.selected_objects)
        original_active = context.view_layer.objects.active
        pair_count = len(high_objects)

        try:
            for index, high_obj in enumerate(high_objects):
                base_name = build_pair_base_name(prefix, high_obj.name, index, pair_count)
                high_obj.name = f"{base_name}{HIGH_SUFFIX}"
                rename_mesh_data(high_obj)

                low_obj = high_obj.copy()
                low_obj.data = high_obj.data.copy()
                low_obj.animation_data_clear()
                low_obj.name = f"{base_name}{LOW_SUFFIX}"
                rename_mesh_data(low_obj)
                low_obj.data.materials.clear()
                context.collection.objects.link(low_obj)

                for selected in context.selected_objects:
                    selected.select_set(False)
                low_obj.select_set(True)
                context.view_layer.objects.active = low_obj

                decimate = low_obj.modifiers.new(name="Generate Low Decimate", type="DECIMATE")
                decimate.decimate_type = "COLLAPSE"
                decimate.ratio = ratio
                bpy.ops.object.modifier_apply(modifier=decimate.name)

                bpy.ops.object.mode_set(mode="EDIT")
                bpy.ops.mesh.select_all(action="SELECT")
                bpy.ops.uv.smart_project()
                bpy.ops.object.mode_set(mode="OBJECT")

                bpy.ops.object.shade_smooth()
                generated_lows.append(low_obj)
        except Exception as exc:
            if context.mode != "OBJECT":
                bpy.ops.object.mode_set(mode="OBJECT")
            self.report({"ERROR"}, f"生成低模失败: {exc}")
            return {"CANCELLED"}
        finally:
            if context.mode != "OBJECT":
                bpy.ops.object.mode_set(mode="OBJECT")
            for obj in context.scene.objects:
                obj.select_set(False)
            for obj in generated_lows:
                obj.select_set(True)
            context.view_layer.objects.active = generated_lows[0] if generated_lows else original_active
            if not generated_lows:
                for obj in original_selection:
                    if obj.name in bpy.data.objects:
                        obj.select_set(True)

        self.report({"INFO"}, f"已生成 {len(generated_lows)} 个低模，减面比例 {ratio:g}")
        return {"FINISHED"}


def mesh_has_boundary_edges(obj):
    """Return True when the mesh has open boundary edges."""
    mesh = obj.data
    mesh.update(calc_edges=True)
    edge_key_use_count = {tuple(sorted(edge.key)): 0 for edge in mesh.edges}
    for polygon in mesh.polygons:
        for edge_key in polygon.edge_keys:
            edge_key_use_count[tuple(sorted(edge_key))] = edge_key_use_count.get(tuple(sorted(edge_key)), 0) + 1
    return any(count == 1 for count in edge_key_use_count.values())


def fill_boundary_holes(context, obj):
    for selected in context.selected_objects:
        selected.select_set(False)
    obj.select_set(True)
    context.view_layer.objects.active = obj
    if context.mode != "OBJECT":
        bpy.ops.object.mode_set(mode="OBJECT")

    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_mode(type="EDGE")
    bpy.ops.mesh.select_all(action="DESELECT")
    bpy.ops.mesh.select_non_manifold(
        extend=False,
        use_wire=False,
        use_boundary=True,
        use_multi_face=False,
        use_non_contiguous=False,
        use_verts=False,
    )
    bpy.ops.mesh.fill_holes(sides=0)
    bpy.ops.object.mode_set(mode="OBJECT")


def run_voxel_remesh(context, obj, voxel_size=0.03):
    for selected in context.selected_objects:
        selected.select_set(False)
    obj.select_set(True)
    context.view_layer.objects.active = obj
    if context.mode != "OBJECT":
        bpy.ops.object.mode_set(mode="OBJECT")

    if hasattr(obj.data, "remesh_voxel_size"):
        obj.data.remesh_voxel_size = voxel_size
    if hasattr(obj.data, "remesh_voxel_adaptivity"):
        obj.data.remesh_voxel_adaptivity = 0.0
    if not hasattr(bpy.ops.object, "voxel_remesh"):
        raise RuntimeError("当前Blender版本未找到 voxel_remesh 操作")
    bpy.ops.object.voxel_remesh()


def apply_project_shrinkwrap(context, low_obj, high_obj, name):
    if context.mode != "OBJECT":
        bpy.ops.object.mode_set(mode="OBJECT")
    for selected in context.selected_objects:
        selected.select_set(False)
    low_obj.select_set(True)
    context.view_layer.objects.active = low_obj

    shrinkwrap = low_obj.modifiers.new(name=name, type="SHRINKWRAP")
    shrinkwrap.target = high_obj
    shrinkwrap.wrap_method = "PROJECT"
    shrinkwrap.use_project_x = True
    shrinkwrap.use_project_y = True
    shrinkwrap.use_project_z = True
    shrinkwrap.use_negative_direction = True
    shrinkwrap.use_positive_direction = True
    bpy.ops.object.modifier_apply(modifier=shrinkwrap.name)


def finish_zbrush_like_lowpoly_after_qremesh(context, low_obj, high_obj):
    if context.mode != "OBJECT":
        bpy.ops.object.mode_set(mode="OBJECT")
    if low_obj.name not in bpy.data.objects:
        raise RuntimeError(f"低模对象已不存在: {low_obj.name}")
    if high_obj.name not in bpy.data.objects:
        raise RuntimeError(f"高模对象已不存在: {high_obj.name}")

    for selected in context.selected_objects:
        selected.select_set(False)
    low_obj.select_set(True)
    context.view_layer.objects.active = low_obj
    if low_obj.data and low_obj.data.users > 1:
        low_obj.data = low_obj.data.copy()
        rename_mesh_data(low_obj)

    apply_project_shrinkwrap(context, low_obj, high_obj, "ZLike Project Shrinkwrap")

    subdivision = low_obj.modifiers.new(name="ZLike Divide", type="SUBSURF")
    subdivision.levels = 1
    subdivision.render_levels = 1
    context.view_layer.objects.active = low_obj
    bpy.ops.object.modifier_apply(modifier=subdivision.name)

    apply_project_shrinkwrap(context, low_obj, high_obj, "ZLike Project Shrinkwrap 2")

    decimate = low_obj.modifiers.new(name="ZLike Final Decimate", type="DECIMATE")
    decimate.decimate_type = "COLLAPSE"
    decimate.ratio = 0.04
    if hasattr(decimate, "use_collapse_triangulate"):
        decimate.use_collapse_triangulate = True
    context.view_layer.objects.active = low_obj
    bpy.ops.object.modifier_apply(modifier=decimate.name)


class POPTOOLS_OT_marmoset_zbrush_like_lowpoly(Operator):
    """复制选中模型并使用Blender内流程生成类ZBrush低模拓扑"""
    bl_idname = "poptools.marmoset_zbrush_like_lowpoly"
    bl_label = "类ZBrush低模拓扑"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        return hasattr(context.scene, "poptools_props") and any(
            obj.type == "MESH" for obj in context.selected_objects
        )

    def execute(self, context):
        high_objects = [obj for obj in context.selected_objects if obj.type == "MESH"]
        if not high_objects:
            self.report({"ERROR"}, "请先选择需要拓扑的高模对象")
            return {"CANCELLED"}

        if not hasattr(bpy.ops, "qremesher") or not hasattr(bpy.ops.qremesher, "remesh"):
            self.report({"ERROR"}, "未找到四边面重构插件 qremesher.remesh，请先启用 Quad Remesher")
            return {"CANCELLED"}

        if context.mode != "OBJECT":
            bpy.ops.object.mode_set(mode="OBJECT")

        self._generated_low_names = []
        self._pending_high_names = [obj.name for obj in high_objects]
        self._active_job = None
        original_selection = list(context.selected_objects)
        original_active = context.view_layer.objects.active
        self._original_selection_names = [obj.name for obj in original_selection]
        self._original_active_name = original_active.name if original_active else ""
        self._pair_count = len(high_objects)
        self._prefix = context.scene.poptools_props.marmoset_baker_settings.model_name_prefix.strip()
        self._job_index = 0

        try:
            self._start_next_qremesh_job(context)
        except Exception as exc:
            if context.mode != "OBJECT":
                bpy.ops.object.mode_set(mode="OBJECT")
            self.report({"ERROR"}, f"类ZBrush低模拓扑失败: {exc}")
            return {"CANCELLED"}

        self._timer = context.window_manager.event_timer_add(0.5, window=context.window)
        context.window_manager.modal_handler_add(self)
        self.report({"INFO"}, "已启动Quad Remesher，完成后将自动继续Shrinkwrap/细分/减面")
        return {"RUNNING_MODAL"}

    def _start_next_qremesh_job(self, context):
        if self._job_index >= len(self._pending_high_names):
            self._active_job = None
            return False

        high_name = self._pending_high_names[self._job_index]
        high_obj = bpy.data.objects.get(high_name)
        if not high_obj or high_obj.type != "MESH":
            raise RuntimeError(f"高模对象不存在或不是网格: {high_name}")

        base_name = build_pair_base_name(self._prefix, high_obj.name, self._job_index, self._pair_count)
        low_obj = high_obj.copy()
        low_obj.data = high_obj.data.copy()
        low_obj.animation_data_clear()
        low_obj.name = f"{base_name}{LOW_SUFFIX}"
        rename_mesh_data(low_obj)
        low_obj.data.materials.clear()
        context.collection.objects.link(low_obj)

        for selected in context.selected_objects:
            selected.select_set(False)
        low_obj.select_set(True)
        context.view_layer.objects.active = low_obj

        if mesh_has_boundary_edges(low_obj):
            fill_boundary_holes(context, low_obj)
        run_voxel_remesh(context, low_obj, 0.03)

        qremesher = getattr(context.scene, "qremesher", None)
        history_len = len(qremesher.history) if qremesher else 0
        self._active_job = {
            "high_name": high_obj.name,
            "low_name": low_obj.name,
            "history_len": history_len,
            "start_time": time.time(),
        }

        result = bpy.ops.qremesher.remesh("INVOKE_DEFAULT")
        if "CANCELLED" in result:
            raise RuntimeError("Quad Remesher启动失败")
        return True

    def _is_qremesh_done(self, context):
        if not self._active_job:
            return False
        low_obj = bpy.data.objects.get(self._active_job["low_name"])
        if not low_obj:
            return False
        qremesher = getattr(context.scene, "qremesher", None)
        if not qremesher:
            return False
        return (
            qremesher.history_object == low_obj
            and len(qremesher.history) > self._active_job["history_len"]
        )

    def _finish_all(self, context):
        if hasattr(self, "_timer") and self._timer:
            context.window_manager.event_timer_remove(self._timer)
            self._timer = None
        if context.mode != "OBJECT":
            bpy.ops.object.mode_set(mode="OBJECT")
        for obj in context.scene.objects:
            obj.select_set(False)
        selected_lows = []
        for name in getattr(self, "_generated_low_names", []):
            obj = bpy.data.objects.get(name)
            if obj:
                obj.select_set(True)
                selected_lows.append(obj)
        if selected_lows:
            context.view_layer.objects.active = selected_lows[0]
        else:
            active = bpy.data.objects.get(getattr(self, "_original_active_name", ""))
            if active:
                context.view_layer.objects.active = active
            for name in getattr(self, "_original_selection_names", []):
                obj = bpy.data.objects.get(name)
                if obj:
                    obj.select_set(True)

    def modal(self, context, event):
        if event.type == "ESC":
            self._finish_all(context)
            self.report({"WARNING"}, "类ZBrush低模拓扑已取消")
            return {"CANCELLED"}

        if event.type != "TIMER":
            return {"PASS_THROUGH"}

        try:
            if not self._active_job:
                self._finish_all(context)
                self.report({"INFO"}, f"已完成 {len(self._generated_low_names)} 个类ZBrush低模拓扑")
                return {"FINISHED"}

            if time.time() - self._active_job["start_time"] > 900:
                raise RuntimeError("等待Quad Remesher完成超时")

            if not self._is_qremesh_done(context):
                return {"RUNNING_MODAL"}

            low_obj = bpy.data.objects.get(self._active_job["low_name"])
            high_obj = bpy.data.objects.get(self._active_job["high_name"])
            finish_zbrush_like_lowpoly_after_qremesh(context, low_obj, high_obj)
            self._generated_low_names.append(low_obj.name)
            self._job_index += 1

            if self._start_next_qremesh_job(context):
                return {"RUNNING_MODAL"}

            self._finish_all(context)
            self.report({"INFO"}, f"已完成 {len(self._generated_low_names)} 个类ZBrush低模拓扑")
            return {"FINISHED"}
        except Exception as exc:
            self._finish_all(context)
            self.report({"ERROR"}, f"类ZBrush低模拓扑失败: {exc}")
            return {"CANCELLED"}


class POPTOOLS_OT_marmoset_show_selected_polycount(Operator):
    """在3D视图显示选中模型面数"""
    bl_idname = "poptools.marmoset_show_selected_polycount"
    bl_label = "查看选中模型面数"
    bl_options = {"REGISTER"}

    @classmethod
    def poll(cls, context):
        return any(obj.type == "MESH" for obj in context.selected_objects)

    def execute(self, context):
        selected_meshes = [obj for obj in context.selected_objects if obj.type == "MESH"]
        if not selected_meshes:
            self.report({"ERROR"}, "请先选择至少一个网格模型")
            return {"CANCELLED"}

        POLYCOUNT_OVERLAY_OBJECT_NAMES.clear()
        POLYCOUNT_OVERLAY_OBJECT_NAMES.extend(obj.name for obj in selected_meshes)
        POLYCOUNT_OVERLAY_COUNTS.clear()
        depsgraph = context.evaluated_depsgraph_get()
        for obj in selected_meshes:
            POLYCOUNT_OVERLAY_COUNTS[obj.name] = count_mesh_faces_and_tris(obj, depsgraph)
        ensure_polycount_overlay()

        total_faces = 0
        total_tris = 0
        for obj in selected_meshes:
            face_count, tri_count = POLYCOUNT_OVERLAY_COUNTS[obj.name]
            total_faces += face_count
            total_tris += tri_count

        self.report({"INFO"}, f"已显示 {len(selected_meshes)} 个模型，Faces:{total_faces:,} Tris:{total_tris:,}")
        return {"FINISHED"}


class POPTOOLS_OT_marmoset_clear_polycount_overlay(Operator):
    """清除3D视图中的模型面数显示"""
    bl_idname = "poptools.marmoset_clear_polycount_overlay"
    bl_label = "清除显示"
    bl_options = {"REGISTER"}

    def execute(self, context):
        clear_polycount_overlay()
        self.report({"INFO"}, "已清除模型面数显示")
        return {"FINISHED"}


class POPTOOLS_OT_marmoset_ai_translate_model_name(Operator):
    """将模型名称输入框内容进行AI翻译"""
    bl_idname = "poptools.marmoset_ai_translate_model_name"
    bl_label = "AI翻译"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        settings = context.scene.poptools_props.marmoset_baker_settings
        raw_name = (settings.model_name_prefix or "").strip()
        if not raw_name:
            self.report({"WARNING"}, "请先输入需要翻译的模型名称")
            return {"CANCELLED"}
        if settings.model_name_translate_in_progress:
            self.report({"WARNING"}, "模型名称AI翻译正在进行中")
            return {"CANCELLED"}

        ok, error = start_ai_translate_job(MARMORSET_MODEL_TRANSLATE_JOB_KEY, raw_name, MARMORSET_MODEL_TRANSLATE_PROMPT)
        if not ok:
            self.report({"ERROR"}, error)
            return {"CANCELLED"}

        settings.model_name_translate_in_progress = True
        settings.model_name_translate_progress = 0.08
        settings.model_name_translate_status = "正在启动AI翻译"
        if not bpy.app.timers.is_registered(poll_marmoset_model_name_translation):
            bpy.app.timers.register(poll_marmoset_model_name_translation, first_interval=0.2)
        self.report({"INFO"}, "模型名称AI翻译已在后台启动")
        return {"FINISHED"}


class POPTOOLS_OT_marmoset_clear_model_name(Operator):
    """清空模型名称输入框"""
    bl_idname = "poptools.marmoset_clear_model_name"
    bl_label = "清空模型名称"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        settings = context.scene.poptools_props.marmoset_baker_settings
        settings.model_name_prefix = ""
        return {"FINISHED"}


class POPTOOLS_OT_marmoset_auto_detect_toolbag(Operator):
    """自动查找Marmoset Toolbag路径"""
    bl_idname = "poptools.marmoset_auto_detect_toolbag"
    bl_label = "自动导入八猴路径"
    bl_options = {"REGISTER"}

    save_to_preferences: bpy.props.BoolProperty(
        name="保存到首选项",
        description="查找到路径后保存为插件默认路径",
        default=True
    )

    def execute(self, context):
        toolbag_path = find_toolbag_executable()
        if not toolbag_path:
            self.report({"WARNING"}, "未自动找到Marmoset Toolbag，请手动选择路径")
            return {"CANCELLED"}

        if self.save_to_preferences:
            save_marmoset_path_to_preferences(context, toolbag_path)

        self.report({"INFO"}, f"已找到Toolbag: {toolbag_path}")
        return {"FINISHED"}


class POPTOOLS_OT_marmoset_open_addon_preferences(Operator):
    """打开PopTools插件首选项"""
    bl_idname = "poptools.marmoset_open_addon_preferences"
    bl_label = "设置"
    bl_options = {"REGISTER"}

    def execute(self, context):
        bpy.ops.screen.userpref_show()
        context.preferences.active_section = 'ADDONS'
        bpy.ops.preferences.addon_show(module=__package__)
        return {"FINISHED"}


class POPTOOLS_OT_high_asset_one_click_process(Operator):
    """对选中高模资产进行减面和Base Color调色节点插入"""
    bl_idname = "poptools.high_asset_one_click_process"
    bl_label = "高模资产一键处理"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        return hasattr(context.scene, "poptools_props") and bool(selected_meshes(context))

    def execute(self, context):
        objects = selected_meshes(context)
        if not objects:
            self.report({"ERROR"}, "请先选择需要处理的高模资产")
            return {"CANCELLED"}

        try:
            decimated_count = apply_decimate_to_objects(context, objects, 0.1)
            material_count = insert_base_color_adjustments(objects)
        except Exception as exc:
            self.report({"ERROR"}, f"高模资产处理失败: {exc}")
            return {"CANCELLED"}

        self.report({"INFO"}, f"已处理 {decimated_count} 个模型，插入 {material_count} 个材质节点链")
        return {"FINISHED"}


class POPTOOLS_OT_high_asset_quick_decimate(Operator):
    """按指定比例对选中模型添加并应用Decimate修改器"""
    bl_idname = "poptools.high_asset_quick_decimate"
    bl_label = "快捷减面"
    bl_options = {"REGISTER", "UNDO"}

    ratio: bpy.props.FloatProperty(
        name="Ratio",
        description="Decimate Collapse比例",
        default=0.1,
        min=0.0001,
        max=1.0,
    )

    @classmethod
    def poll(cls, context):
        return hasattr(context.scene, "poptools_props") and bool(selected_meshes(context))

    def execute(self, context):
        objects = selected_meshes(context)
        if not objects:
            self.report({"ERROR"}, "请先选择需要减面的模型")
            return {"CANCELLED"}

        try:
            count = apply_decimate_to_objects(context, objects, self.ratio)
        except Exception as exc:
            self.report({"ERROR"}, f"快捷减面失败: {exc}")
            return {"CANCELLED"}

        self.report({"INFO"}, f"已按 {self.ratio:g} 减面并应用 {count} 个模型")
        return {"FINISHED"}


class POPTOOLS_OT_high_asset_optimize_material_color(Operator):
    """给选中模型材质插入颜色优化节点并设置Roughness"""
    bl_idname = "poptools.high_asset_optimize_material_color"
    bl_label = "材质颜色优化"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        return hasattr(context.scene, "poptools_props") and bool(selected_meshes(context))

    def execute(self, context):
        objects = selected_meshes(context)
        if not objects:
            self.report({"ERROR"}, "请先选择需要优化材质的模型")
            return {"CANCELLED"}

        try:
            material_count = insert_base_color_adjustments(objects)
        except Exception as exc:
            self.report({"ERROR"}, f"材质颜色优化失败: {exc}")
            return {"CANCELLED"}

        self.report({"INFO"}, f"已优化 {material_count} 个材质")
        return {"FINISHED"}


class POPTOOLS_OT_secure_texture_resources(Operator):
    """收拢工程贴图到textures目录并改为相对路径"""
    bl_idname = "poptools.secure_texture_resources"
    bl_label = "资源贴图防丢失"
    bl_description = "复制普通文件贴图到当前工程textures目录并改为相对路径；磁盘拷贝不能通过撤销操作回退，完成后请保存.blend"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        return hasattr(context.scene, "poptools_props")

    def execute(self, context):
        try:
            stats = secure_project_textures(context)
        except Exception as exc:
            self.report({"ERROR"}, str(exc))
            notify_user("资源贴图防丢失", str(exc), "ERROR")
            return {"CANCELLED"}

        message = (
            f"扫描 {stats['total_nodes']} 个贴图节点；"
            f"复制 {stats['copied']} 张；"
            f"修复 {stats['relinked']} 张；"
            f"已安全 {stats['already_safe']} 张；"
            f"打包贴图 {stats['packed']} 张；"
            f"跳过 {stats['skipped']} 张；"
            "请保存当前.blend"
        )
        if stats["missing"]:
            message += f"；仍缺失 {len(stats['missing'])} 张"
            print("PopTools missing texture resources: " + ", ".join(stats["missing"]))
        if stats["errors"]:
            message += f"；错误 {len(stats['errors'])} 个"
            print("PopTools texture resource errors: " + ", ".join(stats["errors"]))

        notify_user("资源贴图防丢失", message, "INFO" if not stats["missing"] and not stats["errors"] else "ERROR")
        self.report({"INFO" if not stats["missing"] and not stats["errors"] else "WARNING"}, message)
        return {"FINISHED"}


class POPTOOLS_OT_smart_find_missing_textures(Operator):
    """智能查找并重连当前工程中丢失的贴图"""
    bl_idname = "poptools.smart_find_missing_textures"
    bl_label = "智能查找丢失贴图"
    bl_description = "为普通文件贴图查找丢失路径并改为相对路径；完成后请保存.blend"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        return hasattr(context.scene, "poptools_props")

    def execute(self, context):
        try:
            stats = smart_find_missing_textures(context)
        except Exception as exc:
            self.report({"ERROR"}, str(exc))
            notify_user("智能查找丢失贴图", str(exc), "ERROR")
            return {"CANCELLED"}

        message = (
            f"扫描 {stats['total_nodes']} 个贴图节点；"
            f"发现丢失 {stats['missing_nodes']} 张；"
            f"重连 {stats['relinked']} 张；"
            f"跳过 {stats['skipped']} 张；"
            "请保存当前.blend"
        )
        if stats["still_missing"]:
            message += f"；仍缺失 {len(stats['still_missing'])} 张"
            print("PopTools still missing textures: " + ", ".join(stats["still_missing"]))
        if stats["errors"]:
            message += f"；错误 {len(stats['errors'])} 个"
            print("PopTools smart find texture errors: " + ", ".join(stats["errors"]))

        notify_user("智能查找丢失贴图", message, "INFO" if not stats["still_missing"] and not stats["errors"] else "ERROR")
        self.report({"INFO" if not stats["still_missing"] and not stats["errors"] else "WARNING"}, message)
        return {"FINISHED"}


class POPTOOLS_OT_marmoset_one_click_bake(Operator):
    """导出高低模并调用Marmoset Toolbag烘焙"""
    bl_idname = "poptools.marmoset_one_click_bake"
    bl_label = "一键Marmoset烘焙"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        return hasattr(context.scene, "poptools_props")

    def execute(self, context):
        global ACTIVE_BAKE_JOB

        if ACTIVE_BAKE_JOB:
            self.report({"WARNING"}, "已有Marmoset烘焙任务正在运行")
            return {"CANCELLED"}

        settings = context.scene.poptools_props.marmoset_baker_settings
        toolbag_path = resolve_toolbag_path(settings)
        if not toolbag_path:
            toolbag_path = find_toolbag_executable()
            if toolbag_path:
                save_marmoset_path_to_preferences(context, toolbag_path)
        if not toolbag_path or not os.path.isfile(toolbag_path):
            self.report({"ERROR"}, "请先设置有效的Marmoset Toolbag可执行文件路径")
            return {"CANCELLED"}

        map_keys = selected_map_keys(settings)
        if not map_keys:
            self.report({"ERROR"}, "至少需要选择一个烘焙通道")
            return {"CANCELLED"}

        objects = get_candidate_meshes(context, settings)
        active_object = context.view_layer.objects.active
        active_name = clean_base_name(active_object.name) if active_object and active_object.type == "MESH" else ""
        work_dir = ensure_directory(resolve_work_dir(settings))
        output_dir = ensure_directory(os.path.join(work_dir, "textures"))
        prepared_jobs = []

        if settings.bake_mode in {"MANY_TO_MANY", "MANY_TO_ONE"}:
            is_many_to_one = settings.bake_mode == "MANY_TO_ONE"
            if is_many_to_one:
                group, leftovers = infer_many_to_one_group(objects, settings.model_name_prefix.strip())
            else:
                group, leftovers = infer_many_to_many_group(objects, settings.model_name_prefix.strip())
            if leftovers:
                if is_many_to_one:
                    message = "存在未标记高低模的对象，请先在高低模识别区域完成标记: " + ", ".join(obj.name for obj in leftovers)
                else:
                    message = "存在未标记或无法一一配对的对象，请先在高低模识别区域完成标记: " + ", ".join(obj.name for obj in leftovers)
                notify_user("Marmoset烘焙", message, "ERROR")
                self.report({"ERROR"}, message)
                return {"CANCELLED"}
            if not group:
                mode_name = "多对一烘焙" if is_many_to_one else "多对多烘焙"
                self.report({"ERROR"}, f"{mode_name}需要至少一个低模和一个高模")
                return {"CANCELLED"}
            lows = group["lows"]
            highs = group["highs"]
            missing_uv_names = missing_uv_mesh_names(lows)
            if missing_uv_names:
                message = "低模缺少UV，已停止烘焙: " + ", ".join(missing_uv_names)
                notify_user("Marmoset烘焙", message, "ERROR")
                self.report({"ERROR"}, message)
                return {"CANCELLED"}
            if "albedo" in map_keys:
                missing_albedo_names = high_objects_missing_albedo_sources(highs)
                if missing_albedo_names:
                    message = "高模缺少Base Color贴图或顶点色，请给高模添加Base Color贴图或Vertex Color后再烘焙: " + ", ".join(missing_albedo_names)
                    notify_user("Marmoset烘焙", message, "ERROR")
                    self.report({"ERROR"}, message)
                    return {"CANCELLED"}
            try:
                shared_material_name = f"package_{normalize_identifier(active_name or group['base_name'])}_mat"
                prepared_jobs.append(prepare_single_bake_job(
                    context,
                    settings,
                    map_keys,
                    work_dir,
                    output_dir,
                    group["base_name"],
                    lows,
                    highs,
                    alignment_pairs=group["pairs"] or None,
                    shared_output=True,
                    shared_material_name=shared_material_name,
                    merge_shared_highs=is_many_to_one,
                    allow_map_fallback_for_all=is_many_to_one,
                    map_lookup_name=group["base_name"],
                ))
            except Exception as exc:
                self.report({"ERROR"}, f"准备烘焙数据失败: {exc}")
                return {"CANCELLED"}
        else:
            pairs, leftovers = infer_one_to_one_pairs(objects, settings.model_name_prefix.strip())
            if leftovers:
                message = "存在未标记或无法配对的对象，请先在高低模识别区域完成标记: " + ", ".join(obj.name for obj in leftovers)
                notify_user("Marmoset烘焙", message, "ERROR")
                self.report({"ERROR"}, message)
                return {"CANCELLED"}
            if not pairs:
                self.report({"ERROR"}, "需要至少一个_low低模和一个_high高模")
                return {"CANCELLED"}
            lows = [pair["low"] for pair in pairs]
            missing_uv_names = missing_uv_mesh_names(lows)
            if missing_uv_names:
                message = "低模缺少UV，已停止烘焙: " + ", ".join(missing_uv_names)
                notify_user("Marmoset烘焙", message, "ERROR")
                self.report({"ERROR"}, message)
                return {"CANCELLED"}
            if "albedo" in map_keys:
                highs = [pair["high"] for pair in pairs]
                missing_albedo_names = high_objects_missing_albedo_sources(highs)
                if missing_albedo_names:
                    message = "高模缺少Base Color贴图或顶点色，请给高模添加Base Color贴图或Vertex Color后再烘焙: " + ", ".join(missing_albedo_names)
                    notify_user("Marmoset烘焙", message, "ERROR")
                    self.report({"ERROR"}, message)
                    return {"CANCELLED"}
            try:
                for pair in pairs:
                    prepared_jobs.append(prepare_single_bake_job(
                        context,
                        settings,
                        map_keys,
                        work_dir,
                        output_dir,
                        pair["base_name"],
                        [pair["low"]],
                        [pair["high"]],
                        alignment_pairs=[pair],
                        shared_output=False,
                    ))
            except Exception as exc:
                self.report({"ERROR"}, f"准备烘焙数据失败: {exc}")
                return {"CANCELLED"}

        if not prepared_jobs:
            self.report({"ERROR"}, "没有可执行的Marmoset烘焙任务")
            return {"CANCELLED"}

        try:
            first_job = prepared_jobs[0]
            queued_jobs = prepared_jobs[1:]
            ACTIVE_BAKE_JOB = launch_prepared_bake_job(toolbag_path, first_job, queued_jobs)
        except Exception as exc:
            self.report({"ERROR"}, f"启动Toolbag失败: {exc}")
            return {"CANCELLED"}

        bpy.app.timers.register(poll_active_bake_job, first_interval=1.0)
        self.report({"INFO"}, f"已启动Marmoset异步烘焙，共 {len(prepared_jobs)} 个任务")
        return {"FINISHED"}


class POPTOOLS_OT_marmoset_open_work_dir(Operator):
    """打开Marmoset烘焙工作目录"""
    bl_idname = "poptools.marmoset_open_work_dir"
    bl_label = "打开烘焙目录"
    bl_options = {"REGISTER"}

    def execute(self, context):
        settings = context.scene.poptools_props.marmoset_baker_settings
        work_dir = ensure_directory(resolve_work_dir(settings))
        os.startfile(work_dir)
        return {"FINISHED"}


class POPTOOLS_PT_marmoset_baker(Panel):
    """Marmoset一键烘焙面板"""
    bl_label = "AI资产处理工具"
    bl_idname = "POPTOOLS_PT_marmoset_baker"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "PopTools"
    bl_order = 4
    bl_options = {"DEFAULT_CLOSED"}

    @classmethod
    def poll(cls, context):
        prefs = get_addon_preferences()
        return prefs and prefs.enable_marmoset_baker_tools

    def draw(self, context):
        layout = self.layout
        settings = context.scene.poptools_props.marmoset_baker_settings
        objects = get_candidate_meshes(context, settings)
        lows, highs, untagged = split_high_low(objects)

        layout.use_property_split = True
        layout.use_property_decorate = False

        prefs = get_addon_preferences()
        asset_button = layout.row()
        asset_button.scale_y = 1.35
        asset_button.operator("poptools.high_asset_one_click_process", icon="MESH_MONKEY")

        material_button = layout.row()
        material_button.scale_y = 1.2
        material_button.operator("poptools.high_asset_optimize_material_color", icon="MATERIAL")

        secure_texture_button = layout.row()
        secure_texture_button.scale_y = 1.2
        secure_texture_button.operator("poptools.secure_texture_resources", icon="FILE_REFRESH")
        smart_find_button = layout.row()
        smart_find_button.scale_y = 1.2
        smart_find_button.operator("poptools.smart_find_missing_textures", icon="VIEWZOOM")

        layout.label(text="快速减面", icon="MOD_DECIM")
        decimate_row = layout.row(align=True)
        for ratio in (0.8, 0.5, 0.3, 0.1):
            operator = decimate_row.operator(
                "poptools.high_asset_quick_decimate",
                text=f"{ratio:g}",
            )
            operator.ratio = ratio

        layout.separator()
        lowpoly_box = layout.box()
        lowpoly_box.prop(settings, "lowpoly_decimate_ratio")
        lowpoly_button = lowpoly_box.row()
        lowpoly_button.scale_y = 1.2
        lowpoly_button.operator("poptools.marmoset_generate_lowpoly", icon="MOD_DECIM")
        zbrush_like_button = lowpoly_box.row()
        zbrush_like_button.scale_y = 1.2
        zbrush_like_button.operator("poptools.marmoset_zbrush_like_lowpoly", icon="MOD_REMESH")
        polycount_row = lowpoly_box.row(align=True)
        polycount_row.scale_y = 1.1
        polycount_row.operator("poptools.marmoset_show_selected_polycount", icon="MESH_DATA")
        polycount_row.operator("poptools.marmoset_clear_polycount_overlay", text="清除显示", icon="X")

        layout.separator()
        layout.label(text="八猴烘焙设置", icon="MESH_MONKEY")
        layout.prop(prefs, "marmoset_toolbag_path", text="Toolbag路径")
        layout.prop(prefs, "marmoset_bake_work_dir", text="工作目录")
        path_row = layout.row(align=True)
        path_row.operator("poptools.marmoset_auto_detect_toolbag", icon="VIEWZOOM")
        path_row.operator("poptools.marmoset_open_addon_preferences", text="", icon="PREFERENCES")
        layout.prop(settings, "bake_scope")
        layout.prop(settings, "bake_mode")
        layout.prop(settings, "resolution")
        layout.prop(settings, "output_bits")
        layout.prop(settings, "output_samples")
        layout.prop(settings, "edge_padding")

        map_box = layout.box()
        map_box.label(text="烘焙通道", icon="TEXTURE")
        map_buttons = map_box.column(align=True)
        map_buttons.use_property_split = False
        map_row = map_buttons.row(align=True)
        map_row.prop(settings, "bake_normal", text="Normal", toggle=True)
        map_row.prop(settings, "bake_ao", text="AO", toggle=True)
        map_row = map_buttons.row(align=True)
        map_row.prop(settings, "bake_albedo", text="Albedo", toggle=True)
        map_row.prop(settings, "bake_curvature", text="Curvature", toggle=True)

        role_box = layout.box()
        role_box.label(text="高低模识别", icon="OUTLINER_OB_MESH")
        name_col = role_box.column(align=True)
        name_col.use_property_split = False
        name_col.label(text="模型名称:")
        name_row = name_col.row(align=True)
        name_row.prop(settings, "model_name_prefix", text="")
        name_row.operator("poptools.marmoset_clear_model_name", text="", icon="X")
        name_row.operator("poptools.marmoset_ai_translate_model_name", text="AI翻译", icon="OUTLINER_OB_LIGHT")
        if settings.model_name_translate_in_progress or settings.model_name_translate_progress > 0:
            progress_text = settings.model_name_translate_status or "AI翻译"
            name_col.prop(settings, "model_name_translate_progress", text=progress_text, slider=True)
        role_box.label(text=f"低模: {len(lows)}  高模: {len(highs)}  未标记: {len(untagged)}")
        role_box.operator("poptools.marmoset_auto_mark_high_low", icon="SORTSIZE")
        row = role_box.row(align=True)
        row.operator("poptools.marmoset_mark_low", icon="IMPORT")
        row.operator("poptools.marmoset_mark_high", icon="EXPORT")

        bake_row = layout.row()
        bake_row.scale_y = 1.68
        bake_row.operator("poptools.marmoset_one_click_bake", icon="TEXTURE")
        layout.prop(settings, "apply_to_low_material")
        layout.prop(settings, "close_toolbag_when_done")
        layout.operator("poptools.marmoset_open_work_dir", icon="FILE_FOLDER")


classes = (
    POPTOOLS_OT_marmoset_mark_low,
    POPTOOLS_OT_marmoset_mark_high,
    POPTOOLS_OT_marmoset_auto_mark_high_low,
    POPTOOLS_OT_marmoset_generate_lowpoly,
    POPTOOLS_OT_marmoset_zbrush_like_lowpoly,
    POPTOOLS_OT_marmoset_show_selected_polycount,
    POPTOOLS_OT_marmoset_clear_polycount_overlay,
    POPTOOLS_OT_marmoset_ai_translate_model_name,
    POPTOOLS_OT_marmoset_clear_model_name,
    POPTOOLS_OT_marmoset_auto_detect_toolbag,
    POPTOOLS_OT_marmoset_open_addon_preferences,
    POPTOOLS_OT_high_asset_one_click_process,
    POPTOOLS_OT_high_asset_quick_decimate,
    POPTOOLS_OT_high_asset_optimize_material_color,
    POPTOOLS_OT_secure_texture_resources,
    POPTOOLS_OT_smart_find_missing_textures,
    POPTOOLS_OT_marmoset_one_click_bake,
    POPTOOLS_OT_marmoset_open_work_dir,
    POPTOOLS_PT_marmoset_baker,
)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    clear_polycount_overlay()
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
